from __future__ import annotations

from dataclasses import dataclass

from app.services.customer_contact_flow_service import CustomerContactFlowService


@dataclass
class _FakeContacto:
    contacto_id: str = ""
    cliente_id: str = ""


class _FakeSession:
    def __init__(self, *, contact=None, customer=None, contacts=None) -> None:
        self.contact = contact
        self.customer = customer
        self.contacts = contacts or []
        self.add_calls: list[object] = []
        self.exec_called = False
        self.get_calls: list[tuple[object, str]] = []

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def exec(self, *_args, **_kwargs):
        self.exec_called = True
        return list(self.contacts)

    def get(self, model, object_id):  # noqa: ANN001
        self.get_calls.append((model, object_id))
        if getattr(model, "__name__", "") == "Contacto":
            return self.contact
        if getattr(model, "__name__", "") == "Cliente":
            return self.customer
        return None

    def add(self, obj):  # noqa: ANN001
        self.add_calls.append(obj)


class _FakeSessionFactory:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    def __call__(self, *_args, **_kwargs) -> _FakeSession:
        return self.session


class _FakeCustomerVM:
    def __init__(self) -> None:
        self.create_calls: list[tuple[object, dict]] = []

    def create(self, session, payload):  # noqa: ANN001
        self.create_calls.append((session, payload))
        return object()


class _FakeContactVM:
    def __init__(self) -> None:
        self.create_calls: list[tuple[object, dict]] = []
        self.update_calls: list[tuple[object, str, dict]] = []

    def create(self, session, payload):  # noqa: ANN001
        self.create_calls.append((session, payload))
        return _FakeContacto(contacto_id="created-1", cliente_id=str(payload.get("cliente_id") or ""))

    def update(self, session, contacto_id: str, payload: dict):  # noqa: ANN001
        self.update_calls.append((session, contacto_id, payload))
        return _FakeContacto(contacto_id=contacto_id, cliente_id=str(payload.get("cliente_id") or ""))


def test_related_contacts_returns_ordered_list(monkeypatch) -> None:
    from app.services import customer_contact_flow_service as module

    fake_session = _FakeSession(contacts=[_FakeContacto("c1"), _FakeContacto("c2")])
    monkeypatch.setattr(module, "Session", _FakeSessionFactory(fake_session))
    service = CustomerContactFlowService(engine=object())

    result = service.related_contacts("cliente-1")

    assert result == fake_session.contacts
    assert fake_session.exec_called is True


def test_create_and_update_contact_delegate_to_viewmodel(monkeypatch) -> None:
    from app.services import customer_contact_flow_service as module

    fake_session = _FakeSession()
    monkeypatch.setattr(module, "Session", _FakeSessionFactory(fake_session))
    fake_customer_vm = _FakeCustomerVM()
    fake_contact_vm = _FakeContactVM()
    service = CustomerContactFlowService(engine=object(), customer_vm=fake_customer_vm, contact_vm=fake_contact_vm)

    created = service.create_contact({"cliente_id": "c-1", "nombre": "Ana"})
    service.update_contact("contact-1", {"cargo": "Compras"})

    assert created.contacto_id == "created-1"
    assert len(fake_contact_vm.create_calls) == 1
    assert len(fake_contact_vm.update_calls) == 1


def test_upsert_contact_updates_or_creates(monkeypatch) -> None:
    from app.services import customer_contact_flow_service as module

    fake_session = _FakeSession()
    monkeypatch.setattr(module, "Session", _FakeSessionFactory(fake_session))
    fake_contact_vm = _FakeContactVM()
    service = CustomerContactFlowService(engine=object(), contact_vm=fake_contact_vm)

    updated_id = service.upsert_contact("contact-9", {"cliente_id": "c-1"})
    created_id = service.upsert_contact("", {"cliente_id": "c-1"})

    assert updated_id == "contact-9"
    assert created_id == "created-1"
    assert len(fake_contact_vm.update_calls) == 1
    assert len(fake_contact_vm.create_calls) == 1


def test_get_contact_and_unlink_contact_creates_unlinked_customer(monkeypatch) -> None:
    from app.services import customer_contact_flow_service as module

    fake_session = _FakeSession(contact=_FakeContacto("contact-1", "customer-1"))
    monkeypatch.setattr(module, "Session", _FakeSessionFactory(fake_session))
    fake_customer_vm = _FakeCustomerVM()
    fake_contact_vm = _FakeContactVM()
    service = CustomerContactFlowService(engine=object(), customer_vm=fake_customer_vm, contact_vm=fake_contact_vm)

    contact = service.get_contact("contact-1")
    assert contact.contacto_id == "contact-1"

    service.unlink_contact("contact-1", "unlinked-1")

    assert fake_customer_vm.create_calls[0][1]["cliente_id"] == "unlinked-1"
    assert fake_contact_vm.update_calls[0][2]["cliente_id"] == "unlinked-1"


def test_ensure_unlinked_customer_reuses_existing(monkeypatch) -> None:
    from app.services import customer_contact_flow_service as module

    fake_session = _FakeSession(customer=object())
    monkeypatch.setattr(module, "Session", _FakeSessionFactory(fake_session))
    fake_customer_vm = _FakeCustomerVM()
    service = CustomerContactFlowService(engine=object(), customer_vm=fake_customer_vm)

    service.ensure_unlinked_customer("unlinked-1")

    assert fake_customer_vm.create_calls == []


def test_unlink_contact_raises_for_missing_contact(monkeypatch) -> None:
    from app.services import customer_contact_flow_service as module

    fake_session = _FakeSession(contact=None)
    monkeypatch.setattr(module, "Session", _FakeSessionFactory(fake_session))
    service = CustomerContactFlowService(engine=object())

    try:
        service.unlink_contact("missing", "unlinked-1")
    except ValueError as exc:
        assert "Contacto no encontrado" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing contact")


def test_get_contact_returns_none_for_blank_id(monkeypatch) -> None:
    from app.services import customer_contact_flow_service as module

    fake_session = _FakeSession()
    monkeypatch.setattr(module, "Session", _FakeSessionFactory(fake_session))
    service = CustomerContactFlowService(engine=object())

    assert service.get_contact("   ") is None
