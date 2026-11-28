// Khronos glTF-Validator for one or more GLB files; prints one JSON line each.
// Usage: node khronos_check.mjs a.glb [b.glb ...]  (exit 1 on any error/warning)
import fs from 'node:fs';
import validator from 'gltf-validator';

let failed = false;
for (const file of process.argv.slice(2)) {
  const {issues, info} = await validator.validateBytes(new Uint8Array(fs.readFileSync(file)));
  const row = {file, errors: issues.numErrors, warnings: issues.numWarnings,
    infos: issues.numInfos, triangles: info?.totalTriangleCount, vertices: info?.totalVertexCount};
  failed ||= issues.numErrors > 0 || issues.numWarnings > 0;
  console.log(JSON.stringify(row));
}
process.exit(failed ? 1 : 0);
