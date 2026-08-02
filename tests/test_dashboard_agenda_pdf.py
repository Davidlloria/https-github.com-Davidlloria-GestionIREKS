from __future__ import annotations

from pypdf import PdfReader

from app.services.report_export_service import ReportExportService


def test_dashboard_agenda_pdf_uses_cards_and_keeps_all_long_entries(tmp_path) -> None:
    output = tmp_path / 'agenda_cards.pdf'
    long_content = 'Contenido detallado con acuerdos, observaciones y próximos pasos. ' * 8
    states = ['Pendiente', 'Hecha', 'Aplazada', 'Cancelada']
    rows = [
        [f'{day:02d}/07/2026', f'{100 + day} · Cliente {day}', f'Evento {day}. {long_content}', states[(day - 1) % 4]]
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
        assert states[(day - 1) % 4] in text


def test_dashboard_agenda_state_palette_covers_all_states() -> None:
    service = ReportExportService()

    assert service.agenda_state_tone('Pendiente') == 'pending'
    assert service.agenda_state_tone('Hecha') == 'completed'
    assert service.agenda_state_tone('Aplazada') == 'postponed'
    assert service.agenda_state_tone('Cancelada') == 'cancelled'
    assert service.AGENDA_STATE_PALETTE['pending'][0] == '#1D4ED8'
    assert service.AGENDA_STATE_PALETTE['completed'][0] == '#15803D'
    assert service.AGENDA_STATE_PALETTE['postponed'][0] == '#C2410C'
    assert service.AGENDA_STATE_PALETTE['cancelled'][0] == '#B91C1C'
    date_width, customer_width, state_width, horizontal_padding = service.dashboard_agenda_card_widths(800)
    assert date_width + customer_width + state_width + horizontal_padding == 800
    assert customer_width > 0
    assert state_width > date_width
