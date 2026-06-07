from __future__ import annotations

from app.services.customer_report_document_helper import build_customer_report_html, escape_html
from app.services.customer_report_service import CustomerReportIntent, CustomerReportResult


def _report() -> CustomerReportResult:
    return CustomerReportResult(
        title='Listado & <clientes> "especiales"',
        headers=['Cod. &', 'Nombre <', 'Vacío "'],
        rows=[
            ['C-1 &', '<Alpha>', None],
            ['', 'Texto "doble"', '&'],
        ],
        intent=CustomerReportIntent(),
    )


def test_escape_html_special_characters() -> None:
    assert escape_html('A & B < C > D "E"') == "A &amp; B &lt; C &gt; D &quot;E&quot;"


def test_build_customer_report_html_includes_table_structure_and_values() -> None:
    html = build_customer_report_html(_report())

    assert html.startswith("\n        <html>")
    assert "<table border=\"1\" cellspacing=\"0\" cellpadding=\"4\" width=\"100%\">" in html
    assert "<thead><tr><th>Cod. &amp;</th><th>Nombre &lt;</th><th>Vacío &quot;</th></tr></thead>" in html
    assert "<tbody><tr><td>C-1 &amp;</td><td>&lt;Alpha&gt;</td><td>None</td></tr><tr><td></td><td>Texto &quot;doble&quot;</td><td>&amp;</td></tr></tbody>" in html
    assert "<h2>Listado &amp; &lt;clientes&gt; &quot;especiales&quot;</h2>" in html


def test_build_customer_report_html_keeps_empty_cells_as_empty_strings() -> None:
    report = CustomerReportResult(
        title="Listado",
        headers=["Columna 1", "Columna 2"],
        rows=[["", None]],
        intent=CustomerReportIntent(),
    )

    html = build_customer_report_html(report)

    assert "<td></td><td>None</td>" in html
