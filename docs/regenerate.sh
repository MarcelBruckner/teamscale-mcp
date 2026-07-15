#!/bin/sh
# Force-regenerate every PlantUML diagram under docs/ (recursively) to a PNG in
# place next to its .puml source, then merge each before/after pair into one
# side-by-side composite (`<name>-before.png` + `<name>-after.png` -> `<name>.png`,
# written one level up when the pair lives in a `diagrams/` subfolder, next to the
# folder README; otherwise in place).
#
# This is the whole-repo counterpart to .githooks/pre-commit: the hook only
# re-renders *stale* diagrams (so a commit always carries a matching PNG), while
# this rebuilds *all* of them unconditionally — handy after a theme change or when
# you just want a clean sweep. It does not touch Marp deck PDFs (see
# docs/presentation/build-pdf.sh for those).
#
# Usage:  docs/regenerate.sh
# (runnable from anywhere; it cd's to the repo root first.)

set -e

if ! command -v plantuml >/dev/null 2>&1; then
    echo "regenerate: plantuml not found; install it to render the diagrams" >&2
    exit 1
fi

# Work from the repo root (this script's parent dir) so the docs/ paths below and
# the -o . in-place renders line up regardless of where it was invoked from.
cd "$(dirname "$0")/.."

# Repo paths under docs/ contain no spaces, so word-splitting the find output is
# fine. Render each diagram's PNG in place, next to its .puml source.
for puml in $(find docs -type f -name '*.puml'); do
    # Skip include-only theme files (theme.iuml) that have
    # no @startuml diagram of their own. Anchor the match so a mention of @startuml
    # in a comment doesn't count.
    grep -qE '^[[:space:]]*@startuml' "$puml" || continue

    dir=$(dirname "$puml")
    echo "regenerate: rendering $puml -> $dir/$(basename "$puml" .puml).png" >&2
    plantuml -tpng -o . "$puml" || {
        echo "regenerate: failed to render $puml" >&2
        exit 1
    }
done

# Merge each before/after pair into one side-by-side composite. The two renders
# differ in height, so align them at the top (-gravity north) and separate them
# with a white gap (+smush). Exclude the PNG date/time chunks so the output is
# byte-stable across runs (no needless churn). A pair inside a `diagrams/` subfolder
# writes its composite one level up (next to the README); otherwise in place. Needs
# ImageMagick; skipped (not fatal) when absent, matching the pre-commit hook.
if command -v magick >/dev/null 2>&1; then
    for before in $(find docs -type f -name '*-before.png'); do
        after="${before%-before.png}-after.png"
        [ -f "$after" ] || continue

        bdir=$(dirname "$before")
        name=$(basename "${before%-before.png}")
        if [ "$(basename "$bdir")" = "diagrams" ]; then
            merged="$(dirname "$bdir")/$name.png"    # one level up, next to the README
        else
            merged="$bdir/$name.png"
        fi

        echo "regenerate: merging $before + $after -> $merged" >&2
        magick "$before" "$after" -background white -gravity north +smush 30 \
            -define png:exclude-chunk=date,time "$merged" || {
            echo "regenerate: failed to merge $merged" >&2
            exit 1
        }
    done
else
    echo "regenerate: magick (ImageMagick) not found; skipping before/after merge" >&2
fi

echo "regenerate: done" >&2
