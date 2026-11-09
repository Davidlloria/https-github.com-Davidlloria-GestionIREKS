import pytest
from app.services.igsa_monthly_catalog_service import historical_reference

@pytest.mark.parametrize('reference,period,expected', [
 ('27553','2026-07','275021'), ('275021','2026-08','27553'),
 ('D1415178','2026-04','D1415185'), ('D1415185','2026-05','D1415178'),
 ('27553','invalid','27553'), ('OTHER','2026-08','OTHER'),
])
def test_historical_reference(reference, period, expected):
    assert historical_reference(reference, period) == expected

def test_distributor_duplicate_softy_resolves_for_month():
    from types import SimpleNamespace
    from app.services.igsa_monthly_catalog_service import IgsaMonthlyCatalog
    products = [SimpleNamespace(articulo_id=key, articulo_referencia_corta=ref, articulo_referencia=ref, articulo_descripcion="SOFTY") for key, ref in [("old", "275021"), ("new", "27553")]]
    refs = [SimpleNamespace(articulo_id=p.articulo_id, articulo_referencia_distribuidor="72") for p in products]
    catalog = IgsaMonthlyCatalog(refs, products)
    assert catalog.distributor_product("72", "2026-07")[0].product_id == "OLD"
    assert catalog.distributor_product("72", "2026-08")[0].product_id == "NEW"
    assert catalog.distributor_product("72", "")[1] == "referencia_ambigua"
