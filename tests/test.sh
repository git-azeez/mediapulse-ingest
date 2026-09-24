#!/usr/bin/env bash
set -Eeuo pipefail

mkdir -p /logs/verifier

has_valid_reward() {
  [[ -s /logs/verifier/reward.json ]] \
    && jq -e '
      (.reward | type) == "number"
      and (.score | type) == "number"
      and .reward >= 0
      and .reward <= 1
    ' /logs/verifier/reward.json >/dev/null 2>&1
}

ensure_invalid_result() {
  local rc="$1"
  local line="$2"
  if (( rc != 0 )) && ! has_valid_reward; then
    if [[ ! -s /logs/verifier/invalid.json ]]; then
      printf '{"trial_valid":false,"error":"separate verifier exited before producing a valid result","exit_code":%s,"line":%s}\n' \
        "$rc" "$line" >/logs/verifier/report.json
      printf '{"trial_valid":false,"exit_code":%s,"line":%s}\n' "$rc" "$line" >/logs/verifier/invalid.json
    fi
    printf '{"reward":0,"score":0}\n' >/logs/verifier/reward.json
    printf '0\n' >/logs/verifier/reward.txt
  fi
}
trap 'rc=$?; ensure_invalid_result "$rc" "$LINENO"' EXIT

rm -rf /logs/verifier/reward.txt /logs/verifier/reward.json \
  /logs/verifier/report.json /logs/verifier/summary.json /logs/verifier/invalid.json

export PYTHONPATH="/tests${PYTHONPATH:+:$PYTHONPATH}"
export PATH="/opt/venv/bin:${PATH:-/usr/local/bin:/usr/bin:/bin}"

: "${MEDIAPULSE_SUBMISSION_DIR:?MEDIAPULSE_SUBMISSION_DIR is required}"
printf 'MediaPulse verifier: starting pytest oracle\n'

set +e
python3 -m pytest \
  -p no:cacheprovider \
  --tb=short \
  -rA \
  /tests/suite/test_declared.py \
  /tests/suite/test_live.py \
  /tests/suite/test_behavior.py \
  /tests/suite/test_lifecycle.py
pytest_rc=$?
set -e

if [[ -s /logs/verifier/invalid.json ]]; then
  exit 2
fi
if has_valid_reward; then
  exit 0
fi
if (( pytest_rc != 0 )); then
  exit "$pytest_rc"
fi
exit 3
