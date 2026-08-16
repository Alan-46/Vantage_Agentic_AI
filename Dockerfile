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

# 8. HF Spaces runs the container as a non-root UID. Only the directories
# that actually need runtime writes get opened up - not the whole /code tree
# (which includes your source files and have no reason to be writable).
RUN mkdir -p /code/sandbox /code/.ollama && \
    chmod -R 775 /code/sandbox /code/.ollama && \
    chown -R 1000:1000 /code

EXPOSE 7860

# entrypoint.sh handles runtime startup: launching the daemon, waiting for it
# to be ready, and only then starting the app. OLLAMA_API_KEY is picked up
# automatically from the environment by the ollama CLI/daemon - no file
# injection needed.
COPY entrypoint.sh /code/entrypoint.sh
RUN chmod +x /code/entrypoint.sh

CMD ["/code/entrypoint.sh"]