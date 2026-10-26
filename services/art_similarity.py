"""dHash de 64 bits para o guard anti-cópia da arte canônica (SPEC-326 R12)."""

from __future__ import annotations

from io import BytesIO

from PIL import Image


def dhash64(png: bytes) -> int:
    """Hash de diferença 9x8 (64 bits) sobre luminância; robusto a recompressão/escala."""
    with Image.open(BytesIO(png)) as image:
        small = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = small.tobytes()
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return bits


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()
