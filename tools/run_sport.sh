#!/usr/bin/env bash
# Update one sport. Run from that sport's folder:   ../tools/run_sport.sh hockey
#
# Reads and writes the sport's stored data in ../state/<sport> and builds its pages into
# ../dist/<sport>. RUN_MODE is "full" or "live" (a game-night run, which stops within seconds
# when none of the sport's games is on). BY_HAND=1 checks the code first.
set -uo pipefail
sport="$1"
state="../state/$sport"
mkdir -p "$state/logs"

if [ "${BY_HAND:-0}" = 1 ]; then
  echo "::group::Check the $sport code"
  if ! python tests/run_local.py; then
    echo "::endgroup::"
    echo "::error::The $sport checks failed, so $sport was not updated. Its published pages stay as they are."
    exit 1
  fi
  echo "::endgroup::"
fi

log="${RUNNER_TEMP:-/tmp}/$sport.log"
python -m pipeline.run "$state" "../dist/$sport" 2>&1 | tee "$log"
result=${PIPESTATUS[0]}
if [ "${RUN_MODE:-full}" = live ]; then
  # a game-night run keeps its log only when it found something to do
  if [ -f "../dist/$sport/index.html" ]; then cp "$log" "$state/logs/live_run.log"; fi
else
  cp "$log" "$state/logs/last_run.log"
fi
exit "$result"
