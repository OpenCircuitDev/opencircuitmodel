#!/usr/bin/env bash
#
# smoke-test-daemon.sh
# --------------------
# Exercises a running OCM daemon's user-facing surfaces. Used as the v1
# pre-release blocker named in spec v0.6 build status: cross-platform
# verification before tagging v0.1.0.
#
# Run from repo root:
#   bash scripts/smoke-test-daemon.sh
#
# Assumes:
#   - OCM daemon is running and bound to 127.0.0.1:7300 (or set OCM_API_URL)
#   - Mem0 server is running at 127.0.0.1:8765 (or daemon will warn — that's
#     fine for the smoke test; we don't fail on it)
#   - An inference backend is reachable (llama-server / vLLM); the chat
#     endpoint returns 502 if not, which we DO fail on
#
# Optional env vars:
#   - OCM_API_URL       (default: http://127.0.0.1:7300)
#   - OCM_SMOKE_MODEL   (default: ocm-default — matches /v1/models response)
#   - OCM_SKIP_CHAT=1   skip the chat-completion check (useful when no
#                       backend is up but you still want to verify the
#                       HTTP surface itself)

set -euo pipefail

API_URL="${OCM_API_URL:-http://127.0.0.1:7300}"
MODEL="${OCM_SMOKE_MODEL:-ocm-default}"

PASS=0
FAIL=0
WARN=0

check() {
	local label="$1"
	local exit_code="$2"
	local detail="${3:-}"
	if [[ "$exit_code" -eq 0 ]]; then
		printf "[PASS] %s\n" "$label"
		PASS=$((PASS + 1))
	else
		printf "[FAIL] %s — %s\n" "$label" "$detail"
		FAIL=$((FAIL + 1))
	fi
}

warn() {
	local label="$1"
	local detail="${2:-}"
	printf "[WARN] %s — %s\n" "$label" "$detail"
	WARN=$((WARN + 1))
}

require() {
	command -v "$1" >/dev/null 2>&1 || {
		echo "error: $1 is required" >&2
		exit 2
	}
}
require curl
require jq

echo "Smoke-testing OCM daemon at $API_URL"
echo

# ----------- Check 1: /v1/models returns a non-empty array
resp=$(curl --silent --fail-with-body "$API_URL/v1/models" 2>&1) && rc=0 || rc=$?
if [[ "$rc" -eq 0 ]]; then
	model_count=$(echo "$resp" | jq -r '.data | length')
	if [[ "$model_count" -gt 0 ]]; then
		check "/v1/models returns >=1 model" 0
	else
		check "/v1/models returns >=1 model" 1 "got 0 models"
	fi
else
	check "/v1/models reachable" 1 "curl rc=$rc body=$resp"
fi

# ----------- Check 2: /v1/registry/models returns the curated registry
resp=$(curl --silent --fail-with-body "$API_URL/v1/registry/models" 2>&1) && rc=0 || rc=$?
if [[ "$rc" -eq 0 ]]; then
	registry_count=$(echo "$resp" | jq -r '.models | length')
	if [[ "$registry_count" -gt 0 ]]; then
		check "/v1/registry/models returns curated entries" 0
	else
		check "/v1/registry/models returns curated entries" 1 "got 0 entries"
	fi
else
	check "/v1/registry/models reachable" 1 "curl rc=$rc body=$resp"
fi

# ----------- Check 3: localhost auth middleware blocks non-loopback hits
# (skipped — would require binding to non-loopback or spoofing X-Forwarded-For,
# both out of scope for a smoke test on a single host. Auth path is verified
# by the unit tests in crates/ocm-api/src/auth.rs)

# ----------- Check 4: chat completion (non-streaming)
if [[ "${OCM_SKIP_CHAT:-0}" == "1" ]]; then
	warn "/v1/chat/completions skipped" "OCM_SKIP_CHAT=1 set"
else
	body=$(jq -nc \
		--arg model "$MODEL" \
		'{model: $model, messages: [{role: "user", content: "Say hello in one word."}], stream: false, max_tokens: 16}')
	resp=$(curl --silent --fail-with-body \
		--max-time 30 \
		-H "Content-Type: application/json" \
		-d "$body" \
		"$API_URL/v1/chat/completions" 2>&1) && rc=0 || rc=$?
	if [[ "$rc" -eq 0 ]]; then
		content=$(echo "$resp" | jq -r '.choices[0].message.content // empty')
		if [[ -n "$content" ]]; then
			check "/v1/chat/completions returns non-empty content" 0
		else
			check "/v1/chat/completions returns non-empty content" 1 "content was empty"
		fi
	else
		# 502 typically = inference backend unreachable. Document but fail.
		check "/v1/chat/completions reachable" 1 "curl rc=$rc — likely backend unreachable"
	fi
fi

# ----------- Check 5: chat completion (streaming SSE)
if [[ "${OCM_SKIP_CHAT:-0}" == "1" ]]; then
	warn "/v1/chat/completions stream skipped" "OCM_SKIP_CHAT=1 set"
else
	body=$(jq -nc \
		--arg model "$MODEL" \
		'{model: $model, messages: [{role: "user", content: "Count: one, two."}], stream: true, max_tokens: 24}')
	stream_output=$(curl --silent --fail-with-body \
		--max-time 30 \
		-H "Content-Type: application/json" \
		-H "Accept: text/event-stream" \
		-d "$body" \
		"$API_URL/v1/chat/completions" 2>&1) && rc=0 || rc=$?
	if [[ "$rc" -eq 0 ]]; then
		if echo "$stream_output" | grep -q "^data:"; then
			check "/v1/chat/completions SSE emits data: frames" 0
		else
			check "/v1/chat/completions SSE emits data: frames" 1 "no data: lines in response"
		fi
	else
		check "/v1/chat/completions stream reachable" 1 "curl rc=$rc"
	fi
fi

# ----------- Summary
echo
echo "===== smoke test summary ====="
printf "PASS: %d\n" "$PASS"
printf "WARN: %d\n" "$WARN"
printf "FAIL: %d\n" "$FAIL"

if [[ "$FAIL" -gt 0 ]]; then
	exit 1
fi
exit 0
