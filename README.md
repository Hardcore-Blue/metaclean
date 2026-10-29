# MetaClean

MetaClean is a small command-line tool for inspecting metadata in common images and PDFs, and writing cleaned copies. It is designed for privacy-aware sharing and portfolio demonstration.

## Supported formats

- Images: JPEG, PNG, WebP, TIFF, BMP, and single-frame GIF
- PDF: document information metadata and basic file properties

## Install

From this directory, install in editable mode:

```sh
python -m pip install -e .
```

## Usage

Inspect a file or recursively scan a folder:

```sh
metaclean inspect photo.jpg
metaclean inspect ./documents
metaclean inspect ./documents --format json --output report.json
metaclean inspect ./documents --format csv --output report.csv
```

Write a cleaned copy of one file or a folder tree:

```sh
metaclean clean photo.jpg --output cleaned/photo.jpg
metaclean clean ./to_share --output ./cleaned
```

Existing outputs are skipped by default. Add `--overwrite` to replace them. Use `--shallow` to limit folder operations to files directly inside the given folder. Run `metaclean --help` or `metaclean <command> --help` for command options.

## What cleaning does

- **Images:** decodes and re-encodes pixel data without carrying EXIF, ICC profiles, comments, or container metadata. EXIF orientation is applied to the pixels before removing the orientation tag. Animated images are rejected to avoid silently losing animation frames. Re-encoding may change file size or color appearance slightly.
- **PDFs:** creates a new PDF from the source pages without copying the document information dictionary. Encrypted PDFs are rejected. This does not redact visible text, remove sensitive content from page artwork, or guarantee removal of every non-document metadata structure.

The source is never modified. Review the cleaned file and inspect its output before sharing; this utility is not a forensic sanitization guarantee.

## Development

Python 3.10 or later is required. Dependencies are Pillow and pypdf. The project uses a `src` layout and exposes the `metaclean` console command.
