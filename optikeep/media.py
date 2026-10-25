"""Read-only media analysis with bounded streaming and identity checks."""

import hashlib
import json
from pathlib import Path

import imagehash
import numpy as np
from PIL import Image, ImageOps

from optikeep.process import run_tool

ALGORITHM = "internal-v1"
IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
VIDEOS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".m4v",
    ".webm",
    ".mpeg",
    ".mpg",
    ".wmv",
    ".ts",
    ".mts",
    ".m2ts",
}


def identity(path: Path) -> dict:
    """Capture change observations without treating them as content proof."""
    stat = path.stat(follow_symlinks=False)
    return {
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "ctime_ns": stat.st_ctime_ns,
    }


def resolve_media(root: Path, relative: str) -> Path:
    """Reject traversal and symlink components before opening a source."""
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Media path must be relative to its configured root")
    root = root.resolve(strict=True)
    path = root
    for part in candidate.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("Symlink media paths are not permitted")
    path.resolve(strict=True).relative_to(root)
    if not path.is_file():
        raise ValueError("Expected a regular media file")
    return path


def cache_key(relative: str, observed: dict) -> str:
    """Version metadata-trusted cache entries by path and identity."""
    return hashlib.sha256(
        json.dumps([relative, observed, ALGORITHM], sort_keys=True).encode()
    ).hexdigest()


def digest(path: Path) -> str:
    """Hash a whole file with constant buffer memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def analyze(root: Path, task: dict, pixel_limit: int, timeout: int) -> dict:
    """Produce internal measurements while never modifying media."""
    path = resolve_media(root, task["path"])
    before = identity(path)
    if before != task["identity"]:
        raise ValueError("Source changed before analysis")
    result = {"algorithm": ALGORITHM, "sha256": digest(path), "identity": before}
    if task["kind"] == "image":
        with Image.open(path) as original:
            if original.width * original.height > pixel_limit:
                raise ValueError("Image exceeds configured pixel budget")
            if getattr(original, "n_frames", 1) != 1:
                raise ValueError("Animated images require a qualified analyzer")
            image = ImageOps.exif_transpose(original).convert("RGB")
            result.update(
                width=image.width,
                height=image.height,
                hashes={
                    name: str(function(image))
                    for name, function in {
                        "phash": imagehash.phash,
                        "dhash": imagehash.dhash,
                        "ahash": imagehash.average_hash,
                        "whash": imagehash.whash,
                    }.items()
                },
            )
            sample = image.copy()
            sample.thumbnail((1024, 1024))
            gray = np.asarray(sample.convert("L"), dtype=np.float32)
            result["quality"] = {
                "version": "measurements-v1",
                "sharpness": (
                    float(np.var(np.diff(gray, axis=0))) if gray.shape[0] > 1 else 0
                ),
                "clipped_fraction": float(np.mean((gray <= 1) | (gray >= 254))),
                "pixels": image.width * image.height,
                "ranking_qualified": False,
            }
    else:
        output = run_tool(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            timeout=timeout,
        )
        result["video"] = json.loads(output)
    if identity(path) != before:
        raise ValueError("Source changed during analysis")
    return result
