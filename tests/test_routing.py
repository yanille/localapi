import pytest

from localapi import LocalAPI, api
from localapi.routing import make_spec


def test_function_name_is_route_and_post_is_default():
    app = LocalAPI()

    @app.post
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    (spec,) = app.endpoints
    assert (spec.path, spec.method, spec.name) == ("/add", "POST", "add")
    assert spec.description == "Add two numbers."
    assert spec.return_annotation is int
    assert not spec.is_async


def test_decorators_return_original_function():
    app = LocalAPI()

    def add(a: int, b: int) -> int:
        return a + b

    assert app.post(add) is add
    assert app.get(path="/other")(add) is add
    assert add(1, 2) == 3


def test_decorator_options():
    app = LocalAPI()

    @app.post(path="math/add", name="Addition")
    def add(a: int, b: int) -> int: ...

    (spec,) = app.endpoints
    assert (spec.path, spec.name) == ("/math/add", "Addition")


def test_get_decorator():
    app = LocalAPI()

    @app.get
    def status() -> dict: ...

    assert app.endpoints[0].method == "GET"


def test_one_decorator_per_method():
    app = LocalAPI()
    for method in ("get", "post", "put", "patch", "delete"):
        getattr(app, method)(path=f"/{method}")(lambda: None)
    assert [s.method for s in app.endpoints] == ["GET", "POST", "PUT", "PATCH", "DELETE"]
    assert not hasattr(app, "endpoint")


def test_duplicate_route_raises():
    app = LocalAPI()

    @app.post
    def add(a: int, b: int): ...

    with pytest.raises(ValueError, match="already registered"):

        @app.post(path="/add")
        def other(): ...


def test_same_path_different_methods_allowed():
    app = LocalAPI()
    app.get(path="/item")(lambda: None)
    app.delete(path="/item")(lambda: None)
    assert len(app.endpoints) == 2


def test_async_detected():
    async def f(): ...

    assert make_spec(f, "POST").is_async


def test_get_rejects_kwargs():
    with pytest.raises(TypeError, match="GET"):
        LocalAPI().get(lambda **kw: None)


def test_default_app_is_callable_decorator():
    def some_unique_tool(): ...

    assert api(some_unique_tool) is some_unique_tool
    assert any(s.path == "/some_unique_tool" for s in api.endpoints)


def test_init_options():
    app = LocalAPI(title="Tools", version="2.1")
    assert (app.title, app.version) == ("Tools", "2.1")
    assert LocalAPI().version == "0.1.0"
    with pytest.raises(TypeError):
        LocalAPI(description="x")
