from __future__ import annotations

import tempfile
import os
from pathlib import Path
from typing import Iterable

from fastapi import UploadFile

from app.api.errors import bad_request


MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024


async def upload_to_temp_file_path(
    upload: UploadFile,
    *,
    field_name: str,
    allowed_suffixes: Iterable[str],
) -> Path:
    filename = str(getattr(upload, "filename", "") or "").strip()
    if not filename:
        raise bad_request(f"{field_name} debe incluir nombre de archivo.")

    suffix = Path(filename).suffix.lower()
    allowed = {item.lower() for item in allowed_suffixes}
    if allowed and suffix not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise bad_request(f"{field_name} debe usar extension: {allowed_list}.")

    fd, temp_name = tempfile.mkstemp(prefix="gestion_ireks_", suffix=suffix)
    os.close(fd)
    temp_path = Path(temp_name)
    total_bytes = 0
    try:
        with temp_path.open("wb") as fh:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_SIZE_BYTES:
                    raise bad_request(f"{field_name} supera el tamano maximo permitido (20 MB).")
                fh.write(chunk)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    if total_bytes <= 0:
        temp_path.unlink(missing_ok=True)
        raise bad_request(f"{field_name} no contiene datos.")

    return temp_path
