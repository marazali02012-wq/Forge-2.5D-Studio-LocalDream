#!/usr/bin/env bash
set -euo pipefail
mkdir -p vendor/manifold/runtime vendor/watlas vendor/kaykit/packages vendor/quaternius/packages
temp=$(mktemp -d)
trap 'rm -rf "$temp"' EXIT
curl --fail --location --retry 2 --max-time 90 -o vendor/watlas/watlas.wasm https://raw.githubusercontent.com/toji/watlas/9a8f004c1053145e97b2c489fc73a37fe48a44a7/dist/watlas.wasm
test "$(git hash-object vendor/watlas/watlas.wasm)" = 0a8a80a272d41bac2374073a35aacde884b4501e
(cd "$temp" && npm pack manifold-3d@3.5.1 --ignore-scripts --silent)
tar -xzf "$temp/manifold-3d-3.5.1.tgz" -C "$temp"
for f in manifold.js manifold.wasm manifold.d.ts manifold-encapsulated-types.d.ts manifold-global-types.d.ts LICENSE; do cp "$temp/package/$f" vendor/manifold/runtime/; done
node --input-type=module -e 'import fs from "node:fs"; for(const p of ["vendor/watlas/watlas.wasm","vendor/manifold/runtime/manifold.wasm"]){if(!WebAssembly.validate(fs.readFileSync(p))) throw Error(p+" invalid");}'
base=https://media.githubusercontent.com/media/MightyBubble/Ludots-Assets/fab331eff1cb9c552c60399ea10186ef675cd460/animations
download_zip() {
  local dest="$1" name="$2" hash="$3" size="$4"
  curl --fail --location --retry 2 --max-time 120 -o "$dest/$name" "$base/$name"
  test "$(wc -c < "$dest/$name")" -eq "$size"
  printf '%s  %s\n' "$hash" "$dest/$name" | sha256sum -c -
  unzip -tq "$dest/$name"
}
download_zip vendor/kaykit/packages KayKit-Character-Animations-Free-1.1.zip 65882f31f905ad2e953819648a59287cdeab8f623908d5ef701971d3758be20f 14858957
download_zip vendor/quaternius/packages Quaternius-Universal-Animation-Library-Standard.zip cc73fc4e495b82958207316596317a3f40b9fa38065bde1027937452da537724 15904933
download_zip vendor/quaternius/packages Quaternius-Universal-Animation-Library-2-Standard.zip 4008ea208a604773a2b2177d965f0f5d3195498b5bf838c3f5785d68e95f2a68 18735003
sha256sum vendor/manifold/runtime/* vendor/watlas/watlas.wasm vendor/kaykit/packages/*.zip vendor/quaternius/packages/*.zip > vendor/ACQUIRED_SHA256.txt
