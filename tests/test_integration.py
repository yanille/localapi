import asyncio
import datetime as dt
import warnings
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from localapi import LocalAPI


class Point(BaseModel):
    x: int
    y: int


@pytest.fixture
def app():
    app = LocalAPI(title="My Tools", version="1.0")

    @app.endpoint
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    @app.endpoint
    def greet(name: str, excited: bool = False) -> str:
        return f"Hello {name}" + ("!" if excited else "")

    @app.get
    def status() -> dict:
        return {"status": "ok", "version": "1.0"}

    @app.get
    def square(n: int, offset: int = 0) -> int:
        return n * n + offset

    @app.endpoint
    def divide(a: float, b: float) -> float:
        if b == 0:
            raise ValueError("b must be non-zero")
        return a / b

    @app.endpoint
    async def slow_double(n: int) -> int:
        await asyncio.sleep(0)
        return n * 2

    @app.endpoint
    def ping():
        return "pong"

    @app.endpoint
    def shift(p: Point, dx: int = 1) -> Point:
        return Point(x=p.x + dx, y=p.y)

    @app.endpoint
    def when() -> dict:
        return {"at": dt.date(2026, 9, 26), "where": Path("/tmp")}

    @app.endpoint
    def maybe(count: int = 3) -> list[int]:
        return list(range(count))

    return app


@pytest.fixture
def client(app):
    return TestClient(app.asgi, raise_server_exceptions=False)


def test_quickstart(client):
    assert client.post("/add", json={"a": 10, "b": 20}).json() == {"result": 30}


def test_string_result_is_enveloped(client):
    r = client.post("/greet", json={"name": "Ada", "excited": True})
    assert r.status_code == 200
    assert r.json() == {"result": "Hello Ada!"}


def test_default_values(client):
    assert client.post("/greet", json={"name": "Ada"}).json() == {"result": "Hello Ada"}


def test_all_optional_body_can_be_omitted(client):
    assert client.post("/maybe").json() == {"result": [0, 1, 2]}
    assert client.post("/maybe", json={"count": 1}).json() == {"result": [0]}


def test_get_endpoint(client):
    assert client.get("/status").json() == {"result": {"status": "ok", "version": "1.0"}}
    assert client.get("/square", params={"n": 4}).json() == {"result": 16}
    assert client.get("/square", params={"n": 4, "offset": 1}).json() == {"result": 17}


def test_get_validation(client):
    r = client.get("/square", params={"n": "four"})
    assert r.status_code == 422
    assert r.json()["detail"][0]["field"] == "n"


def test_validation_error_envelope(client):
    r = client.post("/add", json={"a": "x", "b": 2})
    assert r.status_code == 422
    assert r.json() == {
        "error": "validation_error",
        "detail": [{"field": "a", "message": "Input should be a valid integer, unable to parse string as an integer"}],
    }


def test_missing_field_and_missing_body(client):
    r = client.post("/add", json={"a": 1})
    assert r.status_code == 422
    assert r.json()["detail"][0]["field"] == "b"
    assert client.post("/add").status_code == 422


def test_invalid_json(client):
    r = client.post("/add", content=b"{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"


def test_exception_becomes_500(client):
    r = client.post("/divide", json={"a": 1, "b": 0})
    assert r.status_code == 500
    assert r.json() == {"error": "ValueError", "detail": "b must be non-zero"}


def test_async_function(client):
    assert client.post("/slow_double", json={"n": 21}).json() == {"result": 42}


def test_zero_arg_post(client):
    assert client.post("/ping").json() == {"result": "pong"}


def test_nested_models(client):
    r = client.post("/shift", json={"p": {"x": 1, "y": 2}, "dx": 5})
    assert r.json() == {"result": {"x": 6, "y": 2}}


def test_rich_return_serialization(client):
    assert client.post("/when").json() == {"result": {"at": "2026-09-26", "where": "/tmp"}}


def test_not_found_and_wrong_method(client):
    r = client.get("/nope")
    assert r.status_code == 404
    assert r.json() == {"error": "not_found", "detail": "Not Found"}
    assert client.get("/add").status_code == 405


def test_openapi_schema(client):
    schema = client.get("/openapi.json").json()
    assert schema["info"] == {"title": "My Tools", "version": "1.0"}
    op = schema["paths"]["/add"]["post"]
    assert op["description"] == "Add two numbers."
    assert op["requestBody"]["required"] is True
    body_ref = op["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    body = schema["components"]["schemas"][body_ref.rsplit("/", 1)[1]]
    assert body["required"] == ["a", "b"]
    assert body["properties"]["a"]["type"] == "integer"
    assert {"422", "500"} <= set(op["responses"])
    assert "get" in schema["paths"]["/status"]
    assert [p["name"] for p in schema["paths"]["/square"]["get"]["parameters"]] == ["n", "offset"]
    assert client.get("/docs").status_code == 200


def test_endpoint_registered_after_build(app, client):
    @app.endpoint
    def late() -> str:
        return "here"

    assert client.post("/late").json() == {"result": "here"}
    assert "/late" in client.get("/openapi.json").json()["paths"]


def test_run_defaults_to_loopback_and_warns_otherwise(monkeypatch, app):
    import uvicorn

    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda asgi, **kw: calls.append(kw))

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        app.run()
    assert calls[-1]["host"] == "127.0.0.1" and calls[-1]["port"] == 8000

    with pytest.warns(UserWarning, match="0.0.0.0"):
        app.run(host="0.0.0.0", port=9000)
    assert calls[-1]["host"] == "0.0.0.0"
