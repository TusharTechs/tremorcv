#!/usr/bin/env bash
# Regenerate docs/architecture.svg from docs/architecture.mmd.
#
# The README and report embed the rendered SVG rather than a ```mermaid fence:
# GitHub renders Mermaid in a sandboxed iframe from viewscreen.githubusercontent.com,
# which costs a visible delay on every page load and scales the diagram to fill the
# container width (scaling a tall diagram UP). A static SVG loads instantly, renders
# everywhere, and is exactly the size we chose.
set -euo pipefail
command -v npx >/dev/null || { echo "needs npx (Node.js)"; exit 1; }
npx --yes @mermaid-js/mermaid-cli \
  -i docs/architecture.mmd -o docs/architecture.svg \
  -b transparent -w 1339
echo "wrote docs/architecture.svg"
