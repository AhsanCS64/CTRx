"""Utility to render a Rental Identity Certificate PDF.

The implementation is intentionally simple and placeholder‑style:

1. It generates a QR code PNG (bytes) using ``segno`` with the URL
   ``{VERIFY_BASE_URL}/{verify_token}``.
2. It loads the HTML template ``ric_standard.html`` and injects a JSON ``data``
   block plus a base64‑encoded PNG for the QR image.
3. It uses ``weasyprint.HTML`` to render the final PDF bytes.

The ``render`` function returns the PDF as ``bytes``.  Swapping the rendering
engine only requires replacing this file (the ``CertificateRenderer`` interface).
"""

import base64
import io
import json
from functools import lru_cache
from html import escape, unescape
from pathlib import Path
from typing import Dict

import segno
from PIL import Image as PillowImage

from app.core.config import settings

TEMPLATE_PATH = Path(__file__).parent / "templates" / "ric_standard.html"
ASSET_ROOT = Path(__file__).resolve().parents[3] / "Assets"


@lru_cache(maxsize=4)
def _asset_bytes(name: str) -> bytes:
    with PillowImage.open(ASSET_ROOT / name) as source:
        source.thumbnail((480, 480), PillowImage.Resampling.LANCZOS)
        output = io.BytesIO()
        source.convert("RGBA").save(output, format="PNG")
    return output.getvalue()


def _asset_data_uri(name: str) -> str:
    return "data:image/png;base64," + base64.b64encode(_asset_bytes(name)).decode("ascii")


def _fallback_pdf(data: Dict, qr_png: bytes) -> bytes:
    """Create the styled certificate when WeasyPrint cannot load on Windows."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Image,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        return _basic_fallback_pdf(data)

    output = io.BytesIO()
    green = colors.HexColor("#0b5d42")
    border_green = colors.HexColor("#06452f")
    border_red = colors.HexColor("#811d2a")
    pale_green = colors.HexColor("#edf4ef")
    paper = colors.HexColor("#fffdf7")
    width, height = A4

    def decorate(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(paper)
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        canvas.setStrokeColor(border_green)
        canvas.setLineWidth(2)
        canvas.rect(10 * mm, 10 * mm, width - 20 * mm, height - 20 * mm, fill=0, stroke=1)
        canvas.setStrokeColor(border_red)
        canvas.setLineWidth(1)
        canvas.rect(14 * mm, 14 * mm, width - 28 * mm, height - 28 * mm, fill=0, stroke=1)
        canvas.restoreState()

    styles = getSampleStyleSheet()
    title = ParagraphStyle("certificate-title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, alignment=TA_CENTER, textColor=green, spaceAfter=2)
    subtitle = ParagraphStyle("subtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=11, alignment=TA_CENTER, textColor=colors.HexColor("#7d611a"), spaceAfter=8)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=13, alignment=TA_LEFT, textColor=colors.HexColor("#17231d"))
    section = ParagraphStyle("section", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=green, spaceBefore=9, spaceAfter=4)
    small = ParagraphStyle("small", parent=body, fontSize=7.5, leading=10)

    def value(key, default="Not available"):
        return str(data.get(key) or default).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def mark(name, box_width, box_height, roundel=False):
        from PIL import Image as PillowImage, ImageDraw
        content = _asset_bytes(name)
        with PillowImage.open(io.BytesIO(content)) as image:
            if roundel:
                badge = PillowImage.new("RGBA", (256, 256))
                ImageDraw.Draw(badge).ellipse((1, 1, 254, 254), fill="#edf4ef", outline="#c5d0c8", width=3)
                logo = image.convert("RGBA")
                logo.thumbnail((199, 199))
                badge.alpha_composite(logo, ((256 - logo.width) // 2, (256 - logo.height) // 2))
                stream = io.BytesIO()
                badge.save(stream, format="PNG")
                stream.seek(0)
                return Image(stream, width=box_width * mm, height=box_height * mm)
            scale = min(box_width / image.width, box_height / image.height)
            return Image(io.BytesIO(content), width=image.width * scale * mm, height=image.height * scale * mm)

    marks = Table([[
        mark("Insignia/shapla.png", 20, 20),
        mark("Insignia/mapsignia.png", 19, 19),
        mark("Logo/logo_ctrx.png", 38, 18),
    ]], colWidths=[170 * mm / 3] * 3)
    marks.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story = [
        marks,
        Spacer(1, 3 * mm),
        Paragraph("Government of the People's Republic of Bangladesh", subtitle),
        Paragraph("RENTAL IDENTITY CERTIFICATE", title),
        Paragraph("Central Tenant Records", subtitle),
        Paragraph("CERTIFICATE OF VERIFIED RENTAL IDENTITY", ParagraphStyle("ribbon", parent=body, alignment=TA_CENTER, textColor=colors.white, backColor=green, fontName="Helvetica-Bold", fontSize=8, leading=14, spaceBefore=2, spaceAfter=8)),
        Paragraph(f"This certificate records the verified rental identity of <b>{value('full_name')}</b> and the household listed below.", body),
        Paragraph("CERTIFICATE HOLDER", section),
    ]
    details = [
        ["Full name", value("full_name"), "Date of birth", value("date_of_birth")],
        ["RIC number", value("ric_number"), "Identity record", "Ending " + value("identity_last4")],
        ["Rental area", value("area_name"), "Status", value("status")],
        ["Household address", value("household_address"), "", ""],
    ]
    detail_table = Table([[Paragraph(cell, small) for cell in row] for row in details],
                         colWidths=[30 * mm, 55 * mm, 30 * mm, 55 * mm])
    detail_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c5d0c8")),
        ("BACKGROUND", (0, 0), (0, -1), pale_green),
        ("BACKGROUND", (2, 0), (2, 2), pale_green),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, 2), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), green),
        ("TEXTCOLOR", (2, 0), (2, 2), green),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("SPAN", (1, 3), (3, 3)),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([detail_table, Paragraph("HOUSEHOLD MEMBERS", section)])
    member_rows = [["Member name", "Relationship", "Date of birth"]]
    member_rows.extend([
        [str(member.get("full_name") or "Not available"), str(member.get("relationship") or "Not specified"), str(member.get("date_of_birth") or "Not available")]
        for member in data.get("members") or []
    ] or [["No additional household members declared", "", ""]])
    member_table = Table([[Paragraph(escape(cell), small) for cell in row] for row in member_rows],
                         colWidths=[80 * mm, 45 * mm, 45 * mm], repeatRows=1)
    member_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c5d0c8")),
        ("BACKGROUND", (0, 0), (-1, 0), pale_green),
        ("TEXTCOLOR", (0, 0), (-1, 0), green),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("SPAN", (0, 1), (-1, 1)) if len(member_rows) == 2 and not data.get("members") else ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([
        member_table,
        Paragraph("DECLARATION", section),
        Paragraph("The holder named above has submitted the stated rental identity information for review. The record was examined through the CTRx local and central review workflow and is maintained as an auditable digital record. This certificate confirms the status of the CTRx record at the date of issue; it does not replace a national identity document, title deed, tenancy agreement, or statutory permission.", body),
        Spacer(1, 7 * mm),
    ])
    qr_image = Image(io.BytesIO(qr_png), width=25 * mm, height=25 * mm)
    verification = Table([[qr_image, Paragraph(f"<b>VERIFY THIS CERTIFICATE</b><br/>Scan the QR code to check the certificate record and current status.<br/>Issued: {value('issued_at')}<br/>Valid until: {value('expires_at')}", small)]], colWidths=[31 * mm, 139 * mm])
    verification.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c5d0c8")), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7faf7")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 6)]))
    story.extend([verification, Spacer(1, 13 * mm)])
    signature = Table([
        [Paragraph(f"<font size=\"13\"><b>{value('signature_name')}</b></font>", small)],
        [Spacer(1, 4 * mm)],
        [Paragraph(f"{value('official_name')}<br/>{value('official_designation')}<br/>Authorized CTRx Government Official", small)],
    ], colWidths=[90 * mm], hAlign="LEFT")
    signature.setStyle(TableStyle([
        ("LINEABOVE", (0, 2), (0, 2), 0.7, colors.HexColor("#17231d")),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
    ]))
    story.extend([signature, Spacer(1, 5 * mm), Paragraph("This is a digitally generated CTRx certificate. Verify before relying on its contents.", ParagraphStyle("notice", parent=small, alignment=TA_CENTER, textColor=colors.HexColor("#6a6a5a")))])
    SimpleDocTemplate(output, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=19 * mm, bottomMargin=19 * mm).build(story, onFirstPage=decorate, onLaterPages=decorate)
    return output.getvalue()


def _basic_fallback_pdf(data: Dict) -> bytes:
    """Create a minimal PDF only if neither renderer is installed."""
    member_lines = [
        f"Member: {member.get('full_name', 'Not available')} ({member.get('relationship') or 'Not specified'})"
        for member in data.get("members") or []
    ]
    lines = [
        "CTRx - Rental Identity Certificate",
        f"RIC number: {data.get('ric_number', 'Pending')}",
        f"Applicant: {data.get('full_name', 'Not available')}",
        f"Date of birth: {data.get('date_of_birth', 'Not available')}",
        f"Identity ending: {data.get('identity_last4', 'Not available')}",
        f"Area: {data.get('area_name', 'Not available')}",
        f"Address: {data.get('household_address', 'Not available')}",
        f"Household members: {len(member_lines)}",
        *member_lines,
        f"Status: {data.get('status', 'Active')}",
        "This certificate records the verified rental identity of the named person.",
        f"Authorized official: {data.get('official_name', 'Authorized Government Official')}",
        f"Designation: {data.get('official_designation', 'Central Reviewing Official')}",
    ]
    lines = [unescape(str(line)).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    stream_lines = ["BT", "/F1 18 Tf", "72 760 Td", f"({lines[0]}) Tj", "/F1 11 Tf"]
    for line in lines[1:]:
        stream_lines.extend(["0 -30 Td", f"({line}) Tj"])
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def _generate_qr(token: str) -> bytes:
    """Generate a QR code PNG for ``token``.

    The QR encodes ``{settings.VERIFY_BASE_URL}/{token}``.  If ``VERIFY_BASE_URL``
    is empty, we still generate the QR with the token only (fallback).
    """
    url = f"{settings.VERIFY_BASE_URL.rstrip('/')}/{token}" if settings.VERIFY_BASE_URL else token
    qr = segno.make(url)
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=5)
    return buf.getvalue()


@lru_cache(maxsize=1)
def _html_engine():
    try:
        from weasyprint import HTML
    except (ImportError, OSError):
        return None
    return HTML


def render(data: Dict, qr_png: bytes) -> bytes:
    """Render the certificate PDF.

    * ``data`` – the JSON payload from the ``v_certificate_render_data`` view.
    * ``qr_png`` – raw PNG bytes for the QR code.
    """
    engine = _html_engine()
    if engine is None:
        return _fallback_pdf(data, qr_png)

    template_html = TEMPLATE_PATH.read_text(encoding="utf-8")

    # Embed the data as a JSON string and the QR as a base64 image.
    context = {
        "data_json": json.dumps(data, ensure_ascii=False, indent=2),
        "qr_base64": base64.b64encode(qr_png).decode("ascii"),
        "shapla_image": _asset_data_uri("Insignia/shapla.png"),
        "mapsignia_image": _asset_data_uri("Insignia/mapsignia.png"),
        "logo_image": _asset_data_uri("Logo/logo_ctrx.png"),
    }
    for key in ("ric_number", "full_name", "date_of_birth", "identity_last4", "area_name", "household_address", "issued_at", "expires_at", "status", "official_name", "official_designation", "signature_name"):
        value = data.get(key) or "Not available"
        context[key] = escape(str(value))
    member_rows = []
    for member in data.get("members") or []:
        member_rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                escape(str(member.get("full_name") or "Not available")),
                escape(str(member.get("relationship") or "Not specified")),
                escape(str(member.get("date_of_birth") or "Not available")),
            )
        )
    context["member_rows"] = "".join(member_rows) or "<tr><td colspan=\"3\">No additional household members declared</td></tr>"
    # Very naive templating – replace {{data_json}} and {{qr_base64}} markers.
    rendered_html = template_html.replace("{{data_json}}", context["data_json"]).replace("{{qr_base64}}", context["qr_base64"])  # noqa: E501
    for key, value in context.items():
        rendered_html = rendered_html.replace("{{" + key + "}}", value)

    try:
        return engine(string=rendered_html).write_pdf()
    except OSError:
        return _fallback_pdf(data, qr_png)
