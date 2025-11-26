#!/usr/bin/env bash
# Start a single, range-capable HTTP server for the IGV report.
# Behavior:
#  - kills any process currently listening on the requested port (default 8000)
#  - prefers to run scripts/serve_range.py; falls back to scripts/range_http_server.py if missing
#  - writes logs to data/output/logs/igv_server.log and prints the new PID
# Usage:
#   ./scripts/start_igv_server.sh [PORT] [ROOT]
# Example:
#   ./scripts/start_igv_server.sh 8000 data/output

set -euo pipefail
PORT=${1:-8000}
ROOT=${2:-data/output}
PYTHON=${PYTHON:-python3}

# Find any process listening on the requested TCP port and kill it (if user permits)
PID="$(lsof -t -iTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "${PID}" ]; then
  echo "Found process(es) listening on port ${PORT}: ${PID}"
  echo "Stopping..."
  # Try graceful first
  kill ${PID} || true
  sleep 1
  # Force kill if still present
  PID2="$(lsof -t -iTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "${PID2}" ]; then
    echo "Force killing: ${PID2}"
    sudo kill -9 ${PID2} || true
    sleep 0.5
  fi
else
  echo "No process listening on port ${PORT}"
fi

# Choose which range-capable server script to use
if [ -x "$(pwd)/scripts/serve_range.py" ] || [ -f "$(pwd)/scripts/serve_range.py" ]; then
  SERVER_SCRIPT="$(pwd)/scripts/serve_range.py"
elif [ -x "$(pwd)/scripts/range_http_server.py" ] || [ -f "$(pwd)/scripts/range_http_server.py" ]; then
  SERVER_SCRIPT="$(pwd)/scripts/range_http_server.py"
else
  echo "ERROR: No range-capable server script found. Expected scripts/serve_range.py or scripts/range_http_server.py"
  exit 1
fi

mkdir -p "${ROOT}/logs"
LOGFILE="${ROOT}/logs/igv_server.log"

echo "Starting range-capable server using ${SERVER_SCRIPT}"
# Build args compatible with the chosen server script
if [[ "${SERVER_SCRIPT}" == *"serve_range.py" ]]; then
  SRV_ARGS=(--root "${ROOT}" --port "${PORT}")
else
  # range_http_server.py expects --dir, --port, --host
  SRV_ARGS=(--dir "${ROOT}" --port "${PORT}")
fi

# Start the server in background with nohup. The server will bind to 127.0.0.1 by default.
nohup ${PYTHON} "${SERVER_SCRIPT}" "${SRV_ARGS[@]}" >"${LOGFILE}" 2>&1 &
NEWPID=$!
sleep 0.2
if ps -p ${NEWPID} >/dev/null 2>&1; then
  echo "Server started (PID ${NEWPID}). Log: ${LOGFILE}"
else
  echo "Server did not start successfully. Check log: ${LOGFILE}"
  tail -n +1 "${LOGFILE}" || true
  exit 1
fi

echo "Quick test:"
# HEAD request
curl -I --http1.1 "http://127.0.0.1:${PORT}/igv_report.html" || true
# small range request (first 1 byte)
curl -v --http1.1 -r 0-0 "http://127.0.0.1:${PORT}/assembly/" -o /dev/null || true

echo "Done. If your browser still reports 'status: 0' for BAM fetches, restart your browser or try a hard refresh (Cmd+Shift+R)."
