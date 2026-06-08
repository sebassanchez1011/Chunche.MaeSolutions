from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class CalibrationPoint:
    image_x: float
    image_y: float
    pose: dict[str, float]
    label: str = ""


class CalibrationStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.points: list[CalibrationPoint] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.points = []
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.points = [CalibrationPoint(**item) for item in data.get("points", [])]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"points": [asdict(point) for point in self.points]}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add_point(self, image_x: float, image_y: float, pose: dict[str, float], label: str = "") -> CalibrationPoint:
        point = CalibrationPoint(float(image_x), float(image_y), {k: float(v) for k, v in pose.items()}, label)
        self.points.append(point)
        self.save()
        return point

    def clear(self) -> None:
        self.points = []
        self.save()

    def as_dict(self) -> dict[str, object]:
        return {"points": [asdict(point) for point in self.points]}

    def pose_for_point(self, image_x: float, image_y: float, fallback_pose: dict[str, float]) -> dict[str, float]:
        if not self.points:
            return dict(fallback_pose)
        if len(self.points) == 1:
            return dict(self.points[0].pose)

        weighted: dict[str, float] = {}
        weights: dict[str, float] = {}
        for point in self.points:
            dist = math.hypot(float(image_x) - point.image_x, float(image_y) - point.image_y)
            weight = 1.0 / max(dist, 1.0)
            for servo, angle in point.pose.items():
                weighted[servo] = weighted.get(servo, 0.0) + angle * weight
                weights[servo] = weights.get(servo, 0.0) + weight

        pose = dict(fallback_pose)
        for servo, total in weighted.items():
            pose[servo] = total / weights[servo]
        return pose

