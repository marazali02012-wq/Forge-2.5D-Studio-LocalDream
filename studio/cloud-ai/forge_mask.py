"""F01 detail-preserving object mask for image-to-3D (BiRefNet, MIT).

Root cause addressed (HARD10 peacock tail, bicycle spokes, thin geometry):
upstream TripoSG preprocessing binarises the RMBG-1.4 alpha with Otsu and then
deletes every connected part under 200 px. Thin feathers, spokes and limbs that
the network only predicts with partial confidence, or that are separated by a
one-pixel gap, are erased before 3D generation. RMBG-1.4 is also non-commercial.

This step keeps BiRefNet's soft alpha, removes only components that are both
small and far from the main object, and never uses a template or manual mask.

Usage: python forge_mask.py INPUT OUT_RGBA.png [--model BiRefNet|BiRefNet_HR]
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

MODELS = {
    # Pinned revisions: remote code is executed, so a moving branch is not trusted.
    "BiRefNet": ("ZhengPeng7/BiRefNet", "e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4", 1024),
    "BiRefNet_HR": ("ZhengPeng7/BiRefNet_HR", "a7a562f6fd16021180f2f4348f4de003a2d3d1e1", 2048),
}


def predict_alpha(image, model_name):
    import torch
    from torchvision import transforms
    from transformers import AutoModelForImageSegmentation

    repo, revision, size = MODELS[model_name]
    net = AutoModelForImageSegmentation.from_pretrained(repo, revision=revision, trust_remote_code=True)
    net.eval().float()
    tf = transforms.Compose([
        transforms.Resize((size, size)), transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    with torch.no_grad():
        pred = net(tf(image).unsqueeze(0))[-1].sigmoid()[0, 0]
    alpha = Image.fromarray((pred.numpy() * 255).round().astype(np.uint8)).resize(image.size, Image.BILINEAR)
    return np.asarray(alpha).astype(np.float32) / 255


def clean_alpha(alpha, keep_distance=0.04, min_far_fraction=0.002):
    """Keep soft alpha; drop only small specks far from the main object."""
    from scipy import ndimage

    solid = alpha > 0.5
    labels, count = ndimage.label(alpha > 0.05)
    if count == 0:
        raise ValueError("No foreground detected")
    sizes = ndimage.sum(np.ones_like(alpha), labels, range(1, count + 1))
    main = labels == (int(np.argmax(sizes)) + 1)
    # Distance (pixels) from the main component; thin parts split by a gap stay.
    distance = ndimage.distance_transform_edt(~main)
    limit = keep_distance * max(alpha.shape)
    total = float((alpha > 0.05).sum())
    keep = np.zeros_like(main)
    removed = []
    for index in range(1, count + 1):
        part = labels == index
        near = distance[part].min() <= limit
        large = sizes[index - 1] >= min_far_fraction * total
        if near or large:
            keep |= part
        else:
            removed.append(int(sizes[index - 1]))
    out = np.where(keep, alpha, 0)
    return out, {
        "components": int(count), "removed_components": len(removed),
        "removed_pixels": int(sum(removed)), "solid_pixels": int(solid.sum()),
        "soft_pixels": int(((alpha > 0.05) & (alpha <= 0.5)).sum()),
    }


def bridge_occluders(image, alpha, checkpoint, min_part=0.08, max_ratio=1.5):
    """Re-attach an object that splits the subject into separate large parts.

    Example failure (HARD10 cafe): a table hides a seated person's lap, so the
    salient mask holds a torso and legs with no connection, and image-to-3D
    reconstructs a fragmented person. SAM2 is prompted at the midpoint of the
    closest points of the two largest parts (negatives on the parts) and the
    segment is accepted only if it touches both parts, is not the subject
    itself and is not larger than max_ratio times the subject.
    """
    from scipy import ndimage

    solid = alpha > 0.5
    labels, count = ndimage.label(solid)
    total = float(solid.sum())
    sizes = ndimage.sum(solid, labels, range(1, count + 1)) if count else []
    big = [i + 1 for i, size in enumerate(sizes) if size >= min_part * total]
    info = {"large_parts": len(big), "occluder": "not_needed"}
    if len(big) < 2:
        return alpha, info
    big = sorted(big, key=lambda i: -sizes[i - 1])[:2]
    a, b = (labels == big[0]), (labels == big[1])
    distance, nearest = ndimage.distance_transform_edt(~a, return_indices=True)
    yb, xb = np.unravel_index(np.argmin(np.where(b, distance, np.inf)), b.shape)
    ya, xa = nearest[0][yb, xb], nearest[1][yb, xb]
    gap = float(distance[yb, xb])
    point = np.array([[(xa + xb) / 2, (ya + yb) / 2]], np.float32)
    negatives = np.array([ndimage.center_of_mass(part)[::-1] for part in (a, b)], np.float32)
    info.update(gap_px=round(gap, 1), prompt=[round(float(v), 1) for v in point[0]])

    import torch
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    predictor = SAM2ImagePredictor(build_sam2(
        "configs/sam2.1/sam2.1_hiera_t.yaml", str(checkpoint), device="cpu", apply_postprocessing=False))
    with torch.inference_mode():
        predictor.set_image(np.asarray(image))
        masks, scores, _ = predictor.predict(
            point_coords=np.vstack([point, negatives]), point_labels=np.array([1, 0, 0]),
            multimask_output=True)
    ring = ndimage.binary_dilation(a, iterations=6), ndimage.binary_dilation(b, iterations=6)
    best = None
    for mask, score in sorted(zip(masks.astype(bool), scores), key=lambda row: -row[1]):
        touches = all((mask & part).any() for part in ring)
        own = (mask & solid).sum() / max(1, mask.sum())
        ratio = mask.sum() / max(1.0, total)
        if touches and own < 0.5 and ratio <= max_ratio:
            best = (mask, float(score), float(ratio))
            break
    if best is None:
        info["occluder"] = "rejected"
        return alpha, info
    mask, score, ratio = best
    info.update(occluder="attached", sam_score=round(score, 3), occluder_area_ratio=round(ratio, 3))
    return np.maximum(alpha, mask.astype(np.float32)), info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--model", default="BiRefNet", choices=sorted(MODELS))
    ap.add_argument("--sam2-checkpoint", help="SAM2.1 tiny checkpoint enables occluder bridging")
    args = ap.parse_args()
    started = time.time()
    image = ImageOps.exif_transpose(Image.open(args.image)).convert("RGB")
    alpha, stats = clean_alpha(predict_alpha(image, args.model))
    if args.sam2_checkpoint:
        alpha, bridge = bridge_occluders(image, alpha, args.sam2_checkpoint)
        stats["bridge"] = bridge
    rgba = np.dstack([np.asarray(image), (alpha * 255).round().astype(np.uint8)])
    Image.fromarray(rgba, "RGBA").save(args.out)
    report = {
        "mask_model": args.model, "revision": MODELS[args.model][1], "license": "MIT",
        "binarized": False, "seconds": round(time.time() - started, 1),
        "input_sha256": hashlib.sha256(Path(args.image).read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(Path(args.out).read_bytes()).hexdigest(), **stats,
    }
    Path(args.out).with_suffix(".mask.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
