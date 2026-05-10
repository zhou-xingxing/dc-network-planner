#!/bin/bash
# Start the DC Network Planner frontend dev server
cd "$(dirname "$0")"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    npm install
fi

npm run dev
