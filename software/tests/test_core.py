from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from chunche.calibration import CalibrationStore
from chunche.camera import SimulatedCamera
from chunche.config import load_config
from chunche.models import BoundingBox, Detection
from chunche.reports import ReportGenerator
from chunche.servo import SafeServoRig, SimServoBackend
from chunche.storage import Storage
from chunche.vision import HeuristicDamageDetector, annotate_image


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "hardware.yaml"


class ConfigAndServoTests(unittest.TestCase):
    def test_loads_hardware_config(self) -> None:
        config = load_config(CONFIG)
        self.assertEqual(config.pca9685_address, 0x40)
        self.assertIn("base", config.servos)
        self.assertEqual(config.servos["pinza"].channel, 5)

    def test_servo_limits_are_enforced(self) -> None:
        config = load_config(CONFIG)
        rig = SafeServoRig(config, SimServoBackend())
        result = rig.move_servo("base", 90, smooth=False)
        self.assertTrue(result.ok)
        result = rig.move_servo("base", 999, smooth=False)
        self.assertFalse(result.ok)
        self.assertIn("fuera de rango", result.message)

    def test_emergency_stop_blocks_motion(self) -> None:
        config = load_config(CONFIG)
        rig = SafeServoRig(config, SimServoBackend())
        rig.emergency_stop()
        result = rig.move_servo("base", 80, smooth=False)
        self.assertFalse(result.ok)
        self.assertIn("parada", result.message.lower())


class VisionStorageReportTests(unittest.TestCase):
    def test_simulated_capture_detects_and_reports(self) -> None:
        config = load_config(CONFIG)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image_path = tmp_path / "capture.jpg"
            SimulatedCamera(1280, 720).capture(image_path)

            detector = HeuristicDamageDetector(confidence_threshold=0.55)
            detections = detector.analyze(image_path)
            self.assertTrue(detections)
            labels = {det.label for det in detections}
            self.assertTrue({"grieta", "perdida_pigmento", "suciedad_superficial"} & labels)

            annotated = annotate_image(image_path, detections, tmp_path / "annotated.jpg")
            self.assertTrue(annotated.exists())

            storage = Storage(tmp_path / "chunche.sqlite3")
            session = storage.create_session("obra-test", "tester")
            image_id = storage.add_image(session.id, "initial", image_path, 1280, 720)
            annotated_id = storage.add_image(session.id, "annotated", annotated, 1280, 720)
            self.assertGreater(annotated_id, image_id)
            for det in detections:
                storage.add_detection(session.id, image_id, det, 1280, 720)
            storage.log_action(session.id, "analysis", {"detections": len(detections)})

            report = ReportGenerator(tmp_path / "reports").build_pdf(storage.session_bundle(session.id))
            self.assertTrue(report.exists())
            self.assertGreater(report.stat().st_size, 1000)
            self.assertEqual(config.confidence_threshold, 0.65)

    def test_polygon_detection_is_saved_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image_path = tmp_path / "capture.jpg"
            SimulatedCamera(640, 360).capture(image_path)
            polygon = [(100, 80), (220, 90), (210, 170), (120, 160)]
            detection = Detection(
                label="suciedad_superficial",
                confidence=0.91,
                box=BoundingBox(100, 80, 120, 90),
                polygon=polygon,
                area_pixels=9600,
                action="limpieza_controlada",
                recommendation="Puede ejecutarse limpieza superficial lenta y supervisada.",
                source="yolo",
            )
            annotated = annotate_image(image_path, [detection], tmp_path / "annotated.jpg")
            storage = Storage(tmp_path / "chunche.sqlite3")
            session = storage.create_session("obra-mask", "tester")
            image_id = storage.add_image(session.id, "initial", image_path, 640, 360)
            storage.add_image(session.id, "annotated", annotated, 640, 360)
            storage.add_detection(session.id, image_id, detection, 640, 360)

            stored = storage.list_detections(session.id)[0]
            self.assertEqual(stored["polygon"], [[100, 80], [220, 90], [210, 170], [120, 160]])
            self.assertEqual(stored["area_pixels"], 9600)
            report = ReportGenerator(tmp_path / "reports").build_pdf(storage.session_bundle(session.id))
            self.assertTrue(report.exists())


class CalibrationTests(unittest.TestCase):
    def test_calibration_interpolates_pose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CalibrationStore(Path(tmp) / "calibration.json")
            store.add_point(0, 0, {"base": 60, "hombro": 80}, "a")
            store.add_point(100, 0, {"base": 120, "hombro": 100}, "b")
            pose = store.pose_for_point(50, 0, {"base": 90, "hombro": 90})
            self.assertGreater(pose["base"], 60)
            self.assertLess(pose["base"], 120)
            self.assertIn("hombro", pose)


if __name__ == "__main__":
    unittest.main()
