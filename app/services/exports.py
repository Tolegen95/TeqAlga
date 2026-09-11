from __future__ import annotations

import csv
import json
from pathlib import Path
from xml.sax.saxutils import escape

from app.models import MeetingResult


def export_json(result: MeetingResult, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destination


def export_csv(result: MeetingResult, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["owner", "task", "due_date", "priority", "evidence"],
        )
        writer.writeheader()
        for item in result.report.action_items:
            writer.writerow(
                {
                    "owner": item.owner or "Не указан",
                    "task": item.task,
                    "due_date": item.due_date or "Не указан",
                    "priority": item.priority,
                    "evidence": ", ".join(item.evidence),
                }
            )
    return destination


def _format_time(seconds: float) -> str:
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def export_pdf(result: MeetingResult, destination: Path) -> Path:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError("reportlab is required for PDF export") from exc

    destination.parent.mkdir(parents=True, exist_ok=True)
    font_name = "Helvetica"
    bold_name = "Helvetica-Bold"
    regular_font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bold_font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if regular_font.exists() and bold_font.exists():
        pdfmetrics.registerFont(TTFont("DejaVu", str(regular_font)))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(bold_font)))
        font_name, bold_name = "DejaVu", "DejaVu-Bold"

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "LocalTitle",
        parent=styles["Title"],
        fontName=bold_name,
        textColor=colors.HexColor("#12324A"),
        fontSize=20,
        leading=24,
        spaceAfter=8 * mm,
    )
    heading = ParagraphStyle(
        "LocalHeading",
        parent=styles["Heading2"],
        fontName=bold_name,
        textColor=colors.HexColor("#0E7490"),
        fontSize=13,
        leading=16,
        spaceBefore=5 * mm,
        spaceAfter=2 * mm,
    )
    body = ParagraphStyle(
        "LocalBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9.5,
        leading=13,
        alignment=TA_LEFT,
        spaceAfter=1.5 * mm,
    )

    doc = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=result.metadata.title,
    )
    story = [
        Paragraph(escape(result.metadata.title), title_style),
        Paragraph(
            f"Файл: {escape(result.metadata.source_filename)} | "
            f"Спикеров: {result.metadata.speaker_count} | "
            f"Модель: {escape(result.metadata.llm_model)}",
            body,
        ),
        Paragraph("Краткая выжимка", heading),
    ]
    for item in result.report.executive_summary:
        story.append(Paragraph(f"• {escape(item.text)}", body))

    story.append(Paragraph("Ключевые факты", heading))
    for item in result.report.key_facts:
        story.append(Paragraph(f"• {escape(item.text)} [{', '.join(item.evidence)}]", body))

    story.append(Paragraph("Принятые решения", heading))
    for item in result.report.decisions:
        story.append(Paragraph(f"• {escape(item.text)}", body))

    story.append(Paragraph("Поручения", heading))
    table_data = [["Ответственный", "Задача", "Срок", "Приоритет"]]
    for item in result.report.action_items:
        table_data.append(
            [
                Paragraph(escape(item.owner or "Не указан"), body),
                Paragraph(escape(item.task), body),
                Paragraph(escape(item.due_date or "Не указан"), body),
                Paragraph(escape(item.priority), body),
            ]
        )
    table = Table(table_data, colWidths=[34 * mm, 85 * mm, 30 * mm, 25 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), bold_name),
                ("FONTNAME", (0, 1), (-1, -1), font_name),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0E7490")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([table, Paragraph("Открытые вопросы", heading)])
    for item in result.report.open_questions:
        story.append(Paragraph(f"• {escape(item.text)}", body))

    story.extend([PageBreak(), Paragraph("Полная расшифровка", title_style)])
    for segment in result.transcript:
        source_label = (
            _format_time(segment.start) if result.metadata.timestamps_precise else segment.id
        )
        story.append(
            Paragraph(
                f"[{escape(source_label)}] <b>{escape(segment.speaker)}:</b> "
                f"{escape(segment.text)}",
                body,
            )
        )

    doc.build(story)
    return destination


def export_result(result: MeetingResult, destination: Path, file_format: str) -> Path:
    exporters = {"json": export_json, "csv": export_csv, "pdf": export_pdf}
    try:
        exporter = exporters[file_format]
    except KeyError as exc:
        raise ValueError(f"Unsupported export format: {file_format}") from exc
    return exporter(result, destination)
