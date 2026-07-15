#!/usr/bin/env bash
#
# Render the Marp deck(s) in this folder to PDF. Marp drives a headless Chrome to
# rasterize the slides, and `--allow-local-files` inlines the embedded diagram /
# screenshot PNGs. Pass one or more markdown files to render just those; with no
# args it renders every *.md in this folder.
#
#   ./build-pdf.sh                        # all decks here
#   ./build-pdf.sh teamscale-mcp-and-docs.md
set -euo pipefail
PRESENTATION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PRESENTATION_DIR"

command -v marp >/dev/null || { echo "marp not found; install with 'brew install marp-cli'" >&2; exit 1; }

# Marp needs a Chrome/Chromium to render PDF. Respect an existing CHROME_PATH,
# otherwise pick the first browser we can find.
if [[ -z "${CHROME_PATH:-}" ]]; then
  for candidate in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Chromium.app/Contents/MacOS/Chromium" \
    "$(command -v google-chrome || true)" \
    "$(command -v chromium || true)"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      CHROME_PATH="$candidate"
      break
    fi
  done
fi
[[ -n "${CHROME_PATH:-}" ]] || { echo "No Chrome/Chromium found; set CHROME_PATH to a browser binary" >&2; exit 1; }
export CHROME_PATH

decks=("$@")
if [[ ${#decks[@]} -eq 0 ]]; then
  decks=(*.md)
fi

for deck in "${decks[@]}"; do
  echo "Rendering $deck -> ${deck%.md}.pdf"
  marp --pdf --allow-local-files "$deck"
done
