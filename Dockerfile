FROM ubuntu:24.04 AS builder
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY rogue-collection/ ./rogue-collection/
RUN make -C rogue-collection headless

FROM ubuntu:24.04
WORKDIR /app/rogue
COPY --from=builder /src/rogue-collection/build/release/rogue-collection-headless ./
COPY --from=builder /src/rogue-collection/build/release/*.so ./
COPY --from=builder /src/rogue-collection/rogue.opt ./
COPY docker/entrypoint.sh /app/entrypoint.sh
COPY docker/rogomatic-entrypoint.sh /app/rogomatic-entrypoint.sh
RUN chmod +x /app/entrypoint.sh /app/rogomatic-entrypoint.sh
ENV LD_LIBRARY_PATH=/app/rogue
ENTRYPOINT ["/app/entrypoint.sh"]
