# Use a clean Python 3.12 slim base image
FROM python:3.12-slim

# 1. Install all system dependencies in a single initial layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    wget \
    gnupg \
    zstd \
    build-essential \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Ollama CLI
RUN curl -fsSL https://ollama.com/install.sh | sh

# 3. Install 'uv' globally
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# 4. Define our app directory and home paths
WORKDIR /code
ENV HOME=/code
ENV OLLAMA_MODELS=/code/.ollama

# Setup virtual environment paths directly in the system PATH
ENV VIRTUAL_ENV=/code/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 5. Copy package configurations and run uv sync
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project --no-dev

# 6. Install Playwright system browsers
RUN playwright install --with-deps chromium

# 7. Copy your source files
COPY . .

# 8. Grant open write permissions for Hugging Face's non-root environment
RUN mkdir -p /code/sandbox /code/.ollama && chmod -R 777 /code

RUN ollama serve > /tmp/ollama.log 2>&1 & sleep 5 && ollama pull gemma4:31b-cloud

EXPOSE 7860


CMD sh -c "\
    echo 'Checking for authenticated identity...'; \
    if [ -n \"\$OLLAMA_PRIVATE_KEY\" ]; then \
        echo \"\$OLLAMA_PRIVATE_KEY\" > /code/.ollama/id_ed25519; \
        chmod 600 /code/.ollama/id_ed25519; \
        echo 'Authenticated identity key injected successfully.'; \
    fi; \
    echo 'Starting Ollama daemon...'; \
    ollama serve > /tmp/ollama.log 2>&1 & \
    sleep 5; \
    echo 'Launching AI Assistant...'; \
    python AI_Assistant.py"