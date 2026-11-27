# R70.18 surface lab (experimental)
Base R70.17 remains unchanged. This is a standalone WASM bridge experiment, not a production modeler release.
PMP upstream: 6221d8f531a9b32893a4f4079c96702471334503 (MIT). MC33 header-only upstream: eef8f8f4d70527af74b988869e34f887ef9ed7ba (MIT).
PMP first: bounded explicit smoothing on indexed meshes, locks open borders and preserves vertex IDs. Not tangential remeshing yet. No UV/normal rewriting; callers must recompute normals after success. Reject invalid/nonmanifold inputs; callers keep originals and check face flips, self-intersections and material/UV seams before accepting. MC33 is for scalar grids only, not existing anatomical meshes. No automatic conversion of the current body or clothes.
Meshoptimizer stays at the existing R70.17 integration; no additional version introduced.
CI builds and tests a small open patch and a closed sphere. These do not establish garment quality, browser integration, mobile performance or visual acceptance. R70.17 remains RED. Physical device tests and front/side/back visual comparison are still required. No paid API.
