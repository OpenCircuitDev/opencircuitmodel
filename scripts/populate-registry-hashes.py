#!/usr/bin/env python3
"""Populate SHA256 hashes in crates/ocm-models/registry.json.

Python alternative to populate-registry-hashes.sh — same job, no jq
dependency. Downloads each model with empty sha256, computes hash,
patches registry.json IN PLACE (after a backup).

Usage:
  python scripts/populate-registry-hashes.py            # all empty entries
  python scripts/populate-registry-hashes.py --only qwen2.5-1.5b-q4
  python scripts/populate-registry-hashes.py --tmp-dir D:/scratch
  python scripts/populate-registry-hashes.py --dry-run  # show plan, no download

Bandwidth: ~30 GB total for all 5 default v1 models. Each download is
streamed to disk + hashed in chunks (no full-file load into memory).
The temp dir is wiped after each entry to keep peak disk usage at
~max(model_size_mb).

Optional env:
  HF_TOKEN — bearer token if any registry entry is gated upstream

Exit codes:
  0  success (or dry-run)
  1  download failed for ≥1 entry
  2  precondition error (registry not found, etc.)
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = REPO_ROOT / "crates" / "ocm-models" / "registry.json"


@dataclass
class Result:
    model_id: str
    status: str  # "skipped" | "ok" | "fail"
    message: str = ""
    sha256: str = ""


def load_registry(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"error: registry not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_registry(path: Path, registry: dict) -> None:
    # Preserve trailing newline + 2-space indent to match the existing file
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")


def download_and_hash(url: str, dest: Path, hf_token: str | None) -> str:
    """Stream download, compute SHA256 in chunks. Returns lowercase hex hash."""
    request = urllib.request.Request(url)
    if hf_token:
        request.add_header("Authorization", f"Bearer {hf_token}")
    request.add_header("User-Agent", "ocm-registry-hasher/0.1")

    sha = hashlib.sha256()
    try:
        with urllib.request.urlopen(request) as resp, dest.open("wb") as out:
            total = int(resp.headers.get("Content-Length", "0"))
            downloaded = 0
            chunk_size = 1024 * 1024
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                sha.update(chunk)
                downloaded += len(chunk)
                if total:
                    pct = (downloaded / total) * 100
                    print(
                        f"  {downloaded // (1024 * 1024)} MB / {total // (1024 * 1024)} MB ({pct:.1f}%)",
                        end="\r",
                        file=sys.stderr,
                    )
            print(file=sys.stderr)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.reason}") from e
    return sha.hexdigest()


def populate(
    *,
    only: str | None,
    tmp_dir: Path,
    dry_run: bool,
    hf_token: str | None,
) -> int:
    registry = load_registry(REGISTRY)
    backup = REGISTRY.with_suffix(".json.bak")
    if not dry_run:
        shutil.copyfile(REGISTRY, backup)
        print(f"[backup] {REGISTRY.name} -> {backup.name}", file=sys.stderr)

    results: list[Result] = []
    for entry in registry.get("models", []):
        model_id = entry["id"]
        if only and only != model_id:
            continue
        if entry.get("sha256"):
            results.append(Result(model_id, "skipped", "already hashed"))
            continue

        url = entry["url"]
        size_mb = entry.get("size_mb", "?")
        print(f"[fetch] {model_id} ({size_mb} MB) <- {url}", file=sys.stderr)

        if dry_run:
            results.append(Result(model_id, "skipped", "dry-run"))
            continue

        dest = tmp_dir / f"{model_id}.gguf"
        try:
            sha = download_and_hash(url, dest, hf_token)
        except (RuntimeError, OSError) as e:
            results.append(Result(model_id, "fail", str(e)))
            with contextlib.suppress(FileNotFoundError):
                dest.unlink()
            continue

        entry["sha256"] = sha
        results.append(Result(model_id, "ok", "", sha))
        save_registry(REGISTRY, registry)
        print(f"[ok] {model_id} sha256={sha}", file=sys.stderr)

        # Drop the GGUF immediately to keep peak disk low
        with contextlib.suppress(FileNotFoundError):
            dest.unlink()

    print("\n=== summary ===", file=sys.stderr)
    failed = 0
    for r in results:
        marker = {"ok": "[OK]    ", "skipped": "[skip]  ", "fail": "[FAIL]  "}[r.status]
        detail = r.sha256 or r.message
        print(f"{marker}{r.model_id}: {detail}", file=sys.stderr)
        if r.status == "fail":
            failed += 1

    if failed:
        print(
            f"\n{failed} download(s) failed. Backup at {backup} if you want to revert.",
            file=sys.stderr,
        )
        return 1
    if not dry_run:
        print(f"\nRegistry patched in place. Review with `git diff {REGISTRY}` before commit.", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        help="Process only this model id (e.g. qwen2.5-1.5b-q4)",
    )
    parser.add_argument(
        "--tmp-dir",
        type=Path,
        help="Where to stage downloads (default: system temp). Useful to avoid Dropbox sync.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded, skip the network IO",
    )
    args = parser.parse_args()

    hf_token = os.environ.get("HF_TOKEN")

    if args.tmp_dir:
        args.tmp_dir.mkdir(parents=True, exist_ok=True)
        return populate(
            only=args.only,
            tmp_dir=args.tmp_dir,
            dry_run=args.dry_run,
            hf_token=hf_token,
        )

    with tempfile.TemporaryDirectory(prefix="ocm-hashes-") as td:
        return populate(
            only=args.only,
            tmp_dir=Path(td),
            dry_run=args.dry_run,
            hf_token=hf_token,
        )


if __name__ == "__main__":
    sys.exit(main())
