# Forge Studio isolated cloud AI test
No Arena Forge Pro infrastructure changes. TripoSR official public Gradio Space, anonymous single synthetic image, 128 marching-cubes resolution. No account tokens, no payment, no retries. API quota or service failure is an explicit failure, not simulated success.
Render's 750 free instance hours are shared across workspace services; no new compute service provisioned to protect the game. Existing Forge static site left intact. Supabase currently only has Arena Forge Pro project; do not use it for Forge Studio. Netlify new deployment deferred until provider probe proves real generation; no empty site creation or shared billing risk.
A successful GLB is an unrigged reconstruction; must be inspected and separately integrated with existing rig, UV and import pipeline. Anonymous public Space is not a production SLA.

## F01 private Kaggle research bridge

The connected R70.34 editor has a separate **Kaggle ile 3D üret** action. It uses
the Forge API access key in memory and calls the server's authenticated
`/v1/kaggle-jobs` endpoints. The Kaggle key is only read by the server.
The previous TripoSR, rig, text and photo endpoints use the same existing handlers.

Run `python studio/cloud-ai/private_api_kaggle.py` from a full checkout on Linux.
Use a single server with a private persistent SQLite directory on a local
filesystem. Place it behind HTTPS and restrict allowed origins to the editor host.
The runtime needs Pillow, Kaggle CLI 2.2.5 and the existing mobile QA Python
dependencies (NumPy, SciPy, trimesh, VTK, PyMeshFix 0.18.1 and MeshLib 3.2.0.75).
Enable only for private research. The Kaggle kernel uses RMBG-1.4 research weights.

| Server setting | Purpose |
| --- | --- |
| `FORGE_KAGGLE_RESEARCH=1` | Explicitly enables the Kaggle job endpoints |
| `FORGE_KAGGLE_OWNER` | The owner of the private Kaggle datasets and notebooks |
| `FORGE_KAGGLE_EXISTING_SLUG` | The existing model notebook slug that must reach a confirmed terminal state before further GPU allocation |
| `FORGE_KAGGLE_STATE_DIR` | Private persistent state directory with permissions 0700 |
| `KAGGLE_API_TOKEN` | Server-side Kaggle secret |
| `FORGE_API_TOKEN`, `FORGE_ALLOWED_ORIGINS` | Existing Forge server access key and allowed editor origins |

The image hash identifies repeated requests for this one-owner server. The
server reserves one active job, checks free GPU quota, creates a private
version-1 dataset and submits one private version-1 notebook. It records the
submission attempt before contacting Kaggle. An interrupted or ambiguous
submission is reconciled using the known notebook slug. If there is no
authoritative terminal status, the reservation persists even after the UI
wait limit. The SQLite record includes the accepted mobile GLB for repeat
downloads. Uploaded datasets and notebook outputs remain private in Kaggle.

A model is delivered only after the expected job, image and GLB hashes are
verified and the experimental mobile geometry gate passes. The editor still
asks before replacing the current scene. Visual acceptance and physical Android
performance require separate evidence. No GLB is substituted if the engine or
geometry check fails.

Local QA, without a Kaggle account or GPU allocation:

```sh
python verification/f01/kaggle_bridge_qa.py
node studio/cloud-ai/ai_import_patch.mjs
node studio/cloud-ai/connected_patch.mjs
node verification/f01/kaggle_editor_qa.mjs /path/to/editor-ready.glb /path/to/evidence
```

The browser QA requires Playwright Chromium and gltf-validator. It uses the
actual HTTP handler and a real GLB, with a local double for Kaggle status and output.

## F01 GPU-free generation (no Kaggle GPU queue)

The same `/v1/kaggle-jobs` API, SQLite job table, duplicate protection,
mobile geometry gate and editor dialog (**Sunucuda 3D üret**) can run without
any GPU:

1. **Server CPU** (`FORGE_LOCAL_TRIPOSG=1`): the Forge server itself runs
   `forge_mask.py` (BiRefNet soft alpha, MIT, optional SAM2.1 occluder bridge,
   Apache-2.0) and `triposg_cpu.py` (official TripoSG weights, MIT, revision
   `2c1c516d22d58db486a058d98d31bb6177344e06`, float32 hierarchical Lewiner
   extraction on CPU). No third-party inference service receives the image.
   Needs about 16 GB RAM (one fp32 TripoSG process holds 7-10 GB; run one at
   a time, two processes on 4 vCPU also oversubscribe threads) and 8 GB for
   weights. Measured on
   4 vCPU (Xeon, AMX): 50 flow steps take about 22-23 minutes in float32;
   extraction time is recorded per model in the F01 evidence. Pre-download
   the weights; requests never download models (`HF_HUB_OFFLINE=1`).
2. **Kaggle CPU session** (`FORGE_KAGGLE_RESEARCH=1`, `FORGE_KAGGLE_ACCELERATOR=cpu`):
   the private notebook requests no GPU/TPU, so it neither waits in the T4
   queue nor uses GPU quota. The exact `forge_mask.py` and `triposg_cpu.py`
   sources are embedded in the private notebook. Measured on 2026-11-28:
   setup about 4 minutes, generation about 3.5 hours per image in float32
   (about 3.8x slower than a 4 vCPU AMX server); sessions run in parallel.
   Jobs on this provider are reported as timed out only after 6 hours.

| Setting | Purpose |
| --- | --- |
| `FORGE_LOCAL_TRIPOSG=1` | Enables the server-CPU provider (mutually exclusive with `FORGE_KAGGLE_RESEARCH`) |
| `FORGE_LOCAL_WORK_DIR` | Private (0700) directory for per-job inputs, logs and outputs |
| `FORGE_LOCAL_PYTHON` | Python with torch 2.5.1 CPU, diffusers 0.32.2, transformers 4.49.0, timm, kornia, sam2 |
| `FORGE_TRIPOSG_SOURCE`, `FORGE_TRIPOSG_WEIGHTS` | TripoSG source checkout (`fc5c409…`) and weights directory |
| `FORGE_SAM2_CHECKPOINT` | Optional SAM2.1 tiny checkpoint (SHA-256 `7402e0d8…`) for occluder bridging |
| `FORGE_KAGGLE_ACCELERATOR=cpu` | Kaggle CPU session instead of T4 GPU |
| `FORGE_KAGGLE_BF16=1` | Allow bfloat16 transformer autocast when the Kaggle CPU has AMX/AVX512-BF16 |

The detail-preserving mask replaces upstream TripoSG preprocessing, which
binarises RMBG-1.4 alpha with Otsu and deletes parts under 200 px (HARD10:
peacock tail and bicycle shadow failures). RMBG-1.4 is not used on these paths.
Inputs and cut-outs are deleted after the GLB and its hashes are verified.

```sh
python verification/f01/local_triposg_qa.py   # provider lifecycle, restart, failure, tamper
FORGE_API_TOKEN=... node verification/f01/local_editor_qa.mjs http://127.0.0.1:8765 image.png evidence/
node verification/f01/glb_views.mjs THREE_DIR views.png "label|source.png|model.glb"
```
