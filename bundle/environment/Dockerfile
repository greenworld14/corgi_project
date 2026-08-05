FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        less \
        procps \
        vim-tiny \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://claude.ai/install.sh | bash

# The deliverable is a URL parser; a JS runtime ships a conformant one, so the
# image must not contain one. This assertion fails the build if a base-image or
# package change ever drags a JS runtime back in.
RUN for b in node nodejs deno bun; do \
        if command -v "$b" >/dev/null 2>&1; then \
            echo "FATAL: '$b' is present in the image" >&2; \
            exit 1; \
        fi; \
    done

WORKDIR /app

COPY urlp /app/urlp
COPY cases /app/cases
COPY docs /app/docs
COPY check.py /app/check.py

# --- task timer (append at the end of environment/Dockerfile) ---
# COPY only — never auto-start it from the image (no ENV BASH_ENV, no shell
# profile hooks). The platform arms /app/timer.sh in the task sandbox with the
# real TASK_BUDGET_SECS. An image-side autostart also fires inside the image
# BUILD container and stalls the build until the timer's budget expires.
COPY timer.sh /app/timer.sh
RUN chmod +x /app/timer.sh && mkdir -p /app/.timer
