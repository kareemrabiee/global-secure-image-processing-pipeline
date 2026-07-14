#!/usr/bin/env bash
# Builds a Lambda Layer zip containing Pillow, matching the Lambda's
# runtime (python3.12) and architecture (x86_64), so we avoid the v1
# "Runtime/Layer version mismatch" bug documented in docs/lessons-learned.md.
#
# Usage: ./build_lambda_layer.sh
# Output: ../build/pillow_layer.zip  (upload this as the Lambda layer for ImageProcessor)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/../build"
LAYER_DIR="$BUILD_DIR/layer/python"

rm -rf "$LAYER_DIR"
mkdir -p "$LAYER_DIR"

echo "Installing Pillow for manylinux (Lambda-compatible)..."
pip install pillow \
    --platform manylinux2014_x86_64 \
    --target "$LAYER_DIR" \
    --python-version 3.12 \
    --only-binary=:all: \
    --break-system-packages 2>/dev/null || \
pip install pillow \
    --platform manylinux2014_x86_64 \
    --target "$LAYER_DIR" \
    --python-version 3.12 \
    --only-binary=:all:

cd "$BUILD_DIR/layer"
zip -r9 "$BUILD_DIR/pillow_layer.zip" python > /dev/null

echo "Layer built: $BUILD_DIR/pillow_layer.zip"
