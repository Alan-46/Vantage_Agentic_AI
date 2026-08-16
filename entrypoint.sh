#!/bin/sh
set -e

# Inject the Ollama signin identity (Ed25519 keypair) before starting the
# daemon. This is what the local `ollama serve` process uses to authenticate
# its proxy calls to ollama.com for :cloud models - NOT OLLAMA_API_KEY,
# which only applies to direct HTTP calls to ollama.com/api that bypass the
# local daemon entirely.

if [ -n "$OLLAMA_PRIVATE_KEY" ]; then
    echo "Injecting Ollama signin identity..."
    echo "$OLLAMA_PRIVATE_KEY" > /code/.ollama/id_ed25519
    chmod 600 /code/.ollama/id_ed25519
else
    echo "WARNING: OLLAMA_PRIVATE_KEY is not set. Cloud model calls will fail with 401."
fi

echo "Starting Ollama daemon..."
ollama serve > /tmp/ollama.log 2>&1 &

# Poll until the daemon is actually answering, instead of a blind sleep.
# Fail fast and loud if it never comes up.
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

echo "Launching AI Assistant..."
exec python AI_Assistant.py