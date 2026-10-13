from fastapi import FastAPI
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


def test_every_endpoint_has_its_own_operation_id(app: FastAPI) -> None:
    """Two endpoints sharing a function name share an operation id, and the
    generated frontend client then silently mixes up their types."""
    seen: dict[str, str] = {}
    for path, methods in app.openapi()["paths"].items():
        for method, operation in methods.items():
            name = operation["operationId"]
            assert name not in seen, f"{method.upper()} {path} reuses '{name}' from {seen[name]}"
            seen[name] = f"{method.upper()} {path}"
