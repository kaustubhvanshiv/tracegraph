"""Read-only preflight for the selected processed DARPA source.

This tool downloads nothing, restores no database and assigns no labels. A
matching size/header is an intake check, not validation of dataset contents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


def inspect_input(manifest_path: Path, input_path: Path, compute_sha256=False):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = manifest["source"]
    path = input_path.resolve()
    result = {
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256_utf8_lf": hashlib.sha256(
            manifest_path.read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest(),
        "source_file_id": source["file_id"],
        "source_url": source["url"],
        "input_path": str(path),
        "expected_bytes": source["expected_bytes"],
        "exists": path.is_file(),
        "publisher_sha256": source.get("publisher_sha256"),
        "sha256": None,
        "publisher_checksum_verified": False,
        "dataset_contents_validated": False,
        "host_date_label_scope_validated": False,
        "safe_to_train": False,
        "splits_created": False,
        "models_trained": False,
    }
    if path.parent.is_dir():
        result["free_bytes_on_input_volume"] = shutil.disk_usage(path.parent).free
    if not result["exists"]:
        result.update(status="awaiting_download", actual_bytes=None, format=None)
        return result
    before = path.stat()
    result["actual_bytes"] = before.st_size
    if before.st_size != source["expected_bytes"]:
        result.update(status="size_mismatch", format=None)
        return result
    with path.open("rb") as stream:
        head = stream.read(1024)
    if head.startswith(b"PGDMP"):
        detected = "postgresql_custom_archive"
        result["archive_version_bytes"] = list(head[5:8])
    elif head.startswith(b"-- PostgreSQL database dump"):
        detected = "postgresql_plain_sql"
    elif head[257:262] == b"ustar":
        detected = "tar_archive_requires_toc_review"
    elif head.startswith(b"\x1f\x8b"):
        detected = "gzip_requires_format_review"
    else:
        detected = "unrecognized"
    result["format"] = detected
    if compute_sha256:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        result["sha256"] = digest.hexdigest()
        expected = source.get("publisher_sha256")
        if expected is not None:
            if result["sha256"].lower() != expected.lower():
                result["status"] = "checksum_mismatch"
                return result
            result["publisher_checksum_verified"] = True
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        result["status"] = "input_changed_during_inspection"
        return result
    result["input_modified_time_ns"] = after.st_mtime_ns
    result["status"] = (
        "unrecognized_format" if detected == "unrecognized"
        else "input_present_requires_archive_and_scope_review"
    )
    result["next_action"] = "Inspect archive/table metadata read-only; do not restore or train automatically."
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sha256", action="store_true", help="Stream the entire local file to record a fingerprint.")
    args = parser.parse_args()
    if args.output.resolve() in {args.input.resolve(), args.manifest.resolve()}:
        parser.error("Output must not overwrite the input or source manifest.")
    result = inspect_input(args.manifest, args.input, args.sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "input_present_requires_archive_and_scope_review" else 2


if __name__ == "__main__":
    raise SystemExit(main())
