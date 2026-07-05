"""MTD quarterly tax-prep pack — HMRC self-employment category breakdown as CSV/PDF.

This is NOT a submission to HMRC. Making Tax Digital for Income Tax requires filing
through HMRC-recognised software connected directly to HMRC's API — getting that
live connection requires formal software-vendor accreditation with HMRC, well beyond
what's buildable here. This prepares the numbers in HMRC's own category shape so a
sole trader (or their accountant) isn't starting from a raw Xero export.
"""

from __future__ import annotations

import asyncio
import csv
import io
from datetime import date
from typing import Any

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

from app.agent.tools.xero_queries import _current_mtd_quarter, parse_xero_report
from app.xero_client import get_accounting_api

# HMRC's official self-employment expense categories (SA103 / MTD ITSA quarterly
# update boxes). Xero has no native mapping to these, so line items are matched by
# account-name keywords; anything unmatched falls into "Other business expenses"
# rather than being silently dropped.
_HMRC_CATEGORIES: list[tuple[str, list[str]]] = [
    ("Cost of goods bought for resale or goods used", ["cost of sales", "purchases", "cost of goods", "materials"]),
    ("Car, van and travel expenses", ["motor", "vehicle", "travel", "van", "mileage", "parking", "fuel", "car"]),
    ("Wages, salaries and other staff costs", ["wages", "salaries", "staff", "payroll", "subcontractor"]),
    (
        "Rent, rates, power and insurance costs",
        ["rent", "rates", "power", "light", "heating", "electricity", "gas", "insurance", "utilities"],
    ),
    ("Repairs and renewals of property and equipment", ["repairs", "maintenance", "renewals"]),
    (
        "Phone, fax, stationery and other office costs",
        ["phone", "telephone", "internet", "stationery", "printing", "postage", "freight", "courier", "office"],
    ),
    ("Advertising and business entertainment costs", ["advertising", "marketing", "entertainment", "promotion"]),
    ("Interest on bank and other loans", ["loan interest", "interest on"]),
    (
        "Bank, credit card and other financial charges",
        ["bank fee", "bank charge", "credit card", "financial charge", "merchant fee"],
    ),
    ("Irrecoverable debts written off", ["bad debt", "doubtful debt", "written off"]),
    ("Accountancy, legal and other professional fees", ["accountancy", "accountant", "legal", "professional fees", "audit"]),
    ("Depreciation and loss/profit on sale of assets", ["depreciation", "loss on sale", "profit on sale"]),
]
_OTHER_CATEGORY = "Other business expenses"
_EXCLUDED_LINE_NAMES = {"gross profit", "net profit"}


def _classify_hmrc_category(account_name: str) -> str:
    lower = account_name.lower()
    for category, keywords in _HMRC_CATEGORIES:
        if any(kw in lower for kw in keywords):
            return category
    return _OTHER_CATEGORY


def _walk_leaf_lines(rows: list[dict[str, Any]]) -> list[tuple[str, str, float]]:
    """Return (section, account_name, amount) for every leaf P&L line — skips subtotal/total rows."""
    out: list[tuple[str, str, float]] = []
    section = ""

    def _leaf(name: str, raw_value: Any) -> tuple[str, float] | None:
        name = name.strip()
        if not name or name.lower().startswith("total ") or name.lower() in _EXCLUDED_LINE_NAMES:
            return None
        try:
            return name, float(str(raw_value).replace(",", ""))
        except (TypeError, ValueError):
            return None

    for row in rows:
        title = row.get("title")
        if isinstance(title, str) and title.strip():
            section = title.strip()
        children = row.get("children") or []
        if children:
            for child in children:
                cells = child.get("cells") or []
                if len(cells) < 2:
                    continue
                leaf = _leaf(str(cells[0] or ""), cells[1])
                if leaf:
                    out.append((section, leaf[0], leaf[1]))
        else:
            cells = row.get("cells") or []
            if len(cells) >= 2:
                leaf = _leaf(str(cells[0] or ""), cells[1])
                if leaf:
                    out.append((section, leaf[0], leaf[1]))
    return out


async def build_tax_pack(connection_id: str, as_of: date) -> dict[str, Any]:
    """Fetch this MTD quarter's P&L and categorise it into HMRC's expense boxes."""
    accounting, tenant_id = get_accounting_api(connection_id)
    q_start, q_end, deadline, label = _current_mtd_quarter(as_of)

    report = await asyncio.to_thread(
        accounting.get_report_profit_and_loss,
        tenant_id,
        from_date=q_start.isoformat(),
        to_date=min(q_end, as_of).isoformat(),
    )
    parsed = parse_xero_report(report)
    rows = parsed.get("rows") or []
    lines = _walk_leaf_lines(rows)

    turnover = 0.0
    category_totals: dict[str, float] = {}
    line_items: list[dict[str, Any]] = []
    for section, name, amount in lines:
        if "income" in section.lower():
            turnover += amount
            continue
        category = _classify_hmrc_category(name)
        category_totals[category] = category_totals.get(category, 0.0) + amount
        line_items.append({"account": name, "category": category, "amount_gbp": round(amount, 2)})

    total_expenses = sum(category_totals.values())
    net_profit = turnover - total_expenses

    return {
        "mtd_quarter": label,
        "quarter_start": q_start.isoformat(),
        "quarter_end": q_end.isoformat(),
        "submission_deadline": deadline.isoformat(),
        "days_until_deadline": (deadline - as_of).days,
        "turnover_gbp": round(turnover, 2),
        "total_expenses_gbp": round(total_expenses, 2),
        "net_profit_gbp": round(net_profit, 2),
        "categories": [
            {"category": cat, "amount_gbp": round(amt, 2)}
            for cat, amt in sorted(category_totals.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "line_items": line_items,
    }


def render_csv(data: dict[str, Any]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["MTD Quarterly Tax Summary — preparation only, not an HMRC submission"])
    writer.writerow(["Quarter", data["mtd_quarter"]])
    writer.writerow(["Period", f"{data['quarter_start']} to {data['quarter_end']}"])
    writer.writerow(["Submission deadline", data["submission_deadline"]])
    writer.writerow([])
    writer.writerow(["Turnover (income)", f"{data['turnover_gbp']:.2f}"])
    writer.writerow([])
    writer.writerow(["HMRC expense category", "Amount (GBP)"])
    for cat in data["categories"]:
        writer.writerow([cat["category"], f"{cat['amount_gbp']:.2f}"])
    writer.writerow([])
    writer.writerow(["Total expenses", f"{data['total_expenses_gbp']:.2f}"])
    writer.writerow(["Net profit", f"{data['net_profit_gbp']:.2f}"])
    writer.writerow([])
    writer.writerow(["Detail — Xero account", "HMRC category", "Amount (GBP)"])
    for line in data["line_items"]:
        writer.writerow([line["account"], line["category"], f"{line['amount_gbp']:.2f}"])
    return buf.getvalue().encode("utf-8")


def render_pdf(data: dict[str, Any]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "MTD Quarterly Tax Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(
        0, 8,
        f"Quarter: {data['mtd_quarter']} ({data['quarter_start']} to {data['quarter_end']})",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.cell(
        0, 8,
        f"Submission deadline: {data['submission_deadline']} "
        f"({data['days_until_deadline']} days away)",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Turnover: GBP {data['turnover_gbp']:,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.cell(0, 8, "Expenses by HMRC category:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    for cat in data["categories"]:
        pdf.cell(0, 7, f"  {cat['category']}: GBP {cat['amount_gbp']:,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Total expenses: GBP {data['total_expenses_gbp']:,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Net profit: GBP {data['net_profit_gbp']:,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Detail (Xero account -> HMRC category)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for line in data["line_items"]:
        pdf.cell(
            0, 6,
            f"{line['account']} -> {line['category']}: GBP {line['amount_gbp']:,.2f}",
            new_x="LMARGIN", new_y="NEXT",
        )
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(
        0, 5,
        "This is a preparation summary, not a submission to HMRC. Making Tax Digital for "
        "Income Tax requires filing through HMRC-recognised software connected directly to "
        "HMRC's API -- use this to brief your accountant or import into your filing software.",
    )
    return bytes(pdf.output())


_CHART_BG = (255, 255, 255)
_CHART_BAR = (37, 99, 235)  # blue-600
_CHART_TEXT = (17, 24, 39)  # gray-900
_CHART_MUTED = (107, 114, 128)  # gray-500


def render_chart_png(data: dict[str, Any]) -> bytes:
    """Horizontal bar chart of this quarter's HMRC expense categories — a WhatsApp
    image renders reliably where a PDF document attachment does not (see
    send_document_via_wassist's docstring in app/wassist.py), so this is the
    actual rich-media path for the tax pack on WhatsApp."""
    categories = data["categories"]
    width, row_h, top_pad, bottom_pad = 1000, 56, 170, 140
    height = top_pad + max(1, len(categories)) * row_h + bottom_pad

    img = Image.new("RGB", (width, height), _CHART_BG)
    draw = ImageDraw.Draw(img)

    title_font = ImageFont.load_default(size=34)
    subtitle_font = ImageFont.load_default(size=20)
    label_font = ImageFont.load_default(size=20)
    amount_font = ImageFont.load_default(size=20)
    footer_font = ImageFont.load_default(size=22)

    # PIL's default font has no glyphs for £/— (renders as tofu boxes) — stick to
    # ASCII, matching the "GBP 1,234.56" convention already used in WhatsApp text
    # replies elsewhere in this app (see _money() in voice_fast.py).
    draw.text((40, 30), "MTD Tax Pack - HMRC Expense Categories", font=title_font, fill=_CHART_TEXT)
    draw.text(
        (40, 76),
        f"{data['mtd_quarter']} ({data['quarter_start']} to {data['quarter_end']}) - "
        f"next update due {data['submission_deadline']}, {data['days_until_deadline']} days away",
        font=subtitle_font,
        fill=_CHART_MUTED,
    )

    label_w = 400
    bar_area_x0 = 40 + label_w
    bar_area_w = width - bar_area_x0 - 160
    max_amount = max((c["amount_gbp"] for c in categories), default=1) or 1

    y = top_pad
    for cat in categories:
        label = cat["category"]
        if len(label) > 42:
            label = label[:39] + "..."
        draw.text((40, y + row_h // 2 - 12), label, font=label_font, fill=_CHART_TEXT)

        bar_w = max(4, int(bar_area_w * (cat["amount_gbp"] / max_amount)))
        draw.rectangle(
            [bar_area_x0, y + 10, bar_area_x0 + bar_w, y + row_h - 18],
            fill=_CHART_BAR,
        )
        draw.text(
            (bar_area_x0 + bar_w + 12, y + row_h // 2 - 12),
            f"GBP {cat['amount_gbp']:,.2f}",
            font=amount_font,
            fill=_CHART_TEXT,
        )
        y += row_h

    footer_y = top_pad + len(categories) * row_h + 30
    draw.line([(40, footer_y - 10), (width - 40, footer_y - 10)], fill=(229, 231, 235), width=2)
    draw.text((40, footer_y + 10), f"Turnover: GBP {data['turnover_gbp']:,.2f}", font=footer_font, fill=_CHART_TEXT)
    draw.text(
        (40, footer_y + 42),
        f"Total expenses: GBP {data['total_expenses_gbp']:,.2f}   -   "
        f"Net profit: GBP {data['net_profit_gbp']:,.2f}",
        font=footer_font,
        fill=_CHART_TEXT,
    )
    draw.text(
        (40, footer_y + 80),
        "Preparation summary - not a submission to HMRC.",
        font=subtitle_font,
        fill=_CHART_MUTED,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
