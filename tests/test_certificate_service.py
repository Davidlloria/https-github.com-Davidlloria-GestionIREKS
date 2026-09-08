import json

import fitz
import pytest

from app.services.certificate_service import CertificateService


@pytest.fixture
def certificate_setup(tmp_path):
    service = CertificateService.__new__(CertificateService)
    config = service._default_config()
    config["template_path"] = "assets/templates/certificados/Plantilla Certificado asistencia.pdf"
    # Existing installations have only the three original fields.
    config["targets"].pop("tecnicos")
    for field in config["targets"].values():
        field.pop("baseline")
        field.pop("bottom")
        field.pop("font_size", None)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return service, path


def test_certificate_replaces_all_fields_and_preserves_preprinted_layout(certificate_setup, tmp_path):
    service, config = certificate_setup
    rows = [
        {"asistente": "María Fernández López", "curso": "Panadería artesanal",
         "tecnicos": "Ana Pérez\nLuis Gómez\nEva Díaz", "fecha": "Arinaga, 8 de septiembre de 2026"},
        {"asistente": "Pedro Martín", "curso": "Masas y fermentaciones",
         "tecnicos": "", "fecha": "Arinaga, 9 de septiembre de 2026"},
    ]
    output = service.generate(rows, tmp_path / "certificates.pdf", config)
    with fitz.open(output) as doc:
        assert len(doc) == 2
        for page, row in zip(doc, rows):
            text = page.get_text()
            for value in (row["asistente"], row["curso"], row["fecha"], *row["tecnicos"].splitlines()):
                assert value in text
            for fixed in ("ha participado en nuestro", "Curso teórico-práctico", "impartido por"):
                assert fixed in text
            for old in ("Nombre del asistente", "Nombre del curso", "Jordi Ampurdanès", "David Lloria", "15 de abril de 2026"):
                assert old not in text
            assert not page.get_images()
            assert page.rect.width == pytest.approx(595.32, abs=0.1)
            assert page.rect.height == pytest.approx(842.04, abs=0.1)
            for field, baseline in (("asistente", 210.12), ("curso", 335.29), ("fecha", 499.56)):
                span = next(span for block in page.get_text("dict")["blocks"] for line in block.get("lines", [])
                            for span in line["spans"] if span["text"] == row[field])
                assert span["origin"][1] == pytest.approx(baseline, abs=0.02)
                assert (span["bbox"][0] + span["bbox"][2]) / 2 == pytest.approx(page.rect.width / 2, abs=0.1)


def test_certificate_long_text_is_complete_or_reports_overflow(certificate_setup, tmp_path):
    service, config = certificate_setup
    course = "Técnicas de panadería artesanal con masas fermentadas y especialidades de pastelería"
    row = {"asistente": "María Fernández López", "curso": course,
           "tecnicos": "Ana Pérez\nLuis Gómez\nEva Díaz\nPedro Martín\nSara León", "fecha": "Arinaga, 15 de abril de 2026"}
    output = service.generate([row], tmp_path / "long.pdf", config)
    with fitz.open(output) as doc:
        assert course in " ".join(doc[0].get_text().split())
        for name in row["tecnicos"].splitlines():
            assert name in doc[0].get_text()
    row["asistente"] = "Nombre " * 100
    with pytest.raises(ValueError, match="sin recortarlo"):
        service.generate([row], tmp_path / "overflow.pdf", config)
    assert not (tmp_path / "overflow.pdf").exists()


def test_course_marker_with_overlapping_font_bounds_preserves_fixed_line(certificate_setup, tmp_path):
    service, config_path = certificate_setup
    template_path = tmp_path / "close-lines.pdf"
    with fitz.open() as template:
        page = template.new_page(width=595.32, height=842.04)
        for text, baseline in (("Nombre del asistente", 210), ("Curso teórico-práctico", 312),
                               ("Nombre del curso", 335), ("Jordi Ampurdanès", 422),
                               ("David Lloria", 441), ("Arinaga, 15 de abril de 2026", 500)):
            page.insert_text((190, baseline), text, fontsize=20)
        fixed_rect = page.search_for("Curso teórico-práctico")[0]
        marker_rect = page.search_for("Nombre del curso")[0]
        assert fixed_rect.intersects(marker_rect)
        template.save(template_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["template_path"] = str(template_path)
    config_path.write_text(json.dumps(config), encoding="utf-8")
    row = {"asistente": "Antonio Bruno Acosta Guerra", "curso": "PANES ESPECIALES",
           "tecnicos": "Alejandro Montes Garcia\nDavid Lloria Abascal\nKevin Keith Gómez Flores",
           "fecha": "Arinaga, 10 de septiembre de 2026"}
    output = service.generate([row], tmp_path / "corrected.pdf", config_path)
    with fitz.open(output) as doc:
        text = doc[0].get_text()
        assert "Curso teórico-práctico" in text
        assert "Nombre del curso" not in text
        assert "PANES ESPECIALES" in text
