import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from reportlab.graphics.barcode import code128
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .models import SalesOrder, OrderLine, Customer

TAX_RATE = 0.1
DEFAULT_FONT_REGULAR = "Helvetica"
DEFAULT_FONT_BOLD = "Helvetica-Bold"
JP_FONT_NAME = "FaxJP"

TEMPLATE_MAP = {
    "order_summary": ["order_summary.pdf", "order_summary.png", "order_summary.jpg", "order_summary.jpeg", "IMG_1361.jpeg"],
    "packing_slip": ["packing_slip.pdf", "packing_slip.png", "packing_slip.jpg", "packing_slip.jpeg", "IMG_1366.jpeg"],
    "delivery_note": ["delivery_note.pdf", "delivery_note.png", "delivery_note.jpg", "delivery_note.jpeg", "IMG_1370.jpeg"],
    "delivery_detail": ["delivery_detail.pdf", "delivery_detail.png", "delivery_detail.jpg", "delivery_detail.jpeg", "IMG_1368.jpeg"],
    "invoice": ["invoice2.jpeg", "invoice.pdf", "invoice.png", "invoice.jpg", "invoice.jpeg"],
    "invoice_detail": ["invoice_detail.pdf", "invoice_detail.png", "invoice_detail.jpg", "invoice_detail.jpeg", "invoice3.jpeg"],
    "invoice_statement": ["invoice_statement.pdf", "invoice_statement.png", "invoice_statement.jpg", "invoice_statement.jpeg", "invoice4.jpeg"],
}


def _register_fonts() -> tuple[str, str]:
    font_path = os.getenv(
        "FAX_JP_FONT_PATH",
        str(Path(__file__).resolve().parent.parent / "assets" / "fonts" / "NotoSansJP-Regular.otf"),
    )
    font_file = Path(font_path)
    if font_file.exists():
        try:
            pdfmetrics.registerFont(TTFont(JP_FONT_NAME, str(font_file)))
            return JP_FONT_NAME, JP_FONT_NAME
        except Exception:
            return DEFAULT_FONT_REGULAR, DEFAULT_FONT_BOLD
    return DEFAULT_FONT_REGULAR, DEFAULT_FONT_BOLD


def _template_dirs() -> list[Path]:
    dirs: list[Path] = []
    env_dir = os.getenv("FAX_TEMPLATE_DIR")
    if env_dir:
        dirs.append(Path(env_dir))
    base_dir = Path(__file__).resolve().parent.parent
    dirs.append(base_dir / "samples" / "output")
    dirs.append(base_dir / "samples" / "input")
    return [directory for directory in dirs if directory.exists()]


def _resolve_template(document_type: str) -> Optional[Path]:
    candidates = TEMPLATE_MAP.get(document_type, [])
    if not candidates:
        return None
    for directory in _template_dirs():
        for name in candidates:
            path = directory / name
            if path.exists():
                return path
    return None


def _draw_background(c: canvas.Canvas, template_path: Optional[Path]) -> None:
    if not template_path or not template_path.exists():
        return
    if template_path.suffix.lower() == ".pdf":
        return
    c.drawImage(str(template_path), 0, 0, width=A4[0], height=A4[1], preserveAspectRatio=False, mask='auto')


FONT_REGULAR, FONT_BOLD = _register_fonts()


def _set_font(c: canvas.Canvas, size: int, bold: bool = False) -> None:
    c.setFont(FONT_BOLD if bold else FONT_REGULAR, size)


def _format_amount(value: float) -> str:
    return f"{value:,.2f}"


def _draw_header(c: canvas.Canvas, title: str, order: SalesOrder, customer: Optional[Customer]) -> None:
    _set_font(c, 14, bold=True)
    c.drawString(20 * mm, 280 * mm, title)
    _set_font(c, 9)
    c.drawString(20 * mm, 272 * mm, f"???: {datetime.utcnow().strftime('%Y-%m-%d')}")
    if customer:
        c.drawString(20 * mm, 266 * mm, f"??: {customer.name}")
    if order.order_number:
        c.drawString(20 * mm, 260 * mm, f"????: {order.order_number}")
    if order.delivery_number:
        c.drawString(20 * mm, 254 * mm, f"????: {order.delivery_number}")
    if order.invoice_number:
        c.drawString(20 * mm, 248 * mm, f"????: {order.invoice_number}")


def _draw_table_header(c: canvas.Canvas, y: float) -> None:
    _set_font(c, 9, bold=True)
    c.drawString(20 * mm, y, "??")
    c.drawString(95 * mm, y, "??")
    c.drawString(120 * mm, y, "??")
    c.drawString(150 * mm, y, "??")
    c.drawString(172 * mm, y, "?????")


def _draw_lines(c: canvas.Canvas, lines: Iterable[OrderLine], start_y: float, template_path: Optional[Path]) -> float:
    y = start_y
    _set_font(c, 9)
    for line in lines:
        if y < 25 * mm:
            c.showPage()
            _draw_background(c, template_path)
            _draw_table_header(c, 270 * mm)
            y = 260 * mm
            _set_font(c, 9)
        c.drawString(20 * mm, y, line.normalized_name or line.customer_name)
        c.drawRightString(110 * mm, y, str(line.quantity))
        c.drawRightString(140 * mm, y, _format_amount(line.unit_price))
        c.drawRightString(170 * mm, y, _format_amount(line.line_total))
        barcode_value = f"{line.order_id}-{line.id}"
        barcode = code128.Code128(barcode_value, barHeight=8 * mm, barWidth=0.3)
        barcode.drawOn(c, 172 * mm, y - 4 * mm)
        y -= 10 * mm
    return y


def _draw_totals(c: canvas.Canvas, subtotal: float, y: float) -> None:
    tax = subtotal * TAX_RATE
    total = subtotal + tax
    _set_font(c, 10, bold=True)
    c.drawRightString(170 * mm, y, f"??: {_format_amount(subtotal)}")
    c.drawRightString(170 * mm, y - 6 * mm, f"???: {_format_amount(tax)}")
    c.drawRightString(170 * mm, y - 12 * mm, f"??: {_format_amount(total)}")


def _draw_order_summary(
    c: canvas.Canvas,
    order: SalesOrder,
    customer: Optional[Customer],
    lines: Iterable[OrderLine],
    template_path: Optional[Path],
) -> None:
    _draw_background(c, template_path)
    _draw_header(c, "???", order, customer)
    y = 235 * mm
    _draw_table_header(c, y)
    y -= 8 * mm
    _draw_lines(c, lines, y, template_path)


def _draw_delivery_note(
    c: canvas.Canvas,
    order: SalesOrder,
    customer: Optional[Customer],
    lines: Iterable[OrderLine],
    template_path: Optional[Path],
) -> None:
    _draw_background(c, template_path)
    _draw_header(c, "???", order, customer)
    y = 235 * mm
    _draw_table_header(c, y)
    y -= 8 * mm
    _draw_lines(c, lines, y, template_path)


def _draw_delivery_detail(
    c: canvas.Canvas,
    order: SalesOrder,
    customer: Optional[Customer],
    lines: Iterable[OrderLine],
    template_path: Optional[Path],
) -> None:
    _draw_background(c, template_path)
    _draw_header(c, "?????", order, customer)
    y = 235 * mm
    _draw_table_header(c, y)
    y -= 8 * mm
    _draw_lines(c, lines, y, template_path)


def _draw_invoice(
    c: canvas.Canvas,
    order: SalesOrder,
    customer: Optional[Customer],
    lines: Iterable[OrderLine],
    template_path: Optional[Path],
) -> None:
    _draw_background(c, template_path)
    _draw_header(c, "???", order, customer)
    y = 235 * mm
    _draw_table_header(c, y)
    y -= 8 * mm
    _draw_lines(c, lines, y, template_path)
    subtotal = sum(line.line_total for line in lines)
    _draw_totals(c, subtotal, 60 * mm)


def _draw_invoice_detail(
    c: canvas.Canvas,
    order: SalesOrder,
    customer: Optional[Customer],
    lines: Iterable[OrderLine],
    template_path: Optional[Path],
) -> None:
    _draw_background(c, template_path)
    _draw_header(c, "?????", order, customer)
    y = 235 * mm
    _draw_table_header(c, y)
    y -= 8 * mm
    _draw_lines(c, lines, y, template_path)


def _draw_invoice_statement(
    c: canvas.Canvas,
    order: SalesOrder,
    customer: Optional[Customer],
    lines: Iterable[OrderLine],
    template_path: Optional[Path],
) -> None:
    _draw_background(c, template_path)
    _draw_header(c, "???(??)", order, customer)
    subtotal = sum(line.line_total for line in lines)
    _draw_totals(c, subtotal, 250 * mm)


def _draw_packing_slips(
    c: canvas.Canvas,
    order: SalesOrder,
    customer: Optional[Customer],
    lines: Iterable[OrderLine],
    template_path: Optional[Path],
) -> None:
    for idx, line in enumerate(lines):
        if idx > 0:
            c.showPage()
        _draw_background(c, template_path)
        _set_font(c, 16, bold=True)
        c.drawString(20 * mm, 270 * mm, "???")
        _set_font(c, 10)
        if customer:
            c.drawString(20 * mm, 260 * mm, f"??: {customer.name}")
        if order.delivery_number:
            c.drawString(20 * mm, 252 * mm, f"????: {order.delivery_number}")
        if line.unit_number:
            c.drawString(20 * mm, 244 * mm, f"????No: {line.unit_number}")
        _set_font(c, 14, bold=True)
        c.drawString(20 * mm, 220 * mm, line.normalized_name or line.customer_name)
        _set_font(c, 18, bold=True)
        c.drawString(20 * mm, 200 * mm, f"??: {line.quantity}")
        barcode_value = f"{line.order_id}-{line.id}"
        barcode = code128.Code128(barcode_value, barHeight=18 * mm, barWidth=0.4)
        barcode.drawOn(c, 20 * mm, 170 * mm)


def generate_pdf(
    document_type: str,
    order: SalesOrder,
    customer: Optional[Customer],
    lines: Iterable[OrderLine],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{order.id}-{document_type}.pdf"
    output_path = output_dir / filename

    template_path = _resolve_template(document_type)
    c = canvas.Canvas(str(output_path), pagesize=A4)

    if document_type == "order_summary":
        _draw_order_summary(c, order, customer, lines, template_path)
    elif document_type == "packing_slip":
        _draw_packing_slips(c, order, customer, lines, template_path)
    elif document_type == "delivery_note":
        _draw_delivery_note(c, order, customer, lines, template_path)
    elif document_type == "delivery_detail":
        _draw_delivery_detail(c, order, customer, lines, template_path)
    elif document_type == "invoice":
        _draw_invoice(c, order, customer, lines, template_path)
    elif document_type == "invoice_detail":
        _draw_invoice_detail(c, order, customer, lines, template_path)
    elif document_type == "invoice_statement":
        _draw_invoice_statement(c, order, customer, lines, template_path)
    else:
        _draw_order_summary(c, order, customer, lines, template_path)

    c.showPage()
    c.save()
    return output_path
