from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from .calibration import CalibrationStore
from .camera import create_camera
from .config import HardwareConfig, load_config
from .models import polygon_centroid
from .reports import ReportGenerator
from .servo import SafeServoRig
from .storage import Storage
from .vision import annotate_image, create_detector


class ChuncheSystem:
    def __init__(
        self,
        mode: str = "sim",
        config_path: str | Path = "config/hardware.yaml",
        data_dir: str | Path = "data",
    ):
        self.mode = mode
        self.config: HardwareConfig = load_config(config_path)
        self.data_dir = Path(data_dir).resolve()
        self.sessions_dir = self.data_dir / "sessions"
        self.reports_dir = self.data_dir / "reports"
        self.state_dir = self.data_dir / "state"
        self.storage = Storage(self.data_dir / "chunche.sqlite3")
        self.calibration = CalibrationStore(self.state_dir / "calibration.json")
        width, height = self.config.camera_size
        camera_raw = self.config.raw.get("camera", {})
        self.camera = create_camera(mode, width, height, float(camera_raw.get("warmup_seconds", 1.0)))
        self.servos = SafeServoRig.create(mode, self.config, state_path=self.state_dir / "servos.json")
        self.detector = create_detector(self.config)
        self.reports = ReportGenerator(self.reports_dir)

    def status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "config": str(self.config.path),
            "data_dir": str(self.data_dir),
            "servos": self.servos.status(),
            "calibration_points": len(self.calibration.points),
            "sessions": self.storage.list_sessions(limit=10),
        }

    def create_session(self, work_id: str, operator: str, notes: str = "") -> dict[str, Any]:
        session = self.storage.create_session(work_id=work_id, operator=operator, notes=notes)
        self.storage.log_action(
            session.id,
            "session_created",
            {"work_id": session.work_id, "operator": session.operator, "mode": self.mode},
        )
        return {
            "id": session.id,
            "work_id": session.work_id,
            "operator": session.operator,
            "notes": session.notes,
            "created_at": session.created_at.isoformat(timespec="seconds"),
            "status": session.status,
        }

    def capture(self, session_id: int, kind: str = "initial") -> dict[str, Any]:
        self.storage.get_session(session_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = self.sessions_dir / str(session_id)
        path = session_dir / f"{kind}_{timestamp}.jpg"
        path, width, height = self.camera.capture(path)
        image_id = self.storage.add_image(session_id, kind, path, width, height)
        self.storage.log_action(session_id, "capture", {"kind": kind, "path": str(path), "image_id": image_id})
        return {
            "image_id": image_id,
            "kind": kind,
            "path": str(path),
            "media_url": self.media_url(path),
            "width": width,
            "height": height,
        }

    def analyze(self, session_id: int) -> dict[str, Any]:
        image = self.storage.latest_image(session_id, kinds=("analysis", "initial", "final"))
        if image is None:
            image = self.capture(session_id, kind="initial")
            image_id = int(image["image_id"])
            image_path = Path(image["path"])
            width = int(image["width"])
            height = int(image["height"])
        else:
            image_id = int(image["id"])
            image_path = Path(image["path"])
            width = int(image["width"])
            height = int(image["height"])

        detections = self.detector.analyze(image_path)
        for detection in detections:
            self.storage.add_detection(session_id, image_id, detection, width, height)

        annotated_path = image_path.with_name(f"annotated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        annotate_image(image_path, detections, annotated_path)
        with Image.open(annotated_path) as annotated:
            annotated_id = self.storage.add_image(session_id, "annotated", annotated_path, annotated.width, annotated.height)

        self.storage.log_action(
            session_id,
            "analysis",
            {
                "source_image_id": image_id,
                "annotated_image_id": annotated_id,
                "detections": len(detections),
                "detector": detections[0].source if detections else "heuristic",
            },
        )
        return {
            "image_id": image_id,
            "annotated_image_id": annotated_id,
            "annotated_media_url": self.media_url(annotated_path),
            "detections": [det.to_dict(width, height) for det in detections],
        }

    def confirm_action(self, session_id: int, detection_id: int) -> dict[str, Any]:
        detection = self.storage.get_detection(detection_id)
        if int(detection["session_id"]) != int(session_id):
            raise ValueError("La deteccion no pertenece a esta sesion.")

        if detection.get("polygon"):
            center_x, center_y = polygon_centroid([(int(x), int(y)) for x, y in detection["polygon"]])
        else:
            box = detection["box"]
            center_x = box["x"] + box["width"] / 2
            center_y = box["y"] + box["height"] / 2
        fallback_pose = self.config.home_pose()

        if detection["action"] == "limpieza_controlada":
            tool_result = self.servos.apply_named_pose("tools_cleaning")
            target_pose = self.calibration.pose_for_point(center_x, center_y, fallback_pose=fallback_pose)
            target_result = self.servos.move_pose(target_pose, smooth=True)
            ok = tool_result.ok and target_result.ok
            message = (
                "Limpieza superficial asistida posicionada. "
                "Mantener supervision y no ejercer presion sobre la obra."
            )
            result = {
                "ok": ok,
                "message": message if ok else f"{tool_result.message} {target_result.message}",
                "requires_human": False,
                "pose": target_pose,
            }
        else:
            assist_result = self.servos.apply_named_pose("tools_assist")
            result = {
                "ok": assist_result.ok,
                "message": (
                    "Accion critica: el robot solo posiciona herramienta/material al alcance. "
                    "La decision de restauracion queda en manos del especialista."
                ),
                "requires_human": True,
                "pose": assist_result.pose,
            }

        self.storage.log_action(
            session_id,
            "confirmed_action",
            {
                "detection_id": detection_id,
                "label": detection["label"],
                "action": detection["action"],
                "target_point": [round(center_x, 1), round(center_y, 1)],
                "result": result,
            },
            detection_id=detection_id,
        )
        return result

    def generate_report(self, session_id: int) -> dict[str, Any]:
        bundle = self.storage.session_bundle(session_id)
        path = self.reports.build_pdf(bundle)
        self.storage.log_action(session_id, "report_generated", {"path": str(path)})
        return {"path": str(path), "media_url": self.media_url(path)}

    def add_calibration_point(self, image_x: float, image_y: float, label: str = "") -> dict[str, Any]:
        point = self.calibration.add_point(image_x, image_y, self.servos.positions, label=label)
        return {"point": point.__dict__, "count": len(self.calibration.points)}

    def media_url(self, path: str | Path) -> str:
        resolved = Path(path).resolve()
        try:
            relative = resolved.relative_to(self.data_dir)
        except ValueError:
            return ""
        return "/media/" + relative.as_posix()
