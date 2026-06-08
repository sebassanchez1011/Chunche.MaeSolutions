from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw


class Camera(Protocol):
    def capture(self, output_path: str | Path) -> tuple[Path, int, int]:
        ...


class SimulatedCamera:
    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height

    def capture(self, output_path: str | Path) -> tuple[Path, int, int]:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (self.width, self.height), "#f2efe7")
        draw = ImageDraw.Draw(img)

        # Fondo tipo obra en papel/lienzo.
        margin_x = int(self.width * 0.12)
        margin_y = int(self.height * 0.10)
        canvas = (margin_x, margin_y, self.width - margin_x, self.height - margin_y)
        draw.rectangle(canvas, fill="#d9c9a3", outline="#8b7e66", width=4)

        # Grieta.
        crack = [
            (int(self.width * 0.28), int(self.height * 0.32)),
            (int(self.width * 0.34), int(self.height * 0.38)),
            (int(self.width * 0.43), int(self.height * 0.36)),
            (int(self.width * 0.52), int(self.height * 0.45)),
        ]
        draw.line(crack, fill="#27221f", width=7)
        draw.line([(x + 6, y + 10) for x, y in crack[:3]], fill="#3b332e", width=3)

        # Perdida de pigmento o desgaste.
        draw.ellipse(
            (
                int(self.width * 0.62),
                int(self.height * 0.28),
                int(self.width * 0.78),
                int(self.height * 0.50),
            ),
            fill="#eee5cf",
            outline="#b8aa8d",
            width=2,
        )

        # Polvo/suciedad superficial.
        random.seed(42)
        for _ in range(130):
            x = random.randint(canvas[0] + 20, canvas[2] - 20)
            y = random.randint(canvas[1] + 20, canvas[3] - 20)
            radius = random.choice([1, 1, 2, 3])
            shade = random.choice(["#6f695f", "#7e7669", "#8d8375"])
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=shade)

        img.save(path, quality=95)
        return path, self.width, self.height


class Picamera2Camera:
    def __init__(self, width: int = 1280, height: int = 720, warmup_seconds: float = 1.0):
        try:
            from picamera2 import Picamera2  # type: ignore
        except ImportError as exc:  # pragma: no cover - requires Raspberry Pi OS package
            raise RuntimeError("Picamera2 no esta instalado. Usa: sudo apt install -y python3-picamera2") from exc

        self.width = width
        self.height = height
        self.camera = Picamera2()
        config = self.camera.create_still_configuration(main={"size": (width, height)})
        self.camera.configure(config)
        self.camera.start()
        time.sleep(warmup_seconds)

    def capture(self, output_path: str | Path) -> tuple[Path, int, int]:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.camera.capture_file(str(path))
        return path, self.width, self.height


def create_camera(mode: str, width: int, height: int, warmup_seconds: float = 1.0) -> Camera:
    if mode == "hardware":
        return Picamera2Camera(width=width, height=height, warmup_seconds=warmup_seconds)
    return SimulatedCamera(width=width, height=height)

