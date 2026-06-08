from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Entrena YOLO-seg para suciedad superficial de Chunche.")
    parser.add_argument("--data", required=True, help="Ruta a data.yaml exportado desde Roboflow/CVAT")
    parser.add_argument("--model", default="yolo11n-seg.pt", help="Modelo base de Ultralytics")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--name", default="chunche_suciedad_seg")
    parser.add_argument("--project", default="runs/segment")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = Path(args.data)
    if not data.exists():
        raise SystemExit(f"No existe data.yaml: {data}")
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Instala Ultralytics primero: pip install -r requirements-yolo.txt") from exc

    model = YOLO(args.model)
    model.train(
        data=str(data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        patience=20,
        project=args.project,
        name=args.name,
    )
    print(f"Modelo entrenado. Busca best.pt en {args.project}/{args.name}/weights/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

