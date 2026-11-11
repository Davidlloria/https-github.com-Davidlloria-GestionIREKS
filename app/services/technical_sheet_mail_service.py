from pathlib import Path

from app.services.recipe_mail_service import RecipeMailService


class TechnicalSheetMailService:
    def __init__(self, library, mail_service=None):
        self.library = library
        self.mail_service = mail_service or RecipeMailService()

    def open_draft(self, *, document_ids, recipients, subject, body, include_signature):
        attachments = []
        seen = set()
        for document_id in document_ids:
            if document_id in seen:
                continue
            seen.add(document_id)
            path = Path(self.library.resolve_document(document_id))
            if path.suffix.lower() != ".pdf":
                raise ValueError(f"La ficha no es un PDF: {path.name}")
            content = path.read_bytes()
            if not content:
                raise ValueError(f"La ficha está vacía: {path.name}")
            attachments.append((path.name, content))
        return self.mail_service.open_attachments_draft(
            attachments=attachments, recipients=recipients, subject=subject,
            body=body, include_signature=include_signature, allow_empty_recipients=True,
        )
