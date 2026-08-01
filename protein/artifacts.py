"""Temporary PDF artifacts for protein workflow responses."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


_EXPORTS: dict[str, dict] = {}
_EXPORT_TTL_SECONDS = 60 * 60
_FINGERPRINT_DOMAIN = "botworld.cloud"


def response_fingerprint(response_object: dict) -> str:
    canonical = json.dumps(
        response_object, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(f"{_FINGERPRINT_DOMAIN}\n{canonical}".encode("utf-8")).hexdigest()


def register_export(temp_store: TemporaryDirectory) -> str:
    now = time.time()
    for export_id, item in list(_EXPORTS.items()):
        if now - item["created"] > _EXPORT_TTL_SECONDS:
            item["temp_store"].cleanup()
            del _EXPORTS[export_id]
    export_id = uuid.uuid4().hex
    _EXPORTS[export_id] = {
        "created": now,
        "temp_store": temp_store,
        "directory": Path(temp_store.name),
    }
    return export_id


def artifact_path(export_id: str) -> Path | None:
    item = _EXPORTS.get(str(export_id))
    if not item:
        return None
    path = item["directory"] / "aum.pdf"
    return path if path.is_file() else None


def _flatten(value, path="$"):
    if isinstance(value, dict):
        if not value:
            yield path, "{}"
        for key, item in value.items():
            yield from _flatten(item, f"{path}.{key}")
    elif isinstance(value, list):
        if not value:
            yield path, "[]"
        for index, item in enumerate(value):
            yield from _flatten(item, f"{path}[{index}]")
    else:
        yield path, json.dumps(value, ensure_ascii=False, default=str)


def _page(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.black)
    canvas.setLineWidth(0.8)
    canvas.rect(13 * mm, 13 * mm, A4[0] - 26 * mm, A4[1] - 26 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(18 * mm, 17 * mm, "botworld.cloud response fingerprint")
    canvas.drawRightString(A4[0] - 18 * mm, 17 * mm, f"page {document.page}")
    canvas.restoreState()


def create_aum_pdf(path: Path, response_object: dict) -> str:
    fingerprint = response_fingerprint(response_object)
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "AumTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=23, leading=27, textColor=colors.black, spaceAfter=10,
    )
    body = ParagraphStyle(
        "AumBody", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=8.5, leading=12, textColor=colors.HexColor("#222222"),
    )
    key_style = ParagraphStyle(
        "AumKey", parent=body, fontName="Courier-Bold", fontSize=6.7, leading=9,
    )
    value_style = ParagraphStyle(
        "AumValue", parent=body, fontName="Courier", fontSize=6.7, leading=9,
        wordWrap="CJK",
    )
    rows = [["Response path", "Value"]]
    for key, value in _flatten(response_object):
        rows.append([
            Paragraph(escape(str(key)), key_style),
            Paragraph(escape(str(value)).replace("\n", "<br/>"), value_style),
        ])
    table = Table(rows, colWidths=[62 * mm, 85 * mm], repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f6f6")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story = [
        Paragraph("AUM - protein workflow response", title),
        Paragraph(
            "Complete field-level representation of the workflow-specific response object. "
            "The fingerprint is deterministic: SHA-256 over the canonical JSON response, "
            "namespaced with botworld.cloud.",
            body,
        ),
        Spacer(1, 4 * mm),
        Table(
            [
                ["Fingerprint", Paragraph(fingerprint, value_style)],
                ["Algorithm", "SHA-256"],
                ["Namespace", _FINGERPRINT_DOMAIN],
                ["Leaf entries", str(len(rows) - 1)],
            ],
            colWidths=[38 * mm, 109 * mm],
            style=TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eeeeee")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]),
        ),
        Spacer(1, 5 * mm),
        Paragraph("Response entries", styles["Heading2"]),
        table,
    ]
    document = SimpleDocTemplate(
        str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=23 * mm, title="AUM protein workflow response",
        author="botworld.cloud automated workflow", subject="Protein response export",
    )
    document.build(story, onFirstPage=_page, onLaterPages=_page)
    return fingerprint
