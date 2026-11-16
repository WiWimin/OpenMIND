"""未捕获 500 的 CORS 回归。

背景：未捕获异常由最外层 `ServerErrorMiddleware` 直接生成 500。若 `CORSMiddleware`
注册在它内层，该 500 不会携带 CORS 头，浏览器会把它误报为「Network Error」，
掩盖真实的服务端故障。此用例保证 CORS 始终位于最外层。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

_ORIGIN = "http://localhost:5173"


def _boom() -> None:
    raise RuntimeError("boom for cors regression")


def test_unhandled_500_keeps_cors_headers() -> None:
    app.add_route("/_test_boom", _boom)
    try:
        # 不进入 context manager：不触发 lifespan（避免测试启动期访问数据库）；
        # raise_server_exceptions=False 才能拿到 ServerErrorMiddleware 生成的 500
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/_test_boom", headers={"Origin": _ORIGIN})
    finally:
        app.routes[:] = [
            route
            for route in app.routes
            if getattr(route, "path", None) != "/_test_boom"
        ]

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") == _ORIGIN
    body = response.json()
    assert body["status"] == "error"
    assert body["error_code"] == "INTERNAL_ERROR"
    assert body["message"]


def test_handled_error_keeps_cors_headers() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/does-not-exist", headers={"Origin": _ORIGIN})
    assert response.status_code == 404
    assert response.headers.get("access-control-allow-origin") == _ORIGIN
    assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_preflight_is_answered_with_cors_headers() -> None:
    client = TestClient(app)
    response = client.options(
        "/api/v1/does-not-exist",
        headers={
            "Origin": _ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == _ORIGIN
