from __future__ import annotations

from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formatdate, make_msgid
from html import escape
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from app.core.config import DATA_DIR


def load_recipe_mail_signature(path: Path) -> dict | None:
    """Read the user's local snapshot, never query or change Outlook settings."""
    if not path.exists():
        return None
    try:
        if path.stat().st_size > 5_000_000:
            raise ValueError("Signature too large")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data["html"], str) or not isinstance(data["text"], str):
            raise ValueError("Invalid signature")
        for image in data.get("images", []):
            if image["subtype"] not in {"png", "jpeg", "gif"}:
                raise ValueError("Unsupported image")
            if not re.fullmatch(r"[a-zA-Z0-9_.@-]+", image["cid"]):
                raise ValueError("Invalid image identifier")
            base64.b64decode(image["data"], validate=True)
        return data
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError("No se pudo leer la firma guardada. Revisa recipe_mail_signature.json.") from exc


def normalize_recipients(addresses: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in addresses:
        for address in re.split(r"[;,]", value):
            address = address.strip()
            if not address:
                continue
            if not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", address):
                raise ValueError(f"Dirección de correo no válida: {address}")
            if address.casefold() not in seen:
                seen.add(address.casefold())
                result.append(address)
    return result


def find_new_outlook() -> Path:
    """Resolve only the new Outlook; never use the default mail client or COM."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        alias = Path(local_app_data) / "Microsoft" / "WindowsApps" / "olk.exe"
        if alias.is_file():
            return alias
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-AppxPackage Microsoft.OutlookForWindows).InstallLocation"],
            capture_output=True, text=True, check=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        location = result.stdout.strip()
        if location:
            executable = Path(location) / "olk.exe"
            if executable.is_file():
                return executable
    except (OSError, subprocess.SubprocessError):
        pass
    raise RuntimeError("No se encontró el nuevo Outlook. Instálalo o habilita su alias olk.exe. No se abrirá Outlook clásico.")


class RecipeMailService:
    """Open a MIME draft explicitly in new Outlook, without sending it."""

    def __init__(self, launcher=None, executable_resolver=None, draft_dir=None, signature_path=None):
        self._launcher = launcher or subprocess.Popen
        self._executable_resolver = executable_resolver or find_new_outlook
        self._draft_dir = Path(draft_dir) if draft_dir else Path(tempfile.gettempdir()) / "GestionIREKS-recipe-mail"
        self._signature_path = Path(signature_path) if signature_path else DATA_DIR / "recipe_mail_signature.json"

    def open_draft(self, *, pdf_content: bytes, recipe_name: str,
                   recipients: list[str], subject: str, body: str, include_signature: bool = True) -> Path:
        recipients = normalize_recipients(recipients)
        if not recipients:
            raise ValueError("Selecciona un contacto o introduce un destinatario.")
        if not pdf_content:
            raise ValueError("No hay un PDF disponible para adjuntar.")
        executable = self._executable_resolver()
        safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", recipe_name).strip(" .")[:100] or "receta"
        message = EmailMessage(policy=SMTP)
        message["X-Unsent"] = "1"
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject.strip()
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid(domain="gestionireks.local")
        signature = load_recipe_mail_signature(self._signature_path) if include_signature else None
        html_body = escape(body).replace("\n", "<br>")
        if signature:
            body += "\n\n" + signature["text"]
            html_body += "<br><br>" + signature["html"]
        message.set_content(body)
        message.add_alternative("<html><body>" + html_body + "</body></html>", subtype="html")
        if signature:
            html_part = message.get_payload()[-1]
            for image in signature.get("images", []):
                html_part.add_related(base64.b64decode(image["data"]), maintype="image",
                                      subtype=image["subtype"], cid=f'<{image["cid"]}>', disposition="inline")
        message.add_attachment(pdf_content, maintype="application", subtype="pdf", filename=f"Receta-{safe_name}.pdf")
        self._draft_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=self._draft_dir, prefix="receta-", suffix=".eml", delete=False) as draft:
            draft.write(message.as_bytes())
            draft_path = Path(draft.name)
        # New Outlook reads the file asynchronously. Retain it independently of
        # the PDF preview lifetime; Windows/user temporary-file cleanup owns it.
        try:
            self._launcher([str(executable), str(draft_path)], shell=False)
        except OSError as exc:
            raise RuntimeError(f"No se pudo abrir el nuevo Outlook. El correo preparado está en {draft_path}. No se ha enviado nada.") from exc
        return draft_path
