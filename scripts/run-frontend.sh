#!/bin/bash
export PATH="/Users/rawwafa/.nvm/versions/node/v24.21.0/bin:$PATH"
cd "$(dirname "$0")/../frontend"
exec npm run dev
