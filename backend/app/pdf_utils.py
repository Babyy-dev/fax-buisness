from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .models import SalesOrder, OrderLine, Customer


def _draw_header(c: canvas.Canvas, title: str, order: SalesOrder, customer: Optional[Customer]) -> None:
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, 280 * mm, title)
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, 272 * mm, f"作成日: {datetime.utcnow().strftime('%Y-%m-%d')}")
    if customer:
        c.drawString(20 * mm, 266 * mm, f"顧客: {customer.name}")
    if order.order_number:
        c.drawString(20 * mm, 260 * mm, f"注文番号: {order.order_number}")
    if order.delivery_number:
        c.drawString(20 * mm, 254 * mm, f"納品番号: {order.delivery_number}")
    if order.invoice_number:
        c.drawString(20 * mm, 248 * mm, f"請求番号: {order.invoice_number}")


def _draw_table_header(c: canvas.Canvas, y: float) -> None:
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, "品名")
    c.drawString(100 * mm, y, "数量")
    c.drawString(120 * mm, y, "単価")
    c.drawString(150 * mm, y, "金額")


def _draw_lines(c: canvas.Canvas, lines: Iterable[OrderLine], start_y: float) -> float:
    y = start_y
    c.setFont("Helvetica", 9)
    for line in lines:
        if y < 20 * mm:
            c.showPage()
            y = 270 * mm
            _draw_table_header(c, y)
            y -= 6 * mm
            c.setFont("Helvetica", 9)
        c.drawString(20 * mm, y, line.normalized_name or line.customer_name)
        c.drawRightString(115 * mm, y, str(line.quantity))
        c.drawRightString(140 * mm, y, f"{line.unit_price:,.2f}")
        c.drawRightString(185 * mm, y, f"{line.line_total:,.2f}")
        y -= 6 * mm
    return y


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

    title_map = {
        "order_summary": "注文書（兼 納品書/請求内訳明細）",
        "packing_slip": "現品票",
        "delivery_note": "納品書",
        "delivery_detail": "納品明細書",
        "invoice": "請求書",
        "invoice_detail": "請求明細書",
        "invoice_statement": "請求書（集計/締め）",
    }
    title = title_map.get(document_type, "帳票")

    c = canvas.Canvas(str(output_path), pagesize=A4)
    _draw_header(c, title, order, customer)

    y = 235 * mm
    _draw_table_header(c, y)
    y -= 6 * mm
    _draw_lines(c, lines, y)

    c.showPage()
    c.save()
    return output_path
