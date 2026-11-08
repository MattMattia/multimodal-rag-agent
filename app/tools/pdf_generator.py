import io
import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("uploads/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def execute_generate_report_pdf(
    title: str,
    summary: str,
    key_points: list[str] | None = None,
    sections: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Genera un informe ejecutivo profesional en formato PDF utilizando ReportLab.

    Args:
        title: Título principal del reporte.
        summary: Párrafo de resumen ejecutivo.
        key_points: Lista opcional de viñetas con puntos o conclusiones clave.
        sections: Lista opcional de secciones adicionales (cada una con 'heading' y 'content').

    Returns:
        Diccionario con filename, file_path, download_url y status.
    """
    logger.info("Generando reporte ejecutivo en PDF: '%s'", title)

    # Sanitizar título para nombre de archivo
    safe_title = re.sub(r"[^\w\-_\. ]", "_", title).strip().replace(" ", "_")[:40]
    unique_id = str(uuid.uuid4())[:8]
    filename = f"reporte_{unique_id}_{safe_title}.pdf"
    file_path = REPORTS_DIR / filename

    # Configuración del documento ReportLab
    doc = SimpleDocTemplate(
        str(file_path),
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    # Estilos tipográficos profesionales
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=10,
    )
    date_style = ParagraphStyle(
        "ReportDate",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=20,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=14,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#334155"),
        spaceAfter=10,
    )
    bullet_style = ParagraphStyle(
        "ReportBullet",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
        leftIndent=15,
        spaceAfter=4,
    )

    elements = []

    # 1. Cabecera y Título
    elements.append(Paragraph(escape(title), title_style))
    current_time_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    elements.append(Paragraph(f"Generado automáticamente por Agente IA Autónomo | Fecha: {current_time_str}", date_style))
    elements.append(Spacer(1, 10))

    # 2. Resumen Ejecutivo
    elements.append(Paragraph("Resumen Ejecutivo", heading_style))
    elements.append(Paragraph(escape(summary).replace("\n", "<br/>"), body_style))
    elements.append(Spacer(1, 10))

    # 3. Puntos Clave
    if key_points:
        elements.append(Paragraph("Conclusiones y Puntos Clave", heading_style))
        for point in key_points:
            elements.append(Paragraph(f"• {escape(point)}", bullet_style))
        elements.append(Spacer(1, 10))

    # 4. Secciones Adicionales
    if sections:
        for sec in sections:
            sec_heading = sec.get("heading", "Sección")
            sec_content = sec.get("content", "")
            elements.append(Paragraph(escape(sec_heading), heading_style))
            elements.append(Paragraph(escape(sec_content).replace("\n", "<br/>"), body_style))
            elements.append(Spacer(1, 10))

    # 5. Pie de página decorativo
    elements.append(Spacer(1, 20))
    footer_data = [["Sistema RAG Multimodal & Agente IA Autónomo - Documento Confidencial"]]
    footer_table = Table(footer_data, colWidths=[530])
    footer_table.setStyle(
        TableStyle(
            [
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#94a3b8")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Oblique"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LINEABOVE", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(footer_table)

    # Construir PDF
    doc.build(elements)
    logger.info("Reporte PDF generado exitosamente en %s", file_path)

    return {
        "status": "success",
        "filename": filename,
        "file_path": str(file_path),
        "download_url": f"/uploads/reports/{filename}",
        "message": f"Reporte PDF '{title}' generado exitosamente.",
    }



def build_conversation_pdf(session_id: uuid.UUID, messages: list[dict[str, Any]]) -> bytes:
    """Maqueta una conversación completa (mensajes, citas y herramientas) como PDF ejecutivo en memoria.

    Síncrona (CPU): ejecutar con asyncio.to_thread. Todo el texto se escapa para ReportLab.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ConvTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18,
        textColor=colors.HexColor("#1e293b"), spaceAfter=6,
    )
    meta_style = ParagraphStyle(
        "ConvMeta", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#64748b"), spaceAfter=12
    )
    role_style = ParagraphStyle(
        "ConvRole", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=11,
        textColor=colors.HexColor("#0f172a"), spaceBefore=10, spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "ConvBody", parent=styles["Normal"], fontSize=10, leading=14,
        textColor=colors.HexColor("#334155"), spaceAfter=6,
    )
    small_style = ParagraphStyle(
        "ConvSmall", parent=body_style, fontSize=8.5, leading=11, leftIndent=12,
        textColor=colors.HexColor("#475569"), spaceAfter=2,
    )

    elements: list[Any] = [
        Paragraph("Conversación con el Agente IA", title_style),
        Paragraph(
            escape(f"Sesión {session_id} | Exportado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"),
            meta_style,
        ),
    ]
    for msg in messages:
        role_label = {"user": "Usuario", "assistant": "Agente"}.get(msg["role"], str(msg["role"]))
        elements.append(Paragraph(escape(role_label), role_style))
        elements.append(Paragraph(escape(msg["content"]).replace("\n", "<br/>"), body_style))
        for cit in msg.get("citations") or []:
            page = f", Pág {cit['page_number']}" if cit.get("page_number") else ""
            elements.append(Paragraph(escape(f"Fuente: {cit.get('document_name', '?')}{page}"), small_style))
        for tool in msg.get("executed_tools") or []:
            args = json.dumps(tool.get("tool_input", {}), ensure_ascii=False, default=str)[:200]
            elements.append(Paragraph(escape(f"Herramienta: {tool.get('tool_name', '?')} {args}"), small_style))

    doc.build(elements)
    return buffer.getvalue()
