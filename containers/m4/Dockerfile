# Runner-owned build context only. Never build a project's Dockerfile as setup.
FROM node:22-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da AS node
FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && apt-get update \
    && apt-get install -y --no-install-recommends bubblewrap chromium git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir setuptools==80.9.0 wheel==0.45.1 \
    && mkdir -p /workspace /run/runner /home/runner \
    && chmod 0755 /home/runner
COPY codex /usr/local/bin/codex
LABEL org.agentic-runner.environment="m4-v1"
ENV PATH="/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin" HOME="/home/runner" CODEX_HOME="/home/runner/.codex"
WORKDIR /workspace
# The trusted launcher supplies the checkout owner's numeric UID/GID.
USER 65534:65534
