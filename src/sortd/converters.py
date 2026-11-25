"""Image conversion and content hashing."""

import hashlib
from pathlib import Path

from PIL import Image

try:
    import pillow_heif
except ImportError:  # pragma: no cover - optional plugin at runtime
    pass
else:
    pillow_heif.register_heif_opener()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 without reading the whole file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def convert_image(path: Path, output_format: str = "jpg") -> Path:
    """Convert HEIC or WEBP to JPEG or PNG and return its output path."""
    fmt = output_format.lower()
    if fmt not in {"jpg", "jpeg", "png"}:
        raise ValueError("output_format must be jpg or png")
    output = path.with_suffix(".jpg" if fmt in {"jpg", "jpeg"} else ".png")
    with Image.open(path) as image:
        if fmt in {"jpg", "jpeg"}:
            image.convert("RGB").save(output, "JPEG", quality=92)
        else:
            image.save(output, "PNG")
    return output
