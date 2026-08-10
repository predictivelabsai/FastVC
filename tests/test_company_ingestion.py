from __future__ import annotations

from ingestion.models import NormalizedCompany
from ingestion.normalize import clean_website, normalize_registry_record, slugify
from ingestion.service import select_registry_cohort
from ingestion.backfill import normalize_provider_record
from ingestion.providers import PappersClient


def test_registry_normalization_preserves_real_annual_periods():
    raw = {
        "name": "Example OÜ", "reg_code": "12345678", "vat": "EE123456789",
        "address": "Harju maakond, Tallinn linn, Test 1", "founded": "12.03.2019",
        "website": "example.ee\n extra page text", "sector": "software",
        "sub_sector": "Application software",
        "financials": [
            {"year": 2023, "sales_revenue": 100_000, "net_profit": 5_000},
            {"year": 2024, "sales_revenue": 150_000},
            {"year": 2024, "sales_revenue": 12_500, "net_profit": 10_000, "equity": 80_000},
        ],
    }
    company = normalize_registry_record(raw, "EE")
    assert company is not None
    assert company.registry_id == "12345678"
    assert company.hq_city == "Tallinn"
    assert company.website == "https://example.ee"
    assert company.revenue == 150_000
    assert company.growth_rate == 50.0
    assert len(company.financials) == 2
    assert company.financials[-1].net_profit == 10_000


def test_slug_and_website_cleanup_are_deterministic():
    assert slugify("Žalias AI, UAB", country="LT", external_id="123") == "zalias-ai-uab-lt123"
    assert clean_website("https://example.com\nClose modal") == "https://example.com"


def test_cohort_selection_respects_country_quotas_and_quality():
    rows = []
    for country in ("LT", "EE", "LV"):
        for index in range(5):
            rows.append(NormalizedCompany(
                source=f"registry_{country.lower()}", external_id=str(index), country=country,
                name=f"{country} {index}", registry_id=str(index), revenue=100,
                quality=float(index),
            ))
    cohort = select_registry_cohort(rows, limit=6, quotas={"LT": 2, "EE": 2, "LV": 2})
    assert len(cohort) == 6
    assert {country: sum(row.country == country for row in cohort) for country in ("LT", "EE", "LV")} == {
        "LT": 2, "EE": 2, "LV": 2,
    }
    assert {row.quality for row in cohort if row.country == "EE"} == {3.0, 4.0}


def test_bulk_provider_normalizers_preserve_registry_identity():
    pappers = normalize_provider_record("pappers", {
        "siren": "123456789", "nom_entreprise": "Example SAS", "date_creation": "2021-03-02",
        "effectif": 12, "siege": {"adresse_ligne_1": "1 Rue Test", "ville": "Paris"},
    })
    sirene = normalize_provider_record("sirene", {
        "siren": "987654321", "dateCreationUniteLegale": "2020-01-01",
        "trancheEffectifsUniteLegale": "11",
        "periodesUniteLegale": [{"dateFin": None, "denominationUniteLegale": "Example AI",
                                  "etatAdministratifUniteLegale": "A",
                                  "activitePrincipaleUniteLegale": "62.01Z"}],
    })
    prh = normalize_provider_record("prh", {
        "businessId": {"value": "1234567-8", "registrationDate": "2019-01-01"},
        "names": [{"name": "Example Oy"}], "website": {"url": "example.fi"},
        "addresses": [], "mainBusinessLine": {"descriptions": []}, "status": "active",
    })
    assert pappers and pappers.country == "FR" and pappers.employees == 12
    assert sirene and sirene.employees == 15 and sirene.registry_status == "active"
    assert prh and prh.website == "https://example.fi" and prh.registry_id == "1234567-8"


def test_pappers_cursor_search_uses_cursor_parameters(monkeypatch):
    client = PappersClient("test-key")
    captured = {}

    def fake_json(method, url, **kwargs):
        captured.update(kwargs["params"])
        return {"resultats": [{}], "curseurSuivant": "next"}, {}

    monkeypatch.setattr(client, "_json", fake_json)
    response = client.search("logiciel", cursor="*", per_page=100)

    assert captured == {
        "api_token": "test-key", "q": "logiciel", "curseur": "*", "par_curseur": 100,
    }
    assert response.credits_used == 0.1
