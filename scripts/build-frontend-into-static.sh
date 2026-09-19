#!/bin/bash
# Builds the React app and copies its output into static/, so server.py
# (port 8765) serves the real app directly - no separate Vite dev server
# needed just to *use* the app. Run this after any frontend source change
# that should show up at http://localhost:8765/ - there is no watch/hot-
# reload into this path; `npm run dev` (port 5173) remains the tool for
# active frontend development.
set -euo pipefail
export PATH="/Users/rawwafa/.nvm/versions/node/v24.21.0/bin:$PATH"
cd "$(dirname "$0")/../frontend"
npm run build
cd ..
cp frontend/dist/index.html static/index.html
rm -rf static/assets
cp -r frontend/dist/assets static/assets
cp frontend/dist/favicon.svg static/favicon.svg
cp frontend/dist/icons.svg static/icons.svg
echo "Built and copied into static/. Restart server.py to pick up any backend changes too."
