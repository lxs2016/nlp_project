#!/usr/bin/env bash
# StoryWeaver Gradio app — one-click launch from project root.
# Usage: ./scripts/run_app.sh   or   bash scripts/run_app.sh
# Ensure you are in the project root so data/ and models/ paths resolve.

set -e
cd "$(dirname "$0")/.."
echo "Working directory: $(pwd)"

if ! python -c "import gradio" 2>/dev/null; then
  echo "Gradio not found. Install with: pip install -r requirements.txt"
  exit 1
fi

# Optional: port (default 7860), e.g. PORT=8080 ./scripts/run_app.sh
export PORT="${PORT:-7860}"
echo "Starting Gradio on port $PORT ..."
exec python app_gradio.py
