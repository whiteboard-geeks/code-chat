# syntax=docker/dockerfile:1.7
#
# code-chat: forked CloudCLI deployed at app.whiteboardgeeks.com/code-chat
#
# Single-stage image. The agent (Claude Code) runs as subprocesses inside this
# container, so we install the CLIs it needs to debug MailerAutomation:
# gh (GitHub PRs), heroku (logs/config/restart), temporal (workflows).
#
# Secrets are pulled from Infisical at startup by deploy/entrypoint.py, which
# requires INFISICAL_CLIENT_ID and INFISICAL_CLIENT_SECRET to be passed in via
# `docker run -e ...` (the bootstrap creds for a machine identity).

FROM node:20-bookworm-slim

# System tools the agent + entrypoint need
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        gnupg \
        python3 \
        python3-requests \
        sudo \
    && rm -rf /var/lib/apt/lists/*

# GitHub CLI (gh) — official apt repo
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        > /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Heroku CLI — official install script
RUN curl https://cli-assets.heroku.com/install-ubuntu.sh | sh

# Temporal CLI — official install script (drops binary in /root/.temporalio/bin)
RUN curl -sSf https://temporal.download/cli.sh | sh \
    && cp /root/.temporalio/bin/temporal /usr/local/bin/temporal \
    && rm -rf /root/.temporalio

WORKDIR /app

# Install dependencies first (best for layer caching)
COPY package.json package-lock.json ./
RUN npm ci

# Source for the build
COPY . .

# Build with subpath base so assets and runtime URLs are prefixed with /code-chat/
ENV VITE_BASE_URL=/code-chat/
RUN npm run build

# Non-root user. Keep uid=1001 to match common host user mappings.
RUN useradd -m -u 1001 -s /bin/bash app \
    && chown -R app:app /app

# Persistent state lives on volumes mounted by the host
RUN mkdir -p /data /repos /home/app/.claude \
    && chown -R app:app /data /repos /home/app/.claude
VOLUME ["/data", "/repos", "/home/app/.claude"]

# Default DB path inside the data volume
ENV DATABASE_PATH=/data/auth.db

# Single-tenant identity for internal team — see deploy/README.md
ENV IS_PLATFORM=true
ENV VITE_IS_PLATFORM=true

# Server listens on this port; Caddy on the host reverse_proxies to it
ENV SERVER_PORT=3001
ENV HOST=0.0.0.0
EXPOSE 3001

USER app

# Entrypoint pulls secrets from Infisical, configures CLI auths, then exec's the CMD
COPY --chown=app:app deploy/entrypoint.py /usr/local/bin/code-chat-entrypoint
ENTRYPOINT ["python3", "/usr/local/bin/code-chat-entrypoint"]
CMD ["npm", "run", "server"]
