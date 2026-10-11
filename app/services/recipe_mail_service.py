from __future__ import annotations

from pathlib import Path
import re
import tempfile


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


class RecipeMailService:
    """Prepare a classic Outlook draft with an embedded attachment. Never send it."""

    def __init__(self, dispatch=None):
        self._dispatch = dispatch

    def open_draft(self, *, pdf_content: bytes, recipe_name: str,
                   recipients: list[str], subject: str, body: str) -> None:
        recipients = normalize_recipients(recipients)
        if not recipients:
            raise ValueError("Selecciona un contacto o introduce un destinatario.")
        if not pdf_content:
            raise ValueError("No hay un PDF disponible para adjuntar.")
        try:
            dispatch = self._dispatch
            if dispatch is None:
                import win32com.client
                dispatch = win32com.client.Dispatch
            outlook = dispatch("Outlook.Application")
        except Exception as exc:
            raise RuntimeError(
                "No se pudo conectar con Outlook clásico. Comprueba que esté instalado "
                "y tenga una cuenta configurada. Esta integración requiere Outlook clásico."
            ) from exc
        safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", recipe_name).strip(" .")[:100] or "receta"
        try:
            with tempfile.TemporaryDirectory(prefix="gestionireks_recipe_mail_") as directory:
                attachment = Path(directory) / f"Receta-{safe_name}.pdf"
                attachment.write_bytes(pdf_content)
                mail = outlook.CreateItem(0)
                mail.To = "; ".join(recipients)
                mail.Subject = subject.strip()
                mail.Body = body
                mail.Attachments.Add(str(attachment), 1)  # olByValue: embed, never link.
                mail.Save()
                mail.Display()
        except Exception as exc:
            raise RuntimeError(
                "No se pudo preparar o abrir el correo en Outlook. No se ha enviado nada. "
                "Revisa Borradores antes de volver a intentarlo; puedes guardar el PDF igualmente."
            ) from exc
