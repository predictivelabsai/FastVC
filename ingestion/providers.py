from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class ProviderError(RuntimeError):
    pass


@dataclass(slots=True)
class ProviderResponse:
    data: Any
    credits_used: float = 0
    credits_remaining: str = ""
    rate_remaining: str = ""


class JsonProvider:
    def __init__(self, *, timeout: float = 30):
        self.client = httpx.Client(timeout=timeout, follow_redirects=True,
                                   headers={"User-Agent": "FastVC/1.0 (+https://fastvc.org)"})

    def _json(self, method: str, url: str, **kwargs) -> tuple[Any, httpx.Headers]:
        response = self.client.request(method, url, **kwargs)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text[:500].replace("\n", " ")
            raise ProviderError(f"{response.status_code} from provider: {detail}") from exc
        try:
            return response.json(), response.headers
        except ValueError as exc:
            raise ProviderError("Provider returned a non-JSON response") from exc


class PappersClient(JsonProvider):
    base_url = "https://api.pappers.fr/v2"

    def __init__(self, api_key: str, **kwargs):
        super().__init__(**kwargs)
        if not api_key:
            raise ValueError("PAPPERS_API_KEY is required")
        self.api_key = api_key

    def search(self, query: str, *, page: int = 1, per_page: int = 10) -> ProviderResponse:
        data, headers = self._json("GET", f"{self.base_url}/recherche", params={
            "api_token": self.api_key, "q": query, "page": page, "par_page": min(per_page, 100),
        })
        return ProviderResponse(data=data, credits_used=0.1 * len(data.get("resultats", [])))

    def company(self, siren: str) -> ProviderResponse:
        data, headers = self._json("GET", f"{self.base_url}/entreprise", params={
            "api_token": self.api_key, "siren": siren,
        })
        return ProviderResponse(data=data, credits_used=1)


class ScorisClient(JsonProvider):
    base_url = "https://scoris.eu/api/v1"

    def __init__(self, api_key: str, **kwargs):
        super().__init__(**kwargs)
        if not api_key:
            raise ValueError("SCORIS_API_KEY is required")
        self.headers = {"X-API-Key": api_key}

    def search(self, query: str, *, country: str = "") -> ProviderResponse:
        params = {"q": query}
        if country:
            params["country"] = country
        data, headers = self._json("GET", f"{self.base_url}/company-search/",
                                   params=params, headers=self.headers)
        return self._response(data, headers)

    def filter(self, filters: dict) -> ProviderResponse:
        data, headers = self._json("POST", f"{self.base_url}/company-filter/",
                                   json=filters, headers=self.headers)
        return self._response(data, headers)

    def company(self, country: str, registry_id: str) -> ProviderResponse:
        data, headers = self._json("GET", f"{self.base_url}/company/{country}/{registry_id}/",
                                   headers=self.headers)
        return self._response(data, headers)

    @staticmethod
    def _response(data: Any, headers: httpx.Headers) -> ProviderResponse:
        cost = headers.get("x-api-request-cost", "0")
        try:
            credits = float(cost)
        except ValueError:
            credits = 0
        return ProviderResponse(data=data, credits_used=credits,
                                credits_remaining=headers.get("x-api-credits-remaining", ""),
                                rate_remaining=headers.get("x-ratelimit-remaining", ""))


class CompaniesHouseClient(JsonProvider):
    base_url = "https://api.company-information.service.gov.uk"

    def __init__(self, api_key: str, **kwargs):
        super().__init__(**kwargs)
        if not api_key:
            raise ValueError("CH_API_KEY is required")
        self.auth = httpx.BasicAuth(api_key, "")

    def search(self, query: str, *, items_per_page: int = 20, start_index: int = 0) -> ProviderResponse:
        data, headers = self._json("GET", f"{self.base_url}/search/companies", auth=self.auth,
                                   params={"q": query, "items_per_page": min(items_per_page, 100),
                                           "start_index": start_index})
        return ProviderResponse(data=data, rate_remaining=headers.get("x-ratelimit-remain", ""))

    def advanced_search(self, **filters) -> ProviderResponse:
        params = {key: value for key, value in filters.items() if value not in (None, "", [])}
        data, headers = self._json("GET", f"{self.base_url}/advanced-search/companies",
                                   auth=self.auth, params=params)
        return ProviderResponse(data=data, rate_remaining=headers.get("x-ratelimit-remain", ""))

    def company(self, company_number: str) -> ProviderResponse:
        data, headers = self._json("GET", f"{self.base_url}/company/{company_number}", auth=self.auth)
        return ProviderResponse(data=data, rate_remaining=headers.get("x-ratelimit-remain", ""))


class SireneClient(JsonProvider):
    base_url = "https://api.insee.fr/api-sirene/3.11"

    def __init__(self, api_key: str = "", **kwargs):
        super().__init__(**kwargs)
        self.headers = {"X-INSEE-Api-Key-Integration": api_key} if api_key else {}

    def search(self, query: str, *, limit: int = 20, offset: int = 0) -> ProviderResponse:
        data, _ = self._json("GET", f"{self.base_url}/siren",
                             params={"q": query, "nombre": min(limit, 1000), "debut": offset},
                             headers=self.headers)
        return ProviderResponse(data=data)

    def company(self, siren: str) -> ProviderResponse:
        data, _ = self._json("GET", f"{self.base_url}/siren/{siren}", headers=self.headers)
        return ProviderResponse(data=data)


class PrhClient(JsonProvider):
    base_url = "https://avoindata.prh.fi/opendata-ytj-api/v3"

    def search(self, *, name: str = "", business_id: str = "", location: str = "",
               page: int = 1) -> ProviderResponse:
        params = {"page": page}
        if name:
            params["name"] = name
        if business_id:
            params["businessId"] = business_id
        if location:
            params["location"] = location
        data, _ = self._json("GET", f"{self.base_url}/companies", params=params)
        return ProviderResponse(data=data)

    def all_companies(self) -> ProviderResponse:
        data, _ = self._json("GET", f"{self.base_url}/all_companies")
        return ProviderResponse(data=data)
