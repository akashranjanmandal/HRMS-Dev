"""Compress a check-in selfie to about 100 KB on upload (RFP 4.1 §4.5).

A phone camera photo is typically 1-5 MB; nothing in this system needs
that resolution to confirm "this is the same person, at this time". We
re-encode as JPEG, scaling down and lowering quality in steps until the
result fits the target, so storage and bandwidth stay small across 300
users checking in twice a day.
"""
import io

from fastapi import HTTPException
from PIL import Image

TARGET_BYTES = 100 * 1024
MAX_DIMENSION = 800  # px, long edge — ample for a face-verification selfie
_QUALITY_STEPS = (85, 70, 55, 40, 25)


def compress_selfie(contents: bytes) -> bytes:
    try:
        image = Image.open(io.BytesIO(contents))
        image = image.convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="That file is not a readable image")

    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))

    best = None
    for quality in _QUALITY_STEPS:
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        best = data
        if len(data) <= TARGET_BYTES:
            return data
    # Even the lowest quality step didn't reach the target (an unusually
    # large/complex image) — return the smallest we achieved rather than
    # fail the check-in over a few extra KB.
    return best
