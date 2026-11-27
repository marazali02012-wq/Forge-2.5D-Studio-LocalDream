# Forge — gerçek TripoSR mobil fizibilite

- 46050513213: x86_64 CPU, 2 threads, 64³ grid, 12.7705 s, peak 3839.77 MiB, 9398 triangles, watertight, GLB 188960 bytes.
- 46051089352: native aarch64 Linux CPU (not Android), prepacking disabled, basic graph optimizations, 2 threads, 4096-point batches; load/encoder peak 3793.04 MiB, 22.311 s, 9528 triangles, watertight, GLB 191588 bytes. Model weights SHA256 checked. Reconstruction succeeded; overall workflow failed in ORT conversion due to missing onnx package.
- 46051263292: installed missing dependency; ORT conversion succeeded, direct bytes + direct initializer mode segfaulted (139) before successful inference. Do not use that configuration in a phone build.
- 46051410103: raw ONNX no graph optimization, single thread, and ORT file path alternative submitted; pending at report creation.

Both completed GLB artifacts were downloaded and independently opened with trimesh. x86 2 components [9382,16] faces; ARM 3 components [9512,8,8] faces; winding consistent, closed surfaces. Three-view CPU previews inspected; recognizable robot shape, antennae lost, fingers/details coarse, tiny isolated pieces. Not a textured/rigged production character. Fixed 512x512 encoder; changing mesh resolution does not reduce encoder memory peak. Physical Realme C55, Android JNI, battery/thermal performance not verified. R70 branch unchanged. No paid service used.
