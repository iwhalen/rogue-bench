FROM ubuntu:24.04 AS builder
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY rogue-collection/ ./rogue-collection/
RUN make -C rogue-collection headless

FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock .python-version README.md ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev

COPY --from=builder /src/rogue-collection/build/release/ ./rogue/
COPY --from=builder /src/rogue-collection/rogue.opt ./rogue/

ENTRYPOINT ["uv", "run", "rogue-bench", "--rogue-path", "/app/rogue/rogue-collection-headless"]
