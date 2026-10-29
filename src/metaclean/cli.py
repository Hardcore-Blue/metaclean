"""Command-line interface for metaclean."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .core import clean_file, find_files, inspect_file, write_report


def _summary(record: dict[str, Any]) -> str:
    kind = record["type"]
    if kind == "image":
        headline = f"{record['format']} image · {record['size']} · {record['mode']} · {record['frames']} frame(s)"
    else:
        headline = f"PDF · {record['pages']} page(s) · {'encrypted' if record['encrypted'] else 'not encrypted'}"
    metadata = record.get("metadata", {})
    lines = [f"{record['path']}", f"  {headline}"]
    if metadata:
        lines.append("  Metadata:")
        for group, values in metadata.items():
            lines.append(f"    {group}:")
            if isinstance(values, dict):
                for key, value in values.items():
                    lines.append(f"      {key}: {value}")
            else:
                lines.append(f"      {values}")
    else:
        lines.append("  Metadata: none found")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="metaclean", description="Inspect and remove metadata from images and PDFs.")
    parser.add_argument("--version", action="version", version=f"metaclean {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Summarize metadata in a file or folder")
    inspect.add_argument("path", type=Path)
    inspect.add_argument("--shallow", action="store_true", help="Do not inspect nested folders")
    inspect.add_argument("--format", choices=("text", "json", "csv"), default="text", help="Output format")
    inspect.add_argument("--output", type=Path, help="Save JSON/CSV report to this path")
    clean = sub.add_parser("clean", help="Write metadata-stripped copies of supported files")
    clean.add_argument("path", type=Path)
    clean.add_argument("-o", "--output", type=Path, required=True, help="Output file (single input) or folder (folder input)")
    clean.add_argument("--shallow", action="store_true", help="Do not process nested folders")
    clean.add_argument("--overwrite", action="store_true", help="Replace existing output files")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source: Path = args.path.expanduser()
    if not source.exists():
        print(f"Error: path does not exist: {source}", file=sys.stderr)
        return 2
    if args.command == "inspect":
        try:
            paths = find_files(source, recursive=not args.shallow)
            records = []
            for path in paths:
                try:
                    records.append(inspect_file(path))
                except Exception as exc:
                    records.append({"path": str(path), "type": "error", "error": str(exc), "metadata": {}})
            if args.format == "text":
                print("\n\n".join(_summary(r) if r["type"] != "error" else f"{r['path']}\n  Error: {r['error']}" for r in records) or "No supported files found.")
            elif args.output:
                write_report(records, args.output.expanduser(), args.format)
                print(f"Saved {len(records)} record(s) to {args.output}")
            elif args.format == "json":
                print(json.dumps(records, indent=2, ensure_ascii=False))
            else:
                print("--output is required when --format=csv", file=sys.stderr)
                return 2
            return 0 if all(r["type"] != "error" for r in records) else 1
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    paths = find_files(source, recursive=not args.shallow)
    if not paths:
        print("No supported files found.", file=sys.stderr)
        return 1
    output: Path = args.output.expanduser()
    single_file = source.is_file()
    failures = 0
    for path in paths:
        target = output if single_file else output / path.relative_to(source)
        if target.exists() and not args.overwrite:
            print(f"Skipped existing output: {target}", file=sys.stderr)
            failures += 1
            continue
        try:
            clean_file(path, target)
            print(f"Cleaned copy saved: {target}")
        except Exception as exc:
            print(f"Failed {path}: {exc}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
