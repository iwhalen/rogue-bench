#!/bin/sh]
# Docker entrypoint. Not meant to use outside docker.
cd /app/rogue

# Remap stdin/stdout to higher FDs for the C++ binary.
# The binary requires --trogue-fd and --frogue-fd > 0.
exec 3<&0           # stdin -> fd 3 (trogue: input from Python)
exec 4>&1           # stdout -> fd 4 (frogue: output to Python)
exec 1>&2           # remaining stdout -> stderr (keeps data stream clean)
exec ./rogue-collection-headless "$@" --pipe-io --trogue-fd 3 --frogue-fd 4
