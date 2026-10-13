from httpx import AsyncClient


async def test_root_serves_index_without_caching(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert "Mentor Pilot" in response.text
    assert response.headers["cache-control"] == "no-cache"


async def test_deep_link_falls_back_to_index(client: AsyncClient) -> None:
    response = await client.get("/projects/123/chat")

    assert response.status_code == 200
    assert "Mentor Pilot" in response.text
    assert response.headers["cache-control"] == "no-cache"


async def test_hashed_assets_are_cached_forever(client: AsyncClient) -> None:
    response = await client.get("/assets/app-abc123.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


async def test_root_level_files_are_served_and_revalidated(client: AsyncClient) -> None:
    response = await client.get("/manifest.webmanifest")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


async def test_missing_asset_is_404_not_index(client: AsyncClient) -> None:
    assert (await client.get("/assets/missing.js")).status_code == 404
    assert (await client.get("/favicon.ico")).status_code == 404


async def test_unknown_api_route_is_json_404_not_index(client: AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


async def test_path_traversal_cannot_escape_static_dir(client: AsyncClient) -> None:
    response = await client.get("/..%2F..%2Fpyproject.toml")

    assert response.status_code == 404
