#!/bin/sh
# Builds the Marcs Film Emulator plug-ins for PhotoCraft and runs the checks in harness/.
#
#   ./build.sh             build the plug-in from the data in lut/, then test it
#   ./build.sh --data      re-digitize the datasheets and re-run the film simulation first
#                          (python3 with numpy, scipy, pymupdf)
#   ./build.sh --test IMG  then run every film in the test host on IMG
#
# Needs Rust with the wasm32-unknown-unknown target: rustup target add wasm32-unknown-unknown
set -eu
cd "$(dirname "$0")"

if [ "${1:-}" = "--data" ]; then
  python3 data/tools/film_data.py        # datasheet PDFs -> data/films/*.json
  python3 model/film_model_v2.py         # film simulation -> lut/<film>.lut per push level (u16)
  python3 model/make_tables.py           # decode tables (tables.bin), Adobe RGB tables, grain texture
fi

(cd plugin && cargo build --release --target wasm32-unknown-unknown)
mkdir -p dist
cp plugin/target/wasm32-unknown-unknown/release/emulsion_film.wasm dist/marcs-film-emulator.wasm
ls -l dist/*.wasm

(cd harness && cargo test --release --quiet)

if [ "${1:-}" = "--test" ]; then
  (cd harness && cargo build --release)
  for film in "Portrait 400" "Portrait 800" "Everyday 200" "Street 400" "Vivid 100" "Cine 500T" "Cine 250D" "Mono 400" "Mono 100"; do
    out="dist/test-$(echo "$film" | tr ' ' '-').png"
    harness/target/release/emulsion-harness dist/marcs-film-emulator.wasm "$2" "$out" "{\"film\":\"$film\"}"
  done
fi
