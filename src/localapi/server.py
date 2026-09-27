"""The ``LocalAPI`` class: turns registered endpoints into FastAPI routes and serves them."""

from __future__ import annotations

import inspect
import ipaddress
import logging
import warnings
from typing import Any, Callable, Optional

from fastapi import Body, FastAPI, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, create_model
from starlette.exceptions import HTTPException as StarletteHTTPException

from localapi import serialization
from localapi.routing import EndpointSpec, Registry, make_spec
from localapi.validation import call_kwargs, get_hints

logger = logging.getLogger("localapi")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


class ErrorResponse(BaseModel):
    error: str
    detail: Any = None


_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Validation error"},
    500: {"model": ErrorResponse, "description": "The function raised an exception"},
}


class LocalAPI:
    """A collection of Python functions exposed as HTTP endpoints.

    >>> app = LocalAPI()
    >>> @app.endpoint
    ... def add(a: int, b: int) -> int:
    ...     return a + b
    """

    def __init__(self, title: str = "localapi", version: str = "0.1.0", description: str | None = None) -> None:
        self.title = title
        self.version = version
        self.description = description
        self._registry = Registry()
        self._fastapi: FastAPI | None = None
        self._mounted: set[str] = set()

    # -- Registration -------------------------------------------------------

    def endpoint(self, func: Callable[..., Any] | None = None, *, path: str | None = None, name: str | None = None):
        """Expose ``func`` as ``POST /<name>`` taking a JSON body. Usable bare or with options."""
        return self._decorate("POST", func, path, name)

    def get(self, func: Callable[..., Any] | None = None, *, path: str | None = None, name: str | None = None):
        """Expose ``func`` as ``GET /<name>`` taking query-string parameters."""
        return self._decorate("GET", func, path, name)

    # ``@api`` is shorthand for ``@api.endpoint`` (D-05).
    __call__ = endpoint

    def _decorate(self, method: str, func, path, name):
        def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
            spec = make_spec(fn, method, path=path, name=name)
            self._registry.add(spec)
            if self._fastapi is not None:
                self._mount(spec)
            return fn  # returned unchanged (D-07)

        return wrap if func is None else wrap(func)

    @property
    def endpoints(self) -> list[EndpointSpec]:
        return list(self._registry)

    # -- ASGI app -----------------------------------------------------------

    @property
    def asgi(self) -> FastAPI:
        """The underlying FastAPI app, built on first access. Usable with any ASGI server or TestClient."""
        if self._fastapi is None:
            self._fastapi = self._build()
            for spec in self._registry:
                self._mount(spec)
        return self._fastapi

    def _build(self) -> FastAPI:
        app = FastAPI(title=self.title, version=self.version, description=self.description or "")

        @app.exception_handler(RequestValidationError)
        async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
            detail = [
                {"field": _field_name(err.get("loc", ())), "message": err.get("msg", "")}
                for err in exc.errors()
            ]
            return JSONResponse(serialization.error("validation_error", detail), status_code=422)

        @app.exception_handler(StarletteHTTPException)
        async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
            kind = _snake(exc.detail) if isinstance(exc.detail, str) else "http_error"
            return JSONResponse(
                serialization.error(kind, exc.detail), status_code=exc.status_code, headers=getattr(exc, "headers", None)
            )

        return app

    def _mount(self, spec: EndpointSpec) -> None:
        if spec.path in self._mounted:
            return
        app = self._fastapi
        assert app is not None
        handler = _make_get_handler(spec) if spec.method == "GET" else _make_post_handler(spec)
        app.add_api_route(
            spec.path,
            handler,
            methods=[spec.method],
            name=spec.name,
            summary=spec.name,
            description=spec.description or "",
            response_model=_response_model(spec),
            responses=_ERROR_RESPONSES,
            operation_id=spec.name,
        )
        app.openapi_schema = None  # regenerate docs to include late registrations
        self._mounted.add(spec.path)

    # -- Serving ------------------------------------------------------------

    def run(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, log_level: str = "info", **uvicorn_kwargs: Any) -> None:
        """Serve the endpoints with Uvicorn. Binds to 127.0.0.1 unless told otherwise (D-06)."""
        import uvicorn

        if not _is_loopback(host):
            warnings.warn(
                f"localapi is binding to {host!r}, which may expose your functions to other machines "
                "on the network. Only do this on a trusted network.",
                stacklevel=2,
            )
        app = self.asgi
        print(f"localapi: serving {len(self._registry)} endpoint(s) at http://{host}:{port}  (docs: /docs)")
        for spec in self._registry:
            print(f"  {spec.method:<5} {spec.path}")
        uvicorn.run(app, host=host, port=port, log_level=log_level, **uvicorn_kwargs)


# -- Handlers ---------------------------------------------------------------


async def _invoke(spec: EndpointSpec, kwargs: dict[str, Any]) -> JSONResponse:
    try:
        if spec.is_async:
            value = await spec.func(**kwargs)
        else:
            value = await run_in_threadpool(spec.func, **kwargs)
        payload = serialization.success(value)
    except Exception as exc:
        logger.exception("Endpoint %s raised", spec.path)
        return JSONResponse(serialization.error(type(exc).__name__, str(exc)), status_code=500)
    return JSONResponse(payload)


def _make_post_handler(spec: EndpointSpec) -> Callable[..., Any]:
    model = spec.request_model
    if model is None:

        async def handler() -> JSONResponse:
            return await _invoke(spec, {})

        return handler

    body_optional = all(not field.is_required() for field in model.model_fields.values())

    async def handler(body: Any = None) -> JSONResponse:
        if body is None:
            body = model()
        return await _invoke(spec, call_kwargs(body))

    # A single un-embedded body parameter makes FastAPI read the model's fields from the JSON root.
    handler.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [
            inspect.Parameter(
                "body",
                inspect.Parameter.KEYWORD_ONLY,
                annotation=Optional[model] if body_optional else model,
                default=Body(None) if body_optional else Body(...),
            )
        ]
    )
    return handler


def _make_get_handler(spec: EndpointSpec) -> Callable[..., Any]:
    hints = get_hints(spec.func)
    params = []
    for param in inspect.signature(spec.func).parameters.values():
        annotation = hints.get(param.name, str)
        if annotation is Any:
            annotation = str
        default = Query(...) if param.default is inspect.Parameter.empty else Query(param.default)
        params.append(inspect.Parameter(param.name, inspect.Parameter.KEYWORD_ONLY, annotation=annotation, default=default))

    async def handler(**kwargs: Any) -> JSONResponse:
        return await _invoke(spec, kwargs)

    handler.__signature__ = inspect.Signature(params)  # type: ignore[attr-defined]
    return handler


# -- Helpers ----------------------------------------------------------------


def _response_model(spec: EndpointSpec) -> type[BaseModel] | None:
    annotation = spec.return_annotation
    if annotation is inspect.Signature.empty or annotation is None or annotation is type(None):
        annotation = Any
    name = "".join(part.capitalize() for part in spec.name.split("_")) + "Response"
    try:
        return create_model(name, result=(annotation, ...))
    except Exception:
        return create_model(name, result=(Any, ...))


def _field_name(loc: tuple[Any, ...] | list[Any]) -> str:
    parts = [str(p) for p in loc]
    if len(parts) > 1 and parts[0] in ("body", "query"):
        parts = parts[1:]
    return ".".join(parts) or "body"


def _snake(text: str) -> str:
    return "_".join(text.lower().split())


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


__all__ = ["LocalAPI", "DEFAULT_HOST", "DEFAULT_PORT"]
