# Credential-free tracing layer over the exact tested M4 image.
# It does not change the production runner image or container security policy.
# Verify the local tag resolves to this ID before building:
# sha256:5cb0fed98f68ac5284b129c6090cd1c75d17f09583f2cb5789d25a6e2d4e3121
FROM agentic-runner-m4:local
USER 0
RUN apt-get update \
    && apt-get install -y --no-install-recommends strace \
    && rm -rf /var/lib/apt/lists/*
USER 65534:65534
LABEL org.agentic-runner.diagnostics="m4-namespace-v1"
