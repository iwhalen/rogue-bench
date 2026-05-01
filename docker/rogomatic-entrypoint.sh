#!/bin/sh
# Docker exec entrypoint for rogomatic. Not meant to use outside docker.
#
# Invoked via `docker exec -i <container> /app/rogomatic-entrypoint.sh <args>`
# to add a second process (rogomatic) alongside the rogue process inside an
# already-running container.
cd /app/rogue
mkdir -p rlog

# Remap stdin/stdout to higher FDs for the C++ binary.
# The binary requires --trogue-fd and --frogue-fd > 0.
exec 3<&0           # stdin -> fd 3 (frogue: rogue screen from Python)
exec 4>&1           # stdout -> fd 4 (trogue: keystrokes to Python)
exec 1>&2           # remaining stdout -> stderr (keeps data stream clean)
# --optfile /dev/null: skip the bundled rogue.opt, which sets
# rogomatic_debug=false and would suppress rogomatic.log. The Rogomatic
# env values we need come from SetRogomaticValues() in the binary itself.
exec ./rogue-collection-headless --rogomatic-player --optfile /dev/null --trogue-fd 4 --frogue-fd 3 "$@"
