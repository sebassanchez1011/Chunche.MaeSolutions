from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class Detection:
    label: str
    confidence: float
    box: BoundingBox
    action: str
    recommendation: str
    source: str = "heuristic"
    polygon: list[tuple[int, int]] | None = None
    area_pixels: float | None = None
    id: int | None = None

    @property
    def target_point(self) -> tuple[float, float]:
        if self.polygon:
            return polygon_centroid(self.polygon)
        return self.box.center

    def quadrant(self, image_width: int, image_height: int) -> str:
        cx, cy = self.target_point
        horizontal = "izquierda" if cx < image_width / 2 else "derecha"
        vertical = "superior" if cy < image_height / 2 else "inferior"
        return f"{vertical} {horizontal}"

    def to_dict(self, image_width: int | None = None, image_height: int | None = None) -> dict[str, Any]:
        data = {
            "id": self.id,
            "label": self.label,
            "confidence": round(float(self.confidence), 3),
            "box": self.box.to_dict(),
            "action": self.action,
            "recommendation": self.recommendation,
            "source": self.source,
            "polygon": [[int(x), int(y)] for x, y in self.polygon] if self.polygon else None,
            "area_pixels": round(float(self.area_pixels), 1) if self.area_pixels is not None else None,
            "target_point": [round(self.target_point[0], 1), round(self.target_point[1], 1)],
        }
        if image_width and image_height:
            data["quadrant"] = self.quadrant(image_width, image_height)
        return data


@dataclass(frozen=True)
class ServoDefinition:
    name: str
    channel: int
    min_angle: float
    max_angle: float
    home_angle: float
    label: str

    def clamp(self, angle: float) -> float:
        return max(self.min_angle, min(self.max_angle, float(angle)))

    def validate(self, angle: float) -> float:
        value = float(angle)
        if value < self.min_angle or value > self.max_angle:
            raise ValueError(
                f"Servo {self.name} fuera de rango: {value} "
                f"(permitido {self.min_angle}-{self.max_angle})"
            )
        return value


@dataclass
class SessionInfo:
    id: int
    work_id: str
    operator: str
    notes: str
    created_at: datetime
    status: str = "open"


@dataclass
class ActionResult:
    ok: bool
    message: str
    pose: dict[str, float] = field(default_factory=dict)
    requires_human: bool = False


def polygon_area(points: list[tuple[int, int]]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    for idx, (x1, y1) in enumerate(points):
        x2, y2 = points[(idx + 1) % len(points)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


def polygon_centroid(points: list[tuple[int, int]]) -> tuple[float, float]:
    if not points:
        return (0.0, 0.0)
    area_twice = 0.0
    cx = 0.0
    cy = 0.0
    for idx, (x1, y1) in enumerate(points):
        x2, y2 = points[(idx + 1) % len(points)]
        cross = x1 * y2 - x2 * y1
        area_twice += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area_twice) < 1e-6:
        return (
            sum(x for x, _ in points) / len(points),
            sum(y for _, y in points) / len(points),
        )
    factor = 1 / (3 * area_twice)
    return (cx * factor, cy * factor)
