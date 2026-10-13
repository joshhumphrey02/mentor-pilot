from httpx import AsyncClient


async def test_health_reports_database_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["environment"] == "test"


async def test_responses_carry_request_id_and_security_headers(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.headers["x-request-id"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    # HSTS is prod-only: sending it from localhost would pin http dev servers to https.
    assert "strict-transport-security" not in response.headers
