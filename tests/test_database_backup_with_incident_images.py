from __future__ import annotations

from pathlib import Path
import sqlite3
import zipfile

import app.core.database as database


def test_zip_backup_contains_database_and_incident_images(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    images_dir = data_dir / "incidencias_pedidos"
    images_dir.mkdir(parents=True)
    db_path = data_dir / "gestion_ireks.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO sample(value) VALUES ('ok')")
    image_path = images_dir / "incident-1" / "image-1.jpg"
    image_path.parent.mkdir()
    image_path.write_bytes(b"image")
    monkeypatch.setattr(database, "DATA_DIR", data_dir)
    monkeypatch.setattr(database, "DB_PATH", db_path)
    monkeypatch.setattr(database, "PEDIDO_INCIDENCIAS_DIR", images_dir)

    destination = tmp_path / "complete-backup.zip"
    saved = database.backup_database(destination)

    assert saved == destination
    with zipfile.ZipFile(destination) as archive:
        assert set(archive.namelist()) == {
            "gestion_ireks.db",
            "incidencias_pedidos/incident-1/image-1.jpg",
        }
        extracted_db = Path(archive.extract("gestion_ireks.db", tmp_path / "restored"))
    with sqlite3.connect(extracted_db) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone() == ("ok",)
