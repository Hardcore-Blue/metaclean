"""File inspection and metadata cleaning primitives."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, ExifTags
from pypdf import PdfReader, PdfWriter

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif"}
PDF_EXTENSIONS = {".pdf"}


def _serializable(value: Any) -> Any:
    if isinstance(value, bytes):
        return f"<binary data: {len(value)} bytes>"
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(v) for v in value]
    return str(value)


def inspect_image(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        exif: dict[str, Any] = {}
        try:
            for key, value in image.getexif().items():
                name = ExifTags.TAGS.get(key, str(key))
                exif[name] = _serializable(value)
        except Exception as exc:
            exif["_read_error"] = str(exc)
        metadata: dict[str, Any] = {}
        if exif:
            metadata["EXIF"] = exif
        info = {k: _serializable(v) for k, v in image.info.items() if k not in {"exif", "icc_profile"}}
        if info:
            metadata["container"] = info
        if image.info.get("icc_profile"):
            metadata["ICC profile"] = f"present ({len(image.info['icc_profile'])} bytes)"
        return {
            "path": str(path),
            "type": "image",
            "format": image.format,
            "size": f"{image.width}x{image.height}",
            "mode": image.mode,
            "frames": getattr(image, "n_frames", 1),
            "metadata": metadata,
        }


def inspect_pdf(path: Path) -> dict[str, Any]:
    reader = PdfReader(str(path), strict=False)
    metadata = {str(k): _serializable(v) for k, v in (reader.metadata or {}).items()}
    return {
        "path": str(path),
        "type": "pdf",
        "pages": len(reader.pages),
        "encrypted": reader.is_encrypted,
        "metadata": metadata,
    }


def inspect_file(path: Path) -> dict[str, Any]:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return inspect_image(path)
    if ext in PDF_EXTENSIONS:
        return inspect_pdf(path)
    raise ValueError(f"Unsupported file type: {path.suffix or '(no extension)'}")


def find_files(path: Path, recursive: bool = True) -> list[Path]:
    if path.is_file():
        return [path]
    iterator = path.rglob("*") if recursive else path.glob("*")
    return sorted(p for p in iterator if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS | PDF_EXTENSIONS)


def clean_image(source: Path, destination: Path) -> None:
    """Re-encode pixels without carrying metadata; animated images are rejected."""
    with Image.open(source) as image:
        if getattr(image, "n_frames", 1) > 1:
            raise ValueError("Animated images are not cleaned to avoid silently dropping frames")
        image = ImageOps.exif_transpose(image)
        image.load()
        # Copy only pixel data/mode. Do not forward EXIF, ICC, comments, or container info.
        clean = Image.new(image.mode, image.size)
        clean.putdata(list(image.getdata()))
        save_options: dict[str, Any] = {}
        if image.format == "JPEG" and clean.mode not in {"RGB", "L", "CMYK"}:
            clean = clean.convert("RGB")
        if image.format == "PNG" and clean.mode == "P":
            clean = clean.convert("RGBA")
        clean.save(destination, format=image.format, **save_options)


def clean_pdf(source: Path, destination: Path) -> None:
    reader = PdfReader(str(source), strict=False)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not cleaned; decrypt them first")
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    # Pages are copied but the source document information dictionary is not.
    with destination.open("wb") as stream:
        writer.write(stream)


def clean_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == destination.resolve():
        raise ValueError("Input and output paths must be different")
    if source.suffix.lower() in IMAGE_EXTENSIONS:
        clean_image(source, destination)
    elif source.suffix.lower() in PDF_EXTENSIONS:
        clean_pdf(source, destination)
    else:
        raise ValueError(f"Unsupported file type: {source.suffix or '(no extension)'}")


def write_report(records: list[dict[str, Any]], destination: Path, fmt: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        destination.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    # CSV keeps metadata as JSON so each source file remains a single row.
    fields = sorted({key for item in records for key in item})
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})
