"""dHash de 64 bits para o guard anti-cópia da arte canônica (SPEC-326 R12)."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps


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


def dhash64_mirrored(png: bytes) -> int:
    """dHash da imagem espelhada na horizontal (cópia espelhada não escapa do guard)."""
    with Image.open(BytesIO(png)) as image:
        out = BytesIO()
        ImageOps.mirror(image.convert("RGB")).save(out, "PNG")
    return dhash64(out.getvalue())


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()
