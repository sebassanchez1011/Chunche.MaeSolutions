from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import ServoDefinition


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return {}
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.lower() in {"null", "none"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        return int(value, 0)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _minimal_yaml_load(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        parsed = _parse_scalar(value)
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        parent[key] = parsed
        if isinstance(parsed, dict):
            stack.append((indent, parsed))
    return root


def load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        return _minimal_yaml_load(text)
    loaded = yaml.safe_load(text)
    return loaded or {}


@dataclass(frozen=True)
class HardwareConfig:
    path: Path
    raw: dict[str, Any]
    servos: dict[str, ServoDefinition]
    poses: dict[str, dict[str, float]]

    @property
    def default_mode(self) -> str:
        return str(self.raw.get("project", {}).get("default_mode", "sim"))

    @property
    def confidence_threshold(self) -> float:
        return float(self.raw.get("project", {}).get("confidence_threshold", 0.65))

    @property
    def pca9685_address(self) -> int:
        return int(self.raw.get("pca9685", {}).get("address", 0x40))

    @property
    def pca9685_frequency(self) -> int:
        return int(self.raw.get("pca9685", {}).get("frequency_hz", 50))

    @property
    def camera_size(self) -> tuple[int, int]:
        camera = self.raw.get("camera", {})
        return int(camera.get("width", 1280)), int(camera.get("height", 720))

    @property
    def motion_step_degrees(self) -> float:
        return float(self.raw.get("motion", {}).get("step_degrees", 2))

    @property
    def motion_step_delay(self) -> float:
        return float(self.raw.get("motion", {}).get("step_delay_seconds", 0.015))

    @property
    def yolo_enabled(self) -> bool:
        return bool(self.raw.get("vision", {}).get("yolo_enabled", False))

    @property
    def yolo_model_path(self) -> Path:
        model = self.raw.get("vision", {}).get("yolo_model_path", "models/best.pt")
        return (self.path.parent.parent / str(model)).resolve()

    def home_pose(self) -> dict[str, float]:
        return dict(self.poses.get("home", {name: servo.home_angle for name, servo in self.servos.items()}))


def load_config(path: str | Path = "config/hardware.yaml") -> HardwareConfig:
    config_path = Path(path).resolve()
    raw = load_yaml(config_path)
    servos: dict[str, ServoDefinition] = {}
    for name, values in raw.get("servos", {}).items():
        servos[name] = ServoDefinition(
            name=name,
            channel=int(values["channel"]),
            min_angle=float(values["min_angle"]),
            max_angle=float(values["max_angle"]),
            home_angle=float(values["home_angle"]),
            label=str(values.get("label", name)),
        )
    poses = {
        pose_name: {servo_name: float(angle) for servo_name, angle in pose.items()}
        for pose_name, pose in raw.get("poses", {}).items()
    }
    return HardwareConfig(path=config_path, raw=raw, servos=servos, poses=poses)

