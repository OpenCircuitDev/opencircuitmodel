#!/usr/bin/env bash
#
# populate-registry-hashes.sh
# ---------------------------
# Downloads each model in crates/ocm-models/registry.json from its canonical
# HuggingFace mirror, computes SHA256, and prints a patched registry.json.
# DOES NOT modify the registry in place — review the diff manually, then
# commit. This pre-release blocker is documented in spec v0.6 build status.
#
# Run from repo root:
#   bash scripts/populate-registry-hashes.sh
#
# Bandwidth: ~30 GB total across the 5 default models. Runs once per release.
# Disk: temporary download dir is wiped at exit unless OCM_KEEP_DOWNLOADS=1.
#
# Requirements:
#   - bash 4+
#   - jq (sudo apt install jq / brew install jq / scoop install jq)
#   - curl
#   - sha256sum (Linux/Mac) or shasum -a 256 (Mac fallback)
#
# Optional:
#   - HF_TOKEN env var if any model is gated (none of the v1 set is, as of
#     2026-05-09 — this is forward-compat).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY="$REPO_ROOT/crates/ocm-models/registry.json"
TMPDIR="${OCM_HASH_TMPDIR:-$(mktemp -d -t ocm-hashes-XXXXXX)}"

cleanup() {
	if [[ "${OCM_KEEP_DOWNLOADS:-0}" != "1" ]]; then
		rm -rf "$TMPDIR"
	else
		echo "Keeping downloads at $TMPDIR" >&2
	fi
}
trap cleanup EXIT

if ! command -v jq >/dev/null 2>&1; then
	echo "error: jq is required. install via 'sudo apt install jq' / 'brew install jq' / 'scoop install jq'" >&2
	exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
	echo "error: curl is required" >&2
	exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
	HASHER="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
	HASHER="shasum -a 256"
else
	echo "error: need sha256sum or shasum on PATH" >&2
	exit 1
fi

if [[ ! -f "$REGISTRY" ]]; then
	echo "error: registry not found at $REGISTRY" >&2
	exit 1
fi

# Read the registry; iterate entries
mapfile -t ENTRIES < <(jq -c '.models[]' "$REGISTRY")

PATCHED="$TMPDIR/registry.patched.json"
cp "$REGISTRY" "$PATCHED"

for entry in "${ENTRIES[@]}"; do
	id=$(echo "$entry" | jq -r '.id')
	url=$(echo "$entry" | jq -r '.url')
	current_hash=$(echo "$entry" | jq -r '.sha256')

	if [[ -n "$current_hash" && "$current_hash" != "null" ]]; then
		echo "[skip] $id already has hash $current_hash" >&2
		continue
	fi

	echo "[fetch] $id from $url" >&2
	dest="$TMPDIR/$id.gguf"

	auth_args=()
	if [[ -n "${HF_TOKEN:-}" ]]; then
		auth_args=(-H "Authorization: Bearer $HF_TOKEN")
	fi

	# -L follow redirects (HuggingFace), --fail bail on 4xx/5xx
	curl --fail --location --output "$dest" "${auth_args[@]}" "$url"

	echo "[hash] $id" >&2
	hash=$($HASHER "$dest" | awk '{print $1}')

	echo "[patch] $id sha256 = $hash" >&2
	# jq with input = path; substitute hash in place
	jq --arg id "$id" --arg hash "$hash" \
		'.models |= map(if .id == $id then .sha256 = $hash else . end)' \
		"$PATCHED" > "$PATCHED.next"
	mv "$PATCHED.next" "$PATCHED"

	# Free disk before the next download
	if [[ "${OCM_KEEP_DOWNLOADS:-0}" != "1" ]]; then
		rm -f "$dest"
	fi
done

echo >&2
echo "=== diff against current registry ===" >&2
diff -u "$REGISTRY" "$PATCHED" >&2 || true
echo >&2
echo "=== patched registry ===" >&2
cat "$PATCHED"
echo >&2
echo "Review the diff above. To apply:" >&2
echo "  cp $PATCHED $REGISTRY" >&2
echo "Or paste the patched JSON into $REGISTRY manually." >&2
