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
