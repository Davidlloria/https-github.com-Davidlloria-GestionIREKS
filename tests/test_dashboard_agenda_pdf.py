from __future__ import annotations

from pypdf import PdfReader

from app.services.report_export_service import ReportExportService


def test_dashboard_agenda_pdf_uses_cards_and_keeps_all_long_entries(tmp_path) -> None:
    output = tmp_path / 'agenda_cards.pdf'
    long_content = 'Contenido detallado con acuerdos, observaciones y próximos pasos. ' * 8
    rows = [
        [f'{day:02d}/07/2026', f'{100 + day} · Cliente {day}', f'Evento {day}. {long_content}', 'Pendiente']
        for day in range(1, 25)
    ]

    result = ReportExportService().export_dashboard_agenda_pdf(output, 'Agenda semana 27', rows)

    assert result == output
    assert output.read_bytes().startswith(b'%PDF')
    pages = PdfReader(output).pages
    assert len(pages) >= 2
    text = '\n'.join(page.extract_text() or '' for page in pages)
    for day in range(1, 25):
        assert f'{day:02d}/07/2026' in text
        assert f'{100 + day} · Cliente {day}' in text
        assert f'Evento {day}.' in text
        assert 'Pendiente' in text
