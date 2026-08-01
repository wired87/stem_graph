"""Per-run graph and PDF artifacts for the precision-drug workflow."""
from __future__ import annotations

import json
import time
import uuid
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

import networkx as nx
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from firegraph.graph.visual import create_g_visual


FIREGRAPH_CLIENT_URL = "https://github.com/wired87/firegraph-client"
ALLOWED_ARTIFACTS = {
    "precision_drug_graph.json",
    "precision_drug_graph.html",
    "order.pdf",
    "process_sum.pdf",
}
_EXPORTS: dict[str, dict] = {}
_EXPORT_TTL_SECONDS = 60 * 60


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


def artifact_path(export_id: str, filename: str) -> Path | None:
    item = _EXPORTS.get(str(export_id))
    if not item or filename not in ALLOWED_ARTIFACTS:
        return None
    path = item["directory"] / filename
    return path if path.is_file() else None


def _json_safe(value):
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_json_safe(item) for item in value]
        return str(value)


def _graph_payload(graph) -> dict:
    return {
        "directed": graph.G.is_directed(),
        "multigraph": graph.G.is_multigraph(),
        "graph": _json_safe(dict(graph.G.graph)),
        "nodes": [
            {"id": str(node_id), **_json_safe(dict(attrs))}
            for node_id, attrs in graph.G.nodes(data=True)
        ],
        "links": [
            {"source": str(source), "target": str(target), **_json_safe(dict(attrs))}
            for source, target, attrs in graph.G.edges(data=True)
        ],
    }


def _page(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.black)
    canvas.setLineWidth(0.8)
    canvas.rect(13 * mm, 13 * mm, A4[0] - 26 * mm, A4[1] - 26 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(18 * mm, 17 * mm, "CNVMaster research export")
    canvas.drawRightString(A4[0] - 18 * mm, 17 * mm, f"page {document.page}")
    canvas.restoreState()


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "DocumentTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=23, leading=26, textColor=colors.black, alignment=TA_CENTER,
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        "SectionTitle", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=13, leading=16, textColor=colors.black, spaceBefore=8, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        "SmallBody", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=8.5, leading=12, textColor=colors.HexColor("#222222"),
    ))
    styles.add(ParagraphStyle(
        "FinePrint", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=7.5, leading=10, textColor=colors.HexColor("#444444"),
    ))
    return styles


def _document(path: Path, title: str):
    return SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=23 * mm,
        title=title,
        author="CNVMaster automated research workflow",
        subject="Research-only graph export",
    )


def _molecule_rows(graph, result: dict) -> list[dict]:
    rows = []
    for drug_id in dict.fromkeys(result.get("drug_ids", [])):
        attrs = dict(graph.G.nodes.get(drug_id, {}))
        scores = []
        for neighbor in graph.G.neighbors(drug_id):
            edge = graph.G.get_edge_data(drug_id, neighbor) or {}
            if graph.G.nodes[neighbor].get("type") == "TARGET":
                scores.append({
                    "target_id": str(neighbor),
                    "score": float(edge.get("score", 0.0)),
                })
        rows.append({
            "drug_id": str(drug_id),
            "name": attrs.get("pref_name") or "not supplied",
            "smiles": attrs.get("canonical_smiles") or "not supplied",
            "molfile": attrs.get("molfile") or "not supplied",
            "research_exposure_factor": attrs.get("research_exposure_factor", 0.0),
            "scores": scores,
        })
    return rows


def create_order_pdf(path: Path, graph, result: dict) -> None:
    styles = _styles()
    story = [
        Paragraph("Manual molecule ordering sheet", styles["DocumentTitle"]),
        Paragraph(
            "Research-only inventory generated from the completed precision-drug graph. "
            "Scores are computational evidence values and are not clinical doses, "
            "purchase instructions, or treatment recommendations.",
            styles["SmallBody"],
        ),
        Spacer(1, 6 * mm),
    ]
    molecules = _molecule_rows(graph, result)
    if not molecules:
        story.append(Paragraph("No eligible molecule nodes were selected.", styles["SectionTitle"]))
    for index, molecule in enumerate(molecules, start=1):
        score_rows = [["Target", "Calculated score"]] + [
            [row["target_id"], f"{row['score']:.8g}"] for row in molecule["scores"]
        ]
        score_table = Table(score_rows, colWidths=[92 * mm, 55 * mm], repeatRows=1)
        score_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.black),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([
            Paragraph(f"{index:02d} / {molecule['drug_id']}", styles["SectionTitle"]),
            Table([
                ["Preferred name", molecule["name"]],
                ["Research exposure factor", str(molecule["research_exposure_factor"])],
                ["Canonical SMILES", Paragraph(str(molecule["smiles"]), styles["FinePrint"])],
            ], colWidths=[48 * mm, 99 * mm], style=TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eeeeee")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 5),
            ])),
            Spacer(1, 4 * mm),
            score_table,
            Spacer(1, 4 * mm),
            Paragraph("MDL molfile", styles["SectionTitle"]),
            Preformatted(str(molecule["molfile"]), ParagraphStyle(
                "Molfile", fontName="Courier", fontSize=5.6, leading=6.8,
                borderColor=colors.black, borderWidth=0.6, borderPadding=7,
                backColor=colors.HexColor("#fafafa"),
            )),
        ])
        if index < len(molecules):
            story.append(PageBreak())
    story.extend([
        Spacer(1, 7 * mm),
        Paragraph(
            "Generated without personal information for manual research review; "
            "verify identity, purity, legal status, vendor documentation, and laboratory "
            "controls independently - greetings from botworld.cloud",
            styles["FinePrint"],
        ),
    ])
    _document(path, "Manual molecule ordering sheet").build(
        story, onFirstPage=_page, onLaterPages=_page
    )


def create_process_pdf(
    path: Path,
    graph,
    result: dict,
    pyvis_url: str,
    graph_url: str,
) -> None:
    styles = _styles()
    type_counts = Counter(
        str(attrs.get("type") or "UNKNOWN")
        for _, attrs in graph.G.nodes(data=True)
    )
    type_table = Table(
        [["Node type", "Count"]] + [[key, str(value)] for key, value in sorted(type_counts.items())],
        colWidths=[100 * mm, 47 * mm],
        repeatRows=1,
    )
    type_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story = [
        Paragraph("Precision-drug process summary", styles["DocumentTitle"]),
        Paragraph(
            "This document captures the completed research graph, its major workflow "
            "stages, and links to the full machine-readable and interactive views.",
            styles["SmallBody"],
        ),
        Spacer(1, 5 * mm),
        Table([
            ["Nodes", str(graph.G.number_of_nodes())],
            ["Edges", str(graph.G.number_of_edges())],
            ["Targets", str(len(result.get("target_ids", [])))],
            ["Selected molecules", str(len(set(result.get("drug_ids", []))))],
            ["Harmful variants", str(result.get("harmful_variant_count", 0))],
        ], colWidths=[78 * mm, 69 * mm], style=TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eeeeee")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])),
        Paragraph("Graph composition", styles["SectionTitle"]),
        type_table,
        Paragraph("Workflow functionality", styles["SectionTitle"]),
        Paragraph(
            "The workflow resolves ChEMBL targets from UniProt accessions, expands "
            "protein interactions through OmniPath, selects at most one eligible "
            "molecule neighbor per target, calculates signed target-response scores, "
            "propagates influence through the pathway graph, evaluates supplied VEP "
            "annotations conservatively, and returns dimensionless research exposure "
            "factors plus an ingredient matrix. It does not calculate a clinical dose.",
            styles["SmallBody"],
        ),
        Paragraph("Interactive PyVis component", styles["SectionTitle"]),
        Paragraph(
            f'<link href="{pyvis_url}" color="black"><u>Open the complete interactive '
            "PyVis graph</u></link>. Every node and edge from this run is included in "
            "the linked HTML component. The view supports zooming, dragging, tooltips, "
            "physics-based layout, and a node-type legend.",
            styles["SmallBody"],
        ),
        Paragraph(
            f'<link href="{graph_url}" color="black"><u>Download the NetworkX node-link '
            "JSON graph</u></link> for reproducible downstream processing.",
            styles["SmallBody"],
        ),
        Paragraph("firegraph-client repository", styles["SectionTitle"]),
        Paragraph(
            f'<link href="{FIREGRAPH_CLIENT_URL}" color="black"><u>firegraph-client</u></link> '
            "is an MIT-licensed React package for visualizing graph spectra in 3D. "
            "Its high-level GraphSpectrumViewer uses internal/default engine input. "
            "For explicit graph control, ThreeScene accepts node objects with IDs and "
            "3D positions plus edges whose endpoints reference existing node IDs. "
            "The package also exports node and edge color helpers and supports node "
            "selection, neighbor highlighting, external hover state, and edge highlighting.",
            styles["SmallBody"],
        ),
        Paragraph("Interpretation boundary", styles["SectionTitle"]),
        Paragraph(
            "The artifacts preserve research evidence and software output only. "
            "They are not evidence of regulatory approval, clinical safety, efficacy, "
            "product quality, or suitability for a patient.",
            styles["FinePrint"],
        ),
    ]
    _document(path, "Precision-drug process summary").build(
        story, onFirstPage=_page, onLaterPages=_page
    )


def build_artifacts(
    graph,
    result: dict,
    directory: Path,
    download_url,
) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    graph_path = directory / "precision_drug_graph.json"
    pyvis_path = directory / "precision_drug_graph.html"
    order_path = directory / "order.pdf"
    process_path = directory / "process_sum.pdf"

    graph_path.write_text(
        json.dumps(_graph_payload(graph), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    create_g_visual(graph.G, dest_path=str(pyvis_path), ds=False, add_legend=True)
    create_order_pdf(order_path, graph, result)
    create_process_pdf(
        process_path,
        graph,
        result,
        pyvis_url=download_url(pyvis_path.name),
        graph_url=download_url(graph_path.name),
    )
    return {
        "nx_graph": {"filename": graph_path.name, "url": download_url(graph_path.name)},
        "pyvis_graph": {"filename": pyvis_path.name, "url": download_url(pyvis_path.name)},
        "order_pdf": {"filename": order_path.name, "url": download_url(order_path.name)},
        "process_pdf": {"filename": process_path.name, "url": download_url(process_path.name)},
    }
