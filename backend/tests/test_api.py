import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert any(p["name"] == "demo" for p in body["providers"])


def test_meta(client):
    body = client.get("/api/v1/meta").json()
    codes = [c["code"] for c in body["categories"]]
    assert codes == ["individual", "legal_entity"]
    assert {v["code"] for v in body["views"]} == {"open", "closed"}


def test_instruments(client):
    body = client.get("/api/v1/instruments", params={"query": "SBER"}).json()
    assert body["total"] >= 1
    assert any(item["ticker"] == "SBERF" for item in body["items"])


def test_instruments_include_index_futures(client):
    body = client.get("/api/v1/instruments").json()
    tickers = {item["ticker"] for item in body["items"]}
    assert {"IMOEX", "MIX", "RTS"} <= tickers, "индексные фьючерсы должны быть в списке"


def test_positions_open(client):
    body = client.get("/api/v1/positions", params={"limit": 10}).json()
    assert body["view"] == "open"
    assert body["total"] > 0
    assert len(body["items"]) == 10
    row = body["items"][0]
    assert {"ticker", "name", "date", "fiz", "jur", "total"} <= set(row)
    assert row["fiz"]["long"] >= 0 and row["jur"]["short"] >= 0
    assert body["source"]["provider"] == "demo"


def test_positions_tickers_filter(client):
    body = client.get("/api/v1/positions", params={"tickers": "SBRF,GAZR", "limit": 10}).json()
    assert body["total"] == 2
    assert {row["ticker"] for row in body["items"]} == {"SBRF", "GAZR"}


def test_positions_open_sorted_by_total(client):
    body = client.get(
        "/api/v1/positions", params={"sort": "total", "order": "desc", "limit": 100}
    ).json()
    totals = [row["total"] for row in body["items"]]
    assert totals == sorted(totals, reverse=True)


def test_positions_closed_non_negative(client):
    body = client.get(
        "/api/v1/positions", params={"view": "closed", "limit": 100}
    ).json()
    assert body["view"] == "closed"
    assert body["items"]
    for row in body["items"]:
        assert row["fiz_long_closed"] >= 0
        assert row["jur_short_closed"] >= 0


def test_history(client):
    body = client.get(
        "/api/v1/positions/history", params={"ticker": "GAZR", "days": 14}
    ).json()
    assert body["ticker"] == "GAZR"
    dates = [p["date"] for p in body["points"]]
    assert dates == sorted(dates)
    assert len(dates) <= 14
    assert body["aggregates"]["fiz_long_closed"] >= 0
    assert body["price_label"], "должна быть подпись цены базового актива"
    assert body["prices"], "история должна содержать цены базового актива"
    price_dates = [p["date"] for p in body["prices"]]
    assert price_dates == sorted(price_dates)


def test_history_unknown_ticker(client):
    response = client.get("/api/v1/positions/history", params={"ticker": "XXXX"})
    assert response.status_code == 404


def test_totals_history(client):
    body = client.get("/api/v1/positions/totals-history", params={"days": 14}).json()
    assert body["instruments"] > 0
    points = body["points"]
    assert 2 <= len(points) <= 14
    dates = [p["date"] for p in points]
    assert dates == sorted(dates)
    for point in points:
        assert point["total"] == (
            point["fiz_long"] + point["fiz_short"] + point["jur_long"] + point["jur_short"]
        )
    assert body["price_label"] == "Индекс МосБиржи"
    assert body["prices"], "динамика рынка должна содержать цены индекса"


def test_summary_shares(client):
    body = client.get("/api/v1/positions/summary").json()
    assert len(body["items"]) == 2
    assert body["instruments"] > 0, "в сводке должно быть число инструментов"
    shares = [item["share_pct"] for item in body["items"]]
    assert abs(sum(shares) - 100.0) < 0.5
    for item in body["items"]:
        assert item["net"] == item["long"] - item["short"]
