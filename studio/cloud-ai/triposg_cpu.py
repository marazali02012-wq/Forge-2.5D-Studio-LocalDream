"""F01 TripoSG on CPU: official weights and pipeline, CPU/float32 geometry extraction.

Why: the free Kaggle T4 queue can stall for hours and free ZeroGPU quota can be
zero. TripoSG's upstream extractor hard-codes CUDA (DiffDMC import and a CUDA
float16 dilation buffer). This module keeps the upstream diffusion pipeline and
replaces only those two device assumptions with the same hierarchical Lewiner
algorithm on CPU in float32. No template, proxy mesh or ground truth is used.

Usage:
    python triposg_cpu.py SOURCE_TRIPOSG_DIR WEIGHTS_DIR INPUT_RGBA.png OUT.glb [--steps 50]
INPUT must already be an RGBA cut-out (alpha = object mask), produced by Forge's
own segmentation step, so mask quality can be audited separately.
"""
import argparse
import hashlib
import json
import sys
import time
import types
from pathlib import Path

import numpy as np


EXTRACT_STATS = {}


def install_cpu_shims():
    # Upstream imports DiffDMC unconditionally; it is used only on the flash path.
    if "diso" not in sys.modules:
        stub = types.ModuleType("diso")

        class DiffDMC:  # pragma: no cover - guard only
            def __init__(self, *_, **__):
                raise RuntimeError("DiffDMC (CUDA) is not available on the CPU path")

        stub.DiffDMC = DiffDMC
        sys.modules["diso"] = stub


def expand_edge_region_cpu(edge_coords, grid_size):
    import torch

    # Same dilation as upstream expand_edge_region_fast, on the input's device and float32.
    grid = torch.zeros((grid_size,) * 3, device=edge_coords.device, dtype=torch.float32)
    grid[edge_coords[:, 0], edge_coords[:, 1], edge_coords[:, 2]] = 1
    k, p = (5, 2) if grid_size < 512 else (3, 1)
    pooled = torch.nn.functional.max_pool3d(grid[None, None], kernel_size=k, stride=1, padding=p)[0, 0]
    low = torch.nonzero(pooled, as_tuple=False).to(torch.int32)
    offsets = torch.tensor([[a, b, c] for a in (0, 1) for b in (0, 1) for c in (0, 1)],
                           dtype=torch.int32, device=low.device)
    return (low[:, None, :] * 2 + offsets[None]).reshape(-1, 3)


def band_candidates(logits):
    """Upstream band selection, evaluated with upstream's float16 semantics.

    Upstream stores the coarse grid as float16 and keeps voxels where
    |2*sigmoid(x)-1| < 1, i.e. where the float16 result is not saturated
    (about |x| < 8). On a float32 grid the same expression is true almost
    everywhere, which refined the whole 512^3 grid (134,217,728 queries for
    the HARD10 peacock) instead of the surface band. Values stay float32.
    """
    import torch
    from triposg import inference_utils as iu

    return iu.find_candidates_band(logits.to(torch.float16), 1.0)


def hierarchical_extract_cpu(*args, **kwargs):
    # Upstream decorates its extractor with @torch.no_grad(); without it a
    # direct call records autograd state for every query chunk (OOM).
    import torch

    with torch.inference_mode():
        return _hierarchical_extract_cpu(*args, **kwargs)


def _hierarchical_extract_cpu(geometric_func, device, bounds=(-1.005, -1.005, -1.005, 1.005, 1.005, 1.005),
                             dense_octree_depth=8, hierarchical_octree_depth=9, chunk=None):
    import torch
    from skimage import measure
    from triposg import inference_utils as iu

    if isinstance(bounds, float):
        bounds = [-bounds, -bounds, -bounds, bounds, bounds, bounds]
    bbox_min = torch.tensor(bounds[0:3], device=device)
    bbox_max = torch.tensor(bounds[3:6], device=device)
    xyz, grid_size, _ = iu.generate_dense_grid_points_gpu(
        bbox_min=bbox_min, bbox_max=bbox_max, octree_depth=dense_octree_depth, indexing="ij")
    started = time.time()
    logits = geometric_func(xyz.unsqueeze(0)).float().view(*grid_size)
    EXTRACT_STATS["dense_queries"] = int(xyz.shape[0])
    EXTRACT_STATS["dense_seconds"] = round(time.time() - started, 1)
    for i in range(hierarchical_octree_depth - dense_octree_depth):
        size = 2 ** (dense_octree_depth + i + 1)
        half = size / 2
        high = torch.nn.functional.interpolate(logits[None, None], scale_factor=2)[0, 0]
        edges = band_candidates(logits)
        coords = expand_edge_region_cpu(edges, int(size / 2)).float()
        norm = (coords - half) * (abs(bounds[0]) / half)
        started = time.time()
        values = geometric_func(norm.unsqueeze(0)).float()[0, :, 0]
        EXTRACT_STATS[f"band_queries_{size}"] = int(norm.shape[0])
        EXTRACT_STATS[f"band_seconds_{size}"] = round(time.time() - started, 1)
        print(json.dumps(EXTRACT_STATS), flush=True)
        idx = (norm * (half / abs(bounds[0])) + half).long()
        high[idx[:, 0], idx[:, 1], idx[:, 2]] = values
        logits = high
    v, f, _, _ = measure.marching_cubes(logits.cpu().numpy(), 0, method="lewiner")
    size = (bbox_max - bbox_min).cpu().numpy()
    v = v / (2 ** hierarchical_octree_depth) * size + bbox_min.cpu().numpy()
    return [(v.astype(np.float32), np.ascontiguousarray(f))]


def rgba_to_engine_input(path):
    """Upstream load_image framing for a given alpha: bbox of alpha>0, 10% padding, white."""
    from PIL import Image

    img = Image.open(path).convert("RGBA")
    if max(img.size) > 2000:
        img.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
    rgba = np.asarray(img).astype(np.float32) / 255
    alpha = rgba[..., 3:]
    ys, xs = np.nonzero(alpha[..., 0] > 0)
    if len(xs) == 0:
        raise ValueError("Empty object mask")
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgb = (rgba[..., :3] * alpha + (1 - alpha))[y0:y1, x0:x1]
    h, w = rgb.shape[:2]
    if w > h:
        px = int(w * 0.1); py = int(px + (w - h) / 2)
    else:
        py = int(h * 0.1); px = int(py + (h - w) / 2)
    canvas = np.ones((h + 2 * py, w + 2 * px, 3), np.float32)
    canvas[py:py + h, px:px + w] = rgb
    return Image.fromarray((canvas * 255).astype(np.uint8))


def weights_revision(weights):
    """Commit recorded by huggingface_hub for a local_dir snapshot, if unique."""
    revisions = {path.read_text().splitlines()[0].strip()
                 for path in Path(weights).glob(".cache/huggingface/download/**/*.metadata")}
    return revisions.pop() if len(revisions) == 1 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("weights")
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--guidance", type=float, default=7.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--depth", type=int, default=9)
    ap.add_argument("--dense-depth", type=int, default=8, help="Upstream default 8; lower only for smoke tests")
    ap.add_argument("--bf16-transformer", action="store_true",
                    help="Run only the flow transformer under CPU bfloat16 autocast (AMX); VAE and extraction stay float32")
    ap.add_argument("--bf16-decoder", action="store_true",
                    help="Research: VAE geometry-query matmuls under CPU bfloat16 autocast")
    ap.add_argument("--latents", help="Decode these saved latents instead of running diffusion (A/B of extraction)")
    args = ap.parse_args()

    install_cpu_shims()
    sys.path.insert(0, args.source)
    import torch
    import trimesh
    from triposg import inference_utils as iu
    from triposg.pipelines import pipeline_triposg as pt
    from triposg.pipelines.pipeline_triposg import TripoSGPipeline

    iu.hierarchical_extract_geometry = hierarchical_extract_cpu
    pt.hierarchical_extract_geometry = hierarchical_extract_cpu
    torch.set_num_threads(max(1, torch.get_num_threads()))

    started = time.time()
    pipe = TripoSGPipeline.from_pretrained(args.weights).to("cpu", torch.float32)
    if args.bf16_transformer:
        forward = pipe.transformer.forward

        def bf16_forward(*a, **k):
            with torch.autocast("cpu", dtype=torch.bfloat16):
                out = forward(*a, **k)
            # Guidance mixing and the scheduler step stay in float32.
            if isinstance(out, tuple):
                return tuple(o.float() if torch.is_tensor(o) else o for o in out)
            out.sample = out.sample.float()
            return out

        pipe.transformer.forward = bf16_forward
    vae_decode = pipe.vae.decode
    saved = {}

    def recorded_decode(z, *a, **k):
        # Latents are saved once per run for reproducible extraction A/B tests.
        if "z" not in saved:
            saved["z"] = z.detach().float().clone()
            torch.save(saved["z"], Path(args.out).with_suffix(".latents.pt"))
        if args.bf16_decoder:
            # Research flag. Query coordinates and Fourier features stay float32
            # (autocast only lowers matmuls); results must pass the A/B check.
            with torch.autocast("cpu", dtype=torch.bfloat16):
                out = vae_decode(z, *a, **k)
            out.sample = out.sample.float()
            return out
        return vae_decode(z, *a, **k)

    pipe.vae.decode = recorded_decode
    timings = {}
    decode = pt.hierarchical_extract_geometry

    def timed_decode(*a, **k):
        timings["denoise_done"] = time.time()
        return decode(*a, **k)

    pt.hierarchical_extract_geometry = timed_decode
    loaded = time.time()
    image = rgba_to_engine_input(args.image)
    image.save(Path(args.out).with_suffix(".engine_input.png"))
    if args.latents:
        z = torch.load(args.latents)
        timings["denoise_done"] = time.time()
        out = decode(lambda x: pipe.vae.decode(z, sampled_points=x).sample, torch.device("cpu"),
                     bounds=(-1.005, -1.005, -1.005, 1.005, 1.005, 1.005),
                     dense_octree_depth=args.dense_depth, hierarchical_octree_depth=args.depth)[0]
    else:
        out = pipe(image=image, generator=torch.Generator("cpu").manual_seed(args.seed),
                   num_inference_steps=args.steps, guidance_scale=args.guidance,
                   use_flash_decoder=False, dense_octree_depth=args.dense_depth,
                   hierarchical_octree_depth=args.depth).samples[0]
    if out[0] is None:
        raise SystemExit("Geometry extraction failed")
    mesh = trimesh.Trimesh(out[0], out[1], process=False)
    mesh.export(args.out)
    raw = Path(args.out).read_bytes()
    report = {
        "engine": "TripoSG", "model_revision": weights_revision(args.weights),
        "device": "cpu", "dtype": "float32", "actual_inference": True,
        "extractor": "hierarchical_lewiner_cpu", "octree_depth": args.depth, "dense_depth": args.dense_depth,
        "steps": args.steps, "guidance": args.guidance, "seed": args.seed,
        "faces": int(len(mesh.faces)), "vertices": int(len(mesh.vertices)),
        "transformer_precision": "bfloat16-autocast" if args.bf16_transformer else "float32",
        "decoder_precision": "bfloat16-autocast" if args.bf16_decoder else "float32",
        "latents_from": hashlib.sha256(Path(args.latents).read_bytes()).hexdigest() if args.latents else None,
        "load_seconds": round(loaded - started, 1), "inference_seconds": round(time.time() - loaded, 1),
        "denoise_seconds": round(timings.get("denoise_done", loaded) - loaded, 1),
        "extraction": EXTRACT_STATS,
        "input_sha256": hashlib.sha256(Path(args.image).read_bytes()).hexdigest(),
        "glb_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
    }
    Path(args.out).with_suffix(".report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
