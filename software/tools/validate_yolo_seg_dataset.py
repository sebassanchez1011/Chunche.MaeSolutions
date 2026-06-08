from __future__ import annotations

import argparse
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida un dataset YOLO-seg de una clase para Chunche.")
    parser.add_argument("dataset", help="Carpeta que contiene data.yaml, images/ y labels/")
    parser.add_argument("--class-name", default="suciedad_superficial")
    return parser.parse_args()


def read_data_yaml(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"No existe {path}")
    return path.read_text(encoding="utf-8")


def image_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.suffix.lower() in IMAGE_EXTENSIONS)


def label_for_image(dataset: Path, image: Path) -> Path:
    parts = list(image.relative_to(dataset).parts)
    if "images" in parts:
        parts[parts.index("images")] = "labels"
    return (dataset / Path(*parts)).with_suffix(".txt")


def validate_label_file(path: Path) -> tuple[int, list[str]]:
    if not path.exists():
        return 0, []
    warnings: list[str] = []
    count = 0
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        values = line.split()
        if len(values) < 7 or len(values[1:]) % 2 != 0:
            warnings.append(f"{path}:{line_number} no parece etiqueta de segmentacion YOLO")
            continue
        try:
            class_id = int(values[0])
            coords = [float(value) for value in values[1:]]
        except ValueError:
            warnings.append(f"{path}:{line_number} contiene valores no numericos")
            continue
        if class_id != 0:
            warnings.append(f"{path}:{line_number} usa clase {class_id}; para MVP debe ser 0")
        if any(value < 0 or value > 1 for value in coords):
            warnings.append(f"{path}:{line_number} tiene coordenadas fuera de 0..1")
        if len(coords) < 6:
            warnings.append(f"{path}:{line_number} necesita al menos 3 puntos")
        count += 1
    return count, warnings


def main() -> int:
    args = parse_args()
    dataset = Path(args.dataset).resolve()
    yaml_text = read_data_yaml(dataset / "data.yaml")
    if args.class_name not in yaml_text:
        print(f"AVISO: data.yaml no menciona la clase esperada: {args.class_name}")

    images = image_files(dataset / "images")
    if not images:
        raise SystemExit("No se encontraron imagenes dentro de images/")

    images_with_masks = 0
    clean_images = 0
    warnings: list[str] = []
    for image in images:
        label_path = label_for_image(dataset, image)
        count, label_warnings = validate_label_file(label_path)
        warnings.extend(label_warnings)
        if count:
            images_with_masks += 1
        else:
            clean_images += 1

    print(f"Dataset: {dataset}")
    print(f"Imagenes: {len(images)}")
    print(f"Imagenes con mascaras: {images_with_masks}")
    print(f"Imagenes limpias/sin etiqueta: {clean_images}")
    print(f"Advertencias: {len(warnings)}")
    for warning in warnings[:30]:
        print(" -", warning)
    if len(warnings) > 30:
        print(f" - ... {len(warnings) - 30} advertencias mas")
    return 1 if warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())

