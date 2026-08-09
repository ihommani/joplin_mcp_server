FROM python:3.13-alpine

# The distroless uv image ships a statically-linked musl binary, so it runs
# on Alpine unchanged — verified, not assumed. Pinned: an unpinned build
# tool would undo the reproducibility uv.lock is here to provide.
COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /uvx /bin/

RUN adduser -D appuser
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY server.py .

USER appuser
ENTRYPOINT ["/app/.venv/bin/python", "server.py"]
