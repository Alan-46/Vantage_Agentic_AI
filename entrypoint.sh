#!/bin/sh
set -e

echo "Starting Ollama daemon..."
ollama serve > /tmp/ollama.log 2>&1 &
OLLAMA_PID=$!

# Poll until the daemon is actually answering, instead of a blind sleep.
# Fail fast and loud if it never comes up, instead of limping into the
# app and producing a confusing downstream error later.
echo "Waiting for Ollama daemon to be ready..."
for i in $(seq 1 30); do
    if curl -s -o /dev/null http://localhost:11434/api/tags; then
        echo "Ollama daemon is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Ollama daemon did not become ready in time. Last log lines:"
        tail -n 40 /tmp/ollama.log
        exit 1
    fi
    sleep 1
done

if [ -z "$OLLAMA_API_KEY" ]; then
    echo "WARNING: OLLAMA_API_KEY is not set. Cloud model calls will fail."
fi

echo "Launching AI Assistant..."
exec python AI_Assistant.py
