from __future__ import annotations

from io import BytesIO

from PIL import Image

from infrastructure.ports import GeneratedImage


class FakeImageGenerator:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        output = BytesIO()
        Image.new("RGB", (320, 480), (42, 23, 29)).save(output, "PNG")
        return GeneratedImage(output.getvalue(), "image/png", "fake-request",
                              request.model, {"images": 1, "cost_usd": 0})
