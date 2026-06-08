from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


class ReportGenerator:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_pdf(self, bundle: dict[str, Any]) -> Path:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError as exc:  # pragma: no cover - reportlab is expected in requirements
            raise RuntimeError("reportlab es requerido para generar PDF") from exc

        session = bundle["session"]
        path = self.output_dir / f"reporte_sesion_{session['id']}.pdf"
        doc = SimpleDocTemplate(str(path), pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()
        story: list[Any] = []

        story.append(Paragraph("Reporte de conservacion - Chunche", styles["Title"]))
        story.append(Paragraph(f"Obra: {session['work_id']}", styles["Heading2"]))
        story.append(Paragraph(f"Operador: {session['operator']}", styles["Normal"]))
        story.append(Paragraph(f"Sesion: {session['id']} | Fecha: {session['created_at']}", styles["Normal"]))
        if session.get("notes"):
            story.append(Paragraph(f"Notas: {session['notes']}", styles["Normal"]))
        story.append(Spacer(1, 0.18 * inch))

        annotated = next((img for img in reversed(bundle["images"]) if img["kind"] == "annotated"), None)
        if annotated and Path(annotated["path"]).exists():
            story.append(Paragraph("Imagen anotada", styles["Heading2"]))
            story.append(Image(annotated["path"], width=6.2 * inch, height=3.5 * inch, kind="proportional"))
            story.append(Spacer(1, 0.15 * inch))

        story.append(Paragraph("Detecciones", styles["Heading2"]))
        detections = bundle["detections"]
        if detections:
            data = [["ID", "Tipo", "Conf.", "Cuadrante", "Area", "Accion"]]
            for det in detections:
                area = f"{float(det['area_pixels']):.0f} px" if det.get("area_pixels") is not None else "-"
                data.append(
                    [
                        str(det["id"]),
                        det["label"].replace("_", " "),
                        f"{float(det['confidence']):.2f}",
                        det["quadrant"],
                        area,
                        det["action"].replace("_", " "),
                    ]
                )
            table = Table(
                data,
                hAlign="LEFT",
                colWidths=[0.35 * inch, 1.25 * inch, 0.55 * inch, 1.15 * inch, 0.75 * inch, 1.55 * inch],
            )
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story.append(table)
        else:
            story.append(Paragraph("No se registraron detecciones sobre el umbral configurado.", styles["Normal"]))
        story.append(Spacer(1, 0.18 * inch))

        story.append(Paragraph("Acciones registradas", styles["Heading2"]))
        actions = bundle["actions"]
        if actions:
            for action in actions:
                created = action.get("created_at", "")
                story.append(Paragraph(f"{created} - {action['action_type']}: {action['details']}", styles["Normal"]))
        else:
            story.append(Paragraph("No se ejecutaron acciones fisicas durante la sesion.", styles["Normal"]))

        story.append(Spacer(1, 0.18 * inch))
        story.append(
            Paragraph(
                "Nota de seguridad: las intervenciones criticas requieren validacion humana. "
                "Este reporte documenta asistencia y sugerencias del prototipo.",
                styles["Italic"],
            )
        )
        story.append(Paragraph(f"Generado: {datetime.now().isoformat(timespec='seconds')}", styles["Normal"]))
        doc.build(story)
        return path
