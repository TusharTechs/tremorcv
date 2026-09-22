#!/usr/bin/env bash
# Regenerate both diagrams from their .mmd sources.
#
# The README and report embed rendered SVGs rather than ```mermaid fences: GitHub
# renders Mermaid in a sandboxed iframe from viewscreen.githubusercontent.com, which
# costs a visible delay on every page load and scales the diagram to the container
# width (scaling a tall diagram UP). A static SVG loads instantly and is the size we
# chose. htmlLabels:false keeps the text as real SVG, because foreignObject does not
# render when the SVG is referenced from an <img>.
set -euo pipefail
command -v npx >/dev/null || { echo "needs npx (Node.js)"; exit 1; }

# mermaid-cli drives Chrome through puppeteer. Point it at a Chrome that already
# exists rather than letting it download another one, and so that a half finished
# download (a full disk will do it) does not leave an unrunnable binary behind.
for c in "${PUPPETEER_EXECUTABLE_PATH:-}" \
         "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
         "$(command -v google-chrome || true)" \
         "$(command -v chromium || true)"; do
  [ -n "$c" ] && [ -x "$c" ] && export PUPPETEER_EXECUTABLE_PATH="$c" && break
done
npx --yes @mermaid-js/mermaid-cli -i docs/architecture.mmd \
  -o docs/architecture.svg -b transparent -w 1339
npx --yes @mermaid-js/mermaid-cli -i docs/agent-workflow.mmd \
  -o docs/agent-workflow.svg -b transparent -w 1339
echo "wrote docs/architecture.svg and docs/agent-workflow.svg"
