"""In-process API client: the seeder drives the same routers and services the UI uses."""
from __future__ import annotations

from typing import Any

import httpx


class DemoSeedError(RuntimeError):
    pass


class DemoApi:
    def __init__(self, app) -> None:
        self._http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://demo.local/api", timeout=120)
        self.user: dict[str, Any] = {}
        self.tenant: dict[str, Any] = {}

    async def login(self) -> None:
        r = await self._http.post("/auth/dev-login")
        if r.status_code != 200:
            raise DemoSeedError(f"dev-login failed: {r.status_code} {r.text[:200]}")
        body = r.json()
        self._http.headers["Authorization"] = f"Bearer {body['access_token']}"
        self.user, self.tenant = body["user"], body["tenant"]

    async def call(self, method: str, path: str, *, ok: tuple[int, ...] = (200, 201, 202, 204), **kw) -> Any:
        r = await self._http.request(method, path, **kw)
        if r.status_code not in ok:
            raise DemoSeedError(f"{method} {path} -> {r.status_code}: {r.text[:400]}")
        return r.json() if r.content else None

    async def get(self, path: str, **params) -> Any:
        return await self.call("GET", path, params=params or None)

    async def post(self, path: str, body: dict | None = None, **kw) -> Any:
        return await self.call("POST", path, json=body if body is not None else {}, **kw)

    async def patch(self, path: str, body: dict) -> Any:
        return await self.call("PATCH", path, json=body)

    async def put(self, path: str, body: dict) -> Any:
        return await self.call("PUT", path, json=body)

    async def items(self, path: str, **params) -> list[dict]:
        """List endpoint -> list of records regardless of whether it wraps them in a key."""
        data = await self.get(path, **params)
        if isinstance(data, list):
            return data
        for key in ("items", "results", "data", "records"):
            if isinstance(data.get(key), list):
                return data[key]
        lists = [v for v in data.values() if isinstance(v, list)]
        return lists[0] if lists else []

    async def aclose(self) -> None:
        await self._http.aclose()
