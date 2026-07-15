#!/bin/sh
# Force-regenerate every PlantUML diagram in this folder to a PNG right here (next
# to its .puml source), then merge each before/after pair into one side-by-side
# image one level up, next to the folder README
# (`<skill>-before.png` + `<skill>-after.png` -> `../<skill>.png`). Only the merged
# composites live beside the README; the per-side renders stay in this folder.
# Unlike the .githooks/pre-commit hook (which only re-renders stale diagrams),
# this rebuilds all of them unconditionally — handy after a theme change or when
# you just want a clean sweep.
#
# Usage:  docs/comparison-to-teamscale-claude-code/diagrams/regenerate.sh
# (runnable from anywhere; it cd's to its own directory first).

set -e

if ! command -v plantuml >/dev/null 2>&1; then
    echo "regenerate: plantuml not found; install it to render the diagrams" >&2
    exit 1
fi

# Work relative to this script's own folder so it can be invoked from anywhere.
cd "$(dirname "$0")"

for puml in *.puml; do
    # Skip any include-only file (no @startuml diagram of its own); the shared
    # theme now lives in ../../theme.iuml, so this normally matches every .puml
    # here. Anchor the match so a mention of @startuml in a comment doesn't count.
    grep -qE '^[[:space:]]*@startuml' "$puml" || continue

    echo "regenerate: rendering $puml -> $(basename "$puml" .puml).png" >&2
    plantuml -tpng -o . "$puml"
done

# Merge each before/after pair into one side-by-side image one level up, next to
# the README. The two renders differ in height, so align them at the top
# (-gravity north) and separate them with a white gap (+smush). Exclude the PNG
# date/time chunks so the output is byte-stable across runs (no needless churn).
# Needs ImageMagick.
if command -v magick >/dev/null 2>&1; then
    for before in *-before.png; do
        [ -f "$before" ] || continue
        base=$(basename "$before" -before.png)
        after="$base-after.png"
        [ -f "$after" ] || continue

        echo "regenerate: merging $base-{before,after}.png -> ../$base.png" >&2
        magick "$before" "$after" -background white -gravity north +smush 30 \
            -define png:exclude-chunk=date,time "../$base.png"
    done
else
    echo "regenerate: magick (ImageMagick) not found; skipping side-by-side merge" >&2
fi

echo "regenerate: done" >&2
