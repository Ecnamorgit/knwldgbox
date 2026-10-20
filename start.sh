#!/bin/bash

echo "🚀 Starting KNWLDGBox..."

# Cleanup function to kill all background processes when the script stops (Ctrl+C)
cleanup() {
    echo -e "\n🛑 Stopping servers..."
    kill $(jobs -p) 2>/dev/null
    exit
}

# Trap SIGINT (Ctrl+C) and SIGTERM and call the cleanup function
trap cleanup SIGINT SIGTERM

# Activate a virtualenv if one is present. Supports both Linux/macOS (bin/)
# and Windows + Git Bash (Scripts/); falls back to the system Python.
activate_venv() {
    for a in knwldg/bin/activate knwldg/Scripts/activate \
             venv/bin/activate venv/Scripts/activate \
             .venv/bin/activate .venv/Scripts/activate; do
        if [ -f "$a" ]; then
            # shellcheck disable=SC1090
            source "$a"
            echo "🐍 Virtualenv: $a"
            return
        fi
    done
    echo "🐍 No virtualenv found — using system Python."
}

# Pick a Python launcher (python, else python3)
PY=python
command -v python >/dev/null 2>&1 || PY=python3

activate_venv

# Start the Backend (FastAPI). `python -m uvicorn` works even when the
# uvicorn script isn't on PATH (common on Windows).
echo "📡 Starting Backend (FastAPI) on http://127.0.0.1:8000 ..."
( cd backend && "$PY" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000 ) &

# Start the Frontend
echo "💻 Starting Frontend (Vue/Vite) on http://localhost:5173 ..."
cd app && npm run dev
