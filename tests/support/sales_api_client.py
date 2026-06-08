from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.schemas.sales import SalesAnnualSummaryResponse, SalesFilterOptionsResponse, SalesYearOptionsResponse


@dataclass(slots=True)
class SalesApiClient:
    client: TestClient

    def annual_summary(
        self,
        year: int,
        month: int = 0,
        acumulado: bool = False,
        cliente_id: str = "",
        articulo_id: str = "",
        producto_texto: str = "",
        fabricante_id: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
    ) -> SalesAnnualSummaryResponse:
        params = {
            "year": year,
            "month": month,
            "acumulado": acumulado,
            "cliente_id": cliente_id,
            "articulo_id": articulo_id,
            "producto_texto": producto_texto,
            "fabricante_id": fabricante_id,
            "familia_id": familia_id,
            "subfamilia_id": subfamilia_id,
        }
        return self._get_model("/sales/annual-summary", params, SalesAnnualSummaryResponse)

    def annual_summary_igsa(
        self,
        year: int,
        month: int = 0,
        acumulado: bool = False,
        producto_texto: str = "",
        fabricante_id: str = "",
        familia_id: str = "",
        subfamilia_id: str = "",
    ) -> SalesAnnualSummaryResponse:
        params = {
            "year": year,
            "month": month,
            "acumulado": acumulado,
            "producto_texto": producto_texto,
            "fabricante_id": fabricante_id,
            "familia_id": familia_id,
            "subfamilia_id": subfamilia_id,
        }
        return self._get_model("/sales/annual-summary/igsa", params, SalesAnnualSummaryResponse)

    def years(self) -> SalesYearOptionsResponse:
        return self._get_model("/sales/annual-summary/years", {}, SalesYearOptionsResponse)

    def years_igsa(self) -> SalesYearOptionsResponse:
        return self._get_model("/sales/annual-summary/igsa/years", {}, SalesYearOptionsResponse)

    def clients(self) -> SalesFilterOptionsResponse:
        return self._get_model("/sales/annual-summary/filters/clients", {}, SalesFilterOptionsResponse)

    def products(self) -> SalesFilterOptionsResponse:
        return self._get_model("/sales/annual-summary/filters/products", {}, SalesFilterOptionsResponse)

    def manufacturers(self) -> SalesFilterOptionsResponse:
        return self._get_model("/sales/annual-summary/filters/manufacturers", {}, SalesFilterOptionsResponse)

    def manufacturers_igsa(self) -> SalesFilterOptionsResponse:
        return self._get_model("/sales/annual-summary/igsa/filters/manufacturers", {}, SalesFilterOptionsResponse)

    def families(self, fabricante_id: str = "") -> SalesFilterOptionsResponse:
        return self._get_model(
            "/sales/annual-summary/filters/families",
            {"fabricante_id": fabricante_id},
            SalesFilterOptionsResponse,
        )

    def families_igsa(self, fabricante_id: str = "") -> SalesFilterOptionsResponse:
        return self._get_model(
            "/sales/annual-summary/igsa/filters/families",
            {"fabricante_id": fabricante_id},
            SalesFilterOptionsResponse,
        )

    def subfamilies(self, familia_id: str = "") -> SalesFilterOptionsResponse:
        return self._get_model(
            "/sales/annual-summary/filters/subfamilies",
            {"familia_id": familia_id},
            SalesFilterOptionsResponse,
        )

    def subfamilies_igsa(self, familia_id: str = "") -> SalesFilterOptionsResponse:
        return self._get_model(
            "/sales/annual-summary/igsa/filters/subfamilies",
            {"familia_id": familia_id},
            SalesFilterOptionsResponse,
        )

    def _get_model(self, path: str, params: dict[str, object], model_type):
        response = self.client.get(path, params=params)
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"Sales API request failed ({response.status_code}) for {path}: {response.text}")
        return model_type.model_validate(response.json())

