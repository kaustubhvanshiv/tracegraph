"""Read DARPA support ZIPs into an ignored inspection cache, not the raw data.

Run with the bundled PDF Python runtime (pypdf required). Only PDF, Markdown,
Avro schema, and IDL members are extracted. Archives remain untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile

from pypdf import PdfReader

ALLOWED = {".pdf", ".md", ".avsc", ".avdl"}
MAX_MEMBER_BYTES = 64 * 1024 * 1024


def safe_member_path(root: Path, name: str) -> Path:
    parts = PurePosixPath(name.replace("\\", "/"))
    if parts.is_absolute() or ".." in parts.parts or ":" in name:
        raise ValueError(f"Unsafe archive member: {name}")
    target = root.joinpath(*parts.parts).resolve()
    if not target.is_relative_to(root.resolve()) or target == root.resolve():
        raise ValueError(f"Archive member escapes output directory: {name}")
    return target


def read_support(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    if not source.is_dir():
        raise ValueError(f"Missing support directory: {source}")
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Output and original source must be separate directories")
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"source_path": str(source), "output_path": str(output), "archives": [], "documents": []}
    extracted = set()
    for archive_path in sorted(source.glob("*.zip")):
        archive = {"path": str(archive_path), "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(), "members": []}
        with zipfile.ZipFile(archive_path) as zipped:
            if len(zipped.infolist()) > 1000:
                raise ValueError("Support archive has too many members")
            for entry in zipped.infolist():
                target = safe_member_path(output, entry.filename)
                mode = entry.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ValueError(f"Symlink member refused: {entry.filename}")
                extract = not entry.is_dir() and target.suffix.lower() in ALLOWED
                item = {"name": entry.filename, "bytes": entry.file_size, "extracted": extract}
                archive["members"].append(item)
                if not extract:
                    continue
                if entry.file_size > MAX_MEMBER_BYTES:
                    raise ValueError(f"Support member too large: {entry.filename}")
                if target in extracted:
                    raise ValueError(f"Duplicate output member: {entry.filename}")
                target.parent.mkdir(parents=True, exist_ok=True)
                payload = zipped.read(entry)  # validates ZIP CRC
                target.write_bytes(payload)
                extracted.add(target)
                item["sha256"] = hashlib.sha256(payload).hexdigest()
                item["output_path"] = str(target)
        manifest["archives"].append(archive)
    for markdown in sorted(source.glob("*.md")):
        target = output / markdown.name
        shutil.copyfile(markdown, target)
        extracted.add(target)
    for path in sorted(extracted):
        document = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if path.suffix.lower() == ".pdf":
            pdf = PdfReader(path)
            text_path = path.with_suffix(".pages.txt")
            pages = [f"\n===== PAGE {i} =====\n{page.extract_text() or ''}\n"
                     for i, page in enumerate(pdf.pages, 1)]
            text_path.write_text("".join(pages), encoding="utf-8")
            document.update(page_count=len(pdf.pages), text_path=str(text_path), metadata={str(k): str(v) for k, v in (pdf.metadata or {}).items()})
        manifest["documents"].append(document)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = read_support(args.source, args.output)
    for document in manifest["documents"]:
        print(f"Read {document['path']} ({document.get('page_count', 'non-PDF')} pages)")


if __name__ == "__main__":
    main()
