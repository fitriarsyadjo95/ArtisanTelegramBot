import asyncio
from pathlib import Path

import jinja2
from markupsafe import Markup, escape
import weasyprint

from app.config import settings

TEMPLATE_DIR = Path(__file__).parent.parent / "pdf" / "templates"
ASSETS_DIR = Path(__file__).parent.parent / "pdf" / "assets"
STAMP_PATH = ASSETS_DIR / "stamp.png"

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


def format_currency(value) -> str:
    """Format a number as Malaysian Ringgit."""
    try:
        return f"RM{float(value):,.2f}"
    except (ValueError, TypeError):
        return f"RM{value}"


jinja_env.filters["currency"] = format_currency


def nl2br(value) -> str:
    """Convert newlines to HTML <br> tags."""
    if not value:
        return ""
    return Markup(str(escape(value)).replace("\n", "<br>"))


jinja_env.filters["nl2br"] = nl2br


def _stamp_path() -> str | None:
    """Return absolute stamp path if the file exists."""
    if STAMP_PATH.exists():
        return str(STAMP_PATH.resolve())
    return None


async def generate_quotation_pdf(quotation, customer, line_items) -> bytes:
    """Generate a quotation PDF and return bytes."""
    template = jinja_env.get_template("quotation.html")
    # Add empty rows to fill the table (aim for ~5 visible rows minimum)
    max_empty_rows = max(0, 3 - len(line_items))
    html_content = template.render(
        quotation=quotation,
        customer=customer,
        line_items=line_items,
        company=_company_context(),
        bank=_bank_context(),
        stamp_path=_stamp_path(),
        max_empty_rows=max_empty_rows,
    )
    pdf_bytes = await asyncio.to_thread(weasyprint.HTML(string=html_content).write_pdf)
    return pdf_bytes


async def generate_invoice_pdf(invoice, quotation, customer, line_items) -> bytes:
    """Generate an invoice PDF and return bytes."""
    template = jinja_env.get_template("invoice.html")
    html_content = template.render(
        invoice=invoice,
        quotation=quotation,
        customer=customer,
        line_items=line_items,
        company=_company_context(),
        bank=_bank_context(),
        stamp_path=_stamp_path(),
    )
    pdf_bytes = await asyncio.to_thread(weasyprint.HTML(string=html_content).write_pdf)
    return pdf_bytes


def _company_context() -> dict:
    return {
        "name": settings.COMPANY_NAME,
        "phone": settings.COMPANY_PHONE,
        "ssm": settings.COMPANY_SSM,
        "address": settings.COMPANY_ADDRESS,
        "authorized_by": settings.AUTHORIZED_BY,
    }


def _bank_context() -> dict:
    return {
        "name": settings.BANK_NAME,
        "account": settings.BANK_ACCOUNT,
        "holder": settings.BANK_HOLDER,
    }
