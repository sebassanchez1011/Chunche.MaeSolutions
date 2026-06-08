from __future__ import annotations

import time
from pathlib import Path
from typing import Protocol

from .config import HardwareConfig
from .models import ActionResult, ServoDefinition


class ServoBackend(Protocol):
    def set_angle(self, servo: ServoDefinition, angle: float) -> None:
        ...

    def deinit(self) -> None:
        ...


class SimServoBackend:
    def __init__(self) -> None:
        self.channels: dict[int, float] = {}

    def set_angle(self, servo: ServoDefinition, angle: float) -> None:
        self.channels[servo.channel] = float(angle)

    def deinit(self) -> None:
        self.channels.clear()


class PCA9685ServoBackend:
    def __init__(self, address: int, frequency_hz: int, channels: int = 16) -> None:
        try:
            from adafruit_servokit import ServoKit  # type: ignore
        except ImportError as exc:  # pragma: no cover - requires Raspberry Pi deps
            raise RuntimeError(
                "No se encontro adafruit_servokit. Instala requirements-rpi.txt en la Raspberry Pi."
            ) from exc
        self.kit = ServoKit(channels=channels, address=address, frequency=frequency_hz)

    def set_angle(self, servo: ServoDefinition, angle: float) -> None:
        self.kit.servo[servo.channel].angle = float(angle)

    def deinit(self) -> None:
        for idx in range(16):
            try:
                self.kit.servo[idx].angle = None
            except Exception:
                pass


class SafeServoRig:
    def __init__(self, config: HardwareConfig, backend: ServoBackend, state_path: str | Path | None = None):
        self.config = config
        self.backend = backend
        self.state_path = Path(state_path) if state_path else None
        self.positions: dict[str, float] = {name: servo.home_angle for name, servo in config.servos.items()}
        self.emergency_stopped = False
        self._load_state()

    @classmethod
    def create(cls, mode: str, config: HardwareConfig, state_path: str | Path | None = None) -> "SafeServoRig":
        if mode == "hardware":
            backend: ServoBackend = PCA9685ServoBackend(
                address=config.pca9685_address,
                frequency_hz=config.pca9685_frequency,
                channels=int(config.raw.get("pca9685", {}).get("channels", 16)),
            )
        else:
            backend = SimServoBackend()
        return cls(config=config, backend=backend, state_path=state_path)

    def _load_state(self) -> None:
        if not self.state_path or not self.state_path.exists():
            return
        try:
            import json

            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return
        for name, angle in data.get("positions", {}).items():
            if name in self.config.servos:
                self.positions[name] = self.config.servos[name].clamp(float(angle))

    def _save_state(self) -> None:
        if not self.state_path:
            return
        import json

        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps({"positions": self.positions}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def clear_stop(self) -> None:
        self.emergency_stopped = False

    def emergency_stop(self) -> ActionResult:
        self.emergency_stopped = True
        self.backend.deinit()
        return ActionResult(ok=True, message="Parada de emergencia activada.")

    def status(self) -> dict[str, object]:
        return {
            "emergency_stopped": self.emergency_stopped,
            "positions": dict(self.positions),
            "servos": {
                name: {
                    "channel": servo.channel,
                    "min_angle": servo.min_angle,
                    "max_angle": servo.max_angle,
                    "home_angle": servo.home_angle,
                    "label": servo.label,
                }
                for name, servo in self.config.servos.items()
            },
        }

    def move_servo(self, name: str, angle: float, smooth: bool = True) -> ActionResult:
        if self.emergency_stopped:
            return ActionResult(ok=False, message="Movimiento bloqueado: parada de emergencia activa.")
        if name not in self.config.servos:
            return ActionResult(ok=False, message=f"Servo desconocido: {name}")

        servo = self.config.servos[name]
        try:
            target = servo.validate(float(angle))
        except ValueError as exc:
            return ActionResult(ok=False, message=str(exc))

        current = float(self.positions.get(name, servo.home_angle))
        if smooth:
            step = max(0.5, self.config.motion_step_degrees)
            distance = target - current
            steps = max(1, int(abs(distance) / step))
            for idx in range(1, steps + 1):
                if self.emergency_stopped:
                    return ActionResult(ok=False, message="Movimiento interrumpido por parada de emergencia.")
                value = current + distance * (idx / steps)
                self.backend.set_angle(servo, value)
                self.positions[name] = value
                time.sleep(max(0.0, self.config.motion_step_delay))
        else:
            self.backend.set_angle(servo, target)
            self.positions[name] = target

        self.positions[name] = target
        self._save_state()
        return ActionResult(ok=True, message=f"{servo.label} movido a {target:.1f} grados.", pose={name: target})

    def move_pose(self, pose: dict[str, float], smooth: bool = True) -> ActionResult:
        moved: dict[str, float] = {}
        for name, angle in pose.items():
            result = self.move_servo(name, angle, smooth=smooth)
            if not result.ok:
                return result
            moved.update(result.pose)
        return ActionResult(ok=True, message="Pose aplicada correctamente.", pose=moved)

    def go_home(self) -> ActionResult:
        self.clear_stop()
        return self.move_pose(self.config.home_pose(), smooth=True)

    def apply_named_pose(self, pose_name: str) -> ActionResult:
        pose = self.config.poses.get(pose_name)
        if not pose:
            return ActionResult(ok=False, message=f"Pose no configurada: {pose_name}")
        return self.move_pose(pose, smooth=True)

