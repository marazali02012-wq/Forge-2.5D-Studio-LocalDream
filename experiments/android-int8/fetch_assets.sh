#!/usr/bin/env bash
set -euo pipefail
BASE=https://huggingface.co/alegauss/modelado-models/resolve/e2a71ca284483bcfd16426ae830cfbd1dfeb16c4
DIR="${1:-android-probe-data}"
mkdir -p "$DIR/models"
get(){ local name="$1" hash="$2"; local target="$DIR/models/$name"; curl --fail --location --retry 2 --max-time 120 -o "$target" "$BASE/$name"; printf '%s  %s\n' "$hash" "$target" | sha256sum -c -; }
get triposr-decoder-fp32.onnx 1604a0dc1903eee485d5a388dd2b4bcac8fad484a96010a797d7c1f40583d985
get triposr-decoder-meta.json 4a318ad9c4ae0ca3b7b4c35f405c34ae3ac2e683191812de538ceadcb9261158
curl --fail --location --retry 2 -o "$DIR/robot.png" https://raw.githubusercontent.com/VAST-AI-Research/TripoSR/main/examples/robot.png
test "$(git hash-object "$DIR/robot.png")" = 31ce9687b54dddf2907a39f25b09d62bcbf2a8b0
if [[ "${2:-}" == "full" ]]; then
  get triposr-encoder-int8.onnx 8a94284bc2c914323e17774a247e47de0dd5b3a6843d026c68b2765c68a67cbd
  test "$(wc -c < "$DIR/models/triposr-encoder-int8.onnx")" -eq 433359857
fi
