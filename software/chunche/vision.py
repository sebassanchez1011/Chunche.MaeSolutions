from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .models import BoundingBox, Detection, polygon_area


ACTION_BY_LABEL = {
    "grieta": "asistencia_restaurador",
    "perdida_pigmento": "asistencia_restaurador",
    "suciedad_superficial": "limpieza_controlada",
    "deformacion_soporte": "asistencia_restaurador",
    "degradacion_capa_pictorica": "asistencia_restaurador",
}

RECOMMENDATION_BY_LABEL = {
    "grieta": "No intervenir automaticamente. Presentar herramienta y zona al restaurador.",
    "perdida_pigmento": "Requiere revision humana antes de cualquier material de restauracion.",
    "suciedad_superficial": "Puede ejecutarse limpieza superficial lenta y supervisada.",
    "deformacion_soporte": "Documentar y solicitar validacion del especialista.",
    "degradacion_capa_pictorica": "Asistir con documentacion y material al alcance del restaurador.",
}


class HeuristicDamageDetector:
    def __init__(self, confidence_threshold: float = 0.65):
        self.confidence_threshold = confidence_threshold

    def analyze(self, image_path: str | Path) -> list[Detection]:
        img = Image.open(image_path).convert("RGB")
        arr = np.asarray(img.resize((640, 640)))
        gray = arr.mean(axis=2)
        max_channel = arr.max(axis=2).astype(float)
        min_channel = arr.min(axis=2).astype(float)
        saturation = max_channel - min_channel

        detections: list[Detection] = []
        dark_mask = gray < np.percentile(gray, 8)
        light_mask = (gray > 222) & (gray < 236) & (saturation < 60)

        dark_components = self._components(dark_mask)
        detections.extend(self._crack_detections(dark_components, img.size, max_items=2))
        detections.extend(self._area_detections(light_mask, "perdida_pigmento", img.size, min_area=350, max_items=2))
        dust_detection = self._dust_detection(dark_components, img.size)
        if dust_detection:
            detections.append(dust_detection)

        unique = self._dedupe(detections)
        return [det for det in unique if det.confidence >= self.confidence_threshold]

    def _components(self, mask: np.ndarray) -> list[dict[str, int]]:
        height, width = mask.shape
        visited = np.zeros(mask.shape, dtype=bool)
        components: list[dict[str, int]] = []
        ys, xs = np.where(mask)
        true_points = set(zip(xs.tolist(), ys.tolist()))

        for start_x, start_y in list(true_points):
            if visited[start_y, start_x]:
                continue
            stack = [(start_x, start_y)]
            visited[start_y, start_x] = True
            min_x = max_x = start_x
            min_y = max_y = start_y
            area = 0
            while stack:
                x, y = stack.pop()
                area += 1
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    if visited[ny, nx] or not mask[ny, nx]:
                        continue
                    visited[ny, nx] = True
                    stack.append((nx, ny))
            components.append({"x": min_x, "y": min_y, "w": max_x - min_x + 1, "h": max_y - min_y + 1, "area": area})
        return components

    def _box_from_component(self, component: dict[str, int], image_size: tuple[int, int]) -> BoundingBox:
        scale_x = image_size[0] / 640
        scale_y = image_size[1] / 640
        pad = 10
        x = max(0, component["x"] - pad)
        y = max(0, component["y"] - pad)
        w = min(640 - x, component["w"] + pad * 2)
        h = min(640 - y, component["h"] + pad * 2)
        return BoundingBox(
            x=int(x * scale_x),
            y=int(y * scale_y),
            width=max(8, int(w * scale_x)),
            height=max(8, int(h * scale_y)),
        )

    def _crack_detections(
        self,
        components: list[dict[str, int]],
        image_size: tuple[int, int],
        max_items: int,
    ) -> list[Detection]:
        candidates: list[tuple[float, BoundingBox]] = []
        for component in components:
            area = component["area"]
            w = component["w"]
            h = component["h"]
            if area < 120:
                continue
            elongation = max(w, h) / max(1, min(w, h))
            if elongation < 1.7:
                continue
            confidence = min(0.98, 0.68 + area / 1200)
            candidates.append((confidence, self._box_from_component(component, image_size)))
        detections: list[Detection] = []
        for confidence, box in sorted(candidates, key=lambda item: item[0], reverse=True)[:max_items]:
            detections.append(
                Detection(
                    label="grieta",
                    confidence=confidence,
                    box=box,
                    action=ACTION_BY_LABEL["grieta"],
                    recommendation=RECOMMENDATION_BY_LABEL["grieta"],
                    source="heuristic",
                )
            )
        return detections

    def _area_detections(
        self,
        mask: np.ndarray,
        label: str,
        image_size: tuple[int, int],
        min_area: int,
        max_items: int,
    ) -> list[Detection]:
        candidates: list[tuple[float, BoundingBox]] = []
        for component in self._components(mask):
            if component["area"] < min_area:
                continue
            elongation = max(component["w"], component["h"]) / max(1, min(component["w"], component["h"]))
            if elongation > 6 or component["w"] > 260 or component["h"] > 260:
                continue
            confidence = min(0.93, 0.66 + component["area"] / 6000)
            candidates.append((confidence, self._box_from_component(component, image_size)))
        return [
            Detection(
                label=label,
                confidence=confidence,
                box=box,
                action=ACTION_BY_LABEL[label],
                recommendation=RECOMMENDATION_BY_LABEL[label],
                source="heuristic",
            )
            for confidence, box in sorted(candidates, key=lambda item: item[0], reverse=True)[:max_items]
        ]

    def _dust_detection(self, components: list[dict[str, int]], image_size: tuple[int, int]) -> Detection | None:
        small = [item for item in components if 1 <= item["area"] <= 45]
        if len(small) < 18:
            return None
        min_x = min(item["x"] for item in small)
        min_y = min(item["y"] for item in small)
        max_x = max(item["x"] + item["w"] for item in small)
        max_y = max(item["y"] + item["h"] for item in small)
        component = {"x": min_x, "y": min_y, "w": max_x - min_x, "h": max_y - min_y, "area": len(small)}
        confidence = min(0.90, 0.64 + len(small) / 120)
        return Detection(
            label="suciedad_superficial",
            confidence=confidence,
            box=self._box_from_component(component, image_size),
            action=ACTION_BY_LABEL["suciedad_superficial"],
            recommendation=RECOMMENDATION_BY_LABEL["suciedad_superficial"],
            source="heuristic",
        )

    def _dedupe(self, detections: Iterable[Detection]) -> list[Detection]:
        result: list[Detection] = []
        for det in sorted(detections, key=lambda item: item.confidence, reverse=True):
            if any(det.label == old.label and _iou(det.box, old.box) > 0.25 for old in result):
                continue
            result.append(det)
        return result


class YoloDamageDetector:
    def __init__(self, model_path: str | Path, confidence_threshold: float = 0.65):
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        try:
            from ultralytics import YOLO  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional path
            raise RuntimeError("Instala requirements-yolo.txt para activar YOLO.") from exc
        if not self.model_path.exists():
            raise FileNotFoundError(f"Modelo YOLO no encontrado: {self.model_path}")
        self.model = YOLO(str(self.model_path))

    def analyze(self, image_path: str | Path) -> list[Detection]:
        results = self.model.predict(source=str(image_path), conf=self.confidence_threshold, imgsz=640, verbose=False)
        detections: list[Detection] = []
        for result in results:
            names = result.names
            masks_xy = result.masks.xy if getattr(result, "masks", None) is not None else []
            for idx, box in enumerate(result.boxes):
                cls = int(box.cls[0])
                label = _normalize_label(str(names.get(cls, cls)))
                xyxy = box.xyxy[0].tolist()
                x0, y0, x1, y1 = [int(v) for v in xyxy]
                polygon = _mask_polygon(masks_xy[idx]) if idx < len(masks_xy) else None
                bbox = _box_from_polygon(polygon) if polygon else BoundingBox(
                    x=x0,
                    y=y0,
                    width=max(1, x1 - x0),
                    height=max(1, y1 - y0),
                )
                detections.append(
                    Detection(
                        label=label,
                        confidence=float(box.conf[0]),
                        box=bbox,
                        action=ACTION_BY_LABEL.get(label, "asistencia_restaurador"),
                        recommendation=RECOMMENDATION_BY_LABEL.get(label, "Validar con el restaurador."),
                        source="yolo",
                        polygon=polygon,
                        area_pixels=polygon_area(polygon) if polygon else None,
                    )
                )
        return detections


def create_detector(config) -> HeuristicDamageDetector | YoloDamageDetector:
    if config.yolo_enabled:
        return YoloDamageDetector(config.yolo_model_path, confidence_threshold=config.confidence_threshold)
    return HeuristicDamageDetector(confidence_threshold=config.confidence_threshold)


def annotate_image(input_path: str | Path, detections: list[Detection], output_path: str | Path) -> Path:
    img = Image.open(input_path).convert("RGB")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    palette = {
        "grieta": "#ef4444",
        "perdida_pigmento": "#f59e0b",
        "suciedad_superficial": "#2563eb",
        "deformacion_soporte": "#7c3aed",
        "degradacion_capa_pictorica": "#be123c",
    }
    for det in detections:
        color = palette.get(det.label, "#22c55e")
        if det.polygon:
            rgb = _hex_to_rgb(color)
            overlay_draw.polygon(det.polygon, fill=(*rgb, 70), outline=(*rgb, 220))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)
    for det in detections:
        color = palette.get(det.label, "#22c55e")
        x0, y0 = det.box.x, det.box.y
        x1, y1 = det.box.x + det.box.width, det.box.y + det.box.height
        draw.rectangle((x0, y0, x1, y1), outline=color, width=4)
        label = f"{det.label} {det.confidence:.2f}"
        text_box = draw.textbbox((x0, max(0, y0 - 24)), label, font=font)
        draw.rectangle(text_box, fill=color)
        draw.text((x0, max(0, y0 - 24)), label, fill="white", font=font)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, quality=95)
    return path


def _iou(a: BoundingBox, b: BoundingBox) -> float:
    ax1, ay1 = a.x + a.width, a.y + a.height
    bx1, by1 = b.x + b.width, b.y + b.height
    x0, y0 = max(a.x, b.x), max(a.y, b.y)
    x1, y1 = min(ax1, bx1), min(ay1, by1)
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    union = a.width * a.height + b.width * b.height - inter
    return inter / union if union else 0.0


def _normalize_label(label: str) -> str:
    value = label.lower().strip().replace(" ", "_").replace("-", "_")
    aliases = {
        "crack": "grieta",
        "grieta": "grieta",
        "pigment_loss": "perdida_pigmento",
        "perdida_pigmento": "perdida_pigmento",
        "dust": "suciedad_superficial",
        "dirt": "suciedad_superficial",
        "dirty": "suciedad_superficial",
        "soil": "suciedad_superficial",
        "stain": "suciedad_superficial",
        "surface_dirt": "suciedad_superficial",
        "suciedad": "suciedad_superficial",
        "suciedad_superficial": "suciedad_superficial",
        "deformation": "deformacion_soporte",
        "paint_layer": "degradacion_capa_pictorica",
    }
    return aliases.get(value, value)


def _mask_polygon(raw_points, max_points: int = 120) -> list[tuple[int, int]] | None:
    points = [(int(round(float(x))), int(round(float(y)))) for x, y in raw_points.tolist()]
    points = [point for idx, point in enumerate(points) if idx == 0 or point != points[idx - 1]]
    if len(points) < 3:
        return None
    if len(points) <= max_points:
        return points
    stride = max(1, int(np.ceil(len(points) / max_points)))
    simplified = points[::stride]
    return simplified if len(simplified) >= 3 else points[:max_points]


def _box_from_polygon(points: list[tuple[int, int]]) -> BoundingBox:
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    x0, y0 = min(xs), min(ys)
    x1, y1 = max(xs), max(ys)
    return BoundingBox(x=x0, y=y0, width=max(1, x1 - x0), height=max(1, y1 - y0))


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
