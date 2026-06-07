from __future__ import annotations

from app.services.product_report_service import ProductReportResult


def escape_html(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_product_report_html(report: ProductReportResult) -> str:
    header_html = "".join(f"<th>{escape_html(header)}</th>" for header in report.headers)
    rows_html = ""
    for row in report.rows:
        rows_html += "<tr>" + "".join(f"<td>{escape_html(value)}</td>" for value in row) + "</tr>"
    return f"""
        <html>
        <body>
        <h2>{escape_html(report.title)}</h2>
        <table border="1" cellspacing="0" cellpadding="4" width="100%">
        <thead><tr>{header_html}</tr></thead>
        <tbody>{rows_html}</tbody>
        </table>
        </body>
        </html>
        """
