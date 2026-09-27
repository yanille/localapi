"""Decorators and the endpoint registry."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel

from localapi.validation import build_request_model, get_hints


@dataclass
class EndpointSpec:
    func: Callable[..., Any]
    path: str  # "/add"
    method: str  # "POST" | "GET"
    name: str  # "add"
    description: str | None
    request_model: type[BaseModel] | None
    is_async: bool
    return_annotation: Any = inspect.Signature.empty


def make_spec(
    func: Callable[..., Any],
    method: str,
    path: str | None = None,
    name: str | None = None,
) -> EndpointSpec:
    """Inspect ``func`` and describe it as an endpoint."""
    if not callable(func):
        raise TypeError(f"Expected a function, got {func!r}")

    path = path or f"/{func.__name__}"
    if not path.startswith("/"):
        path = "/" + path

    request_model = build_request_model(func)
    if method == "GET" and any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in inspect.signature(func).parameters.values()
    ):
        raise TypeError(f"{func.__qualname__}: **kwargs isn't supported on GET endpoints")

    return EndpointSpec(
        func=func,
        path=path,
        method=method,
        name=name or func.__name__,
        description=inspect.getdoc(func),
        request_model=request_model,
        is_async=inspect.iscoroutinefunction(func),
        return_annotation=get_hints(func).get("return", inspect.Signature.empty),
    )


class Registry:
    """Ordered collection of endpoints, keyed by path."""

    def __init__(self) -> None:
        self._specs: dict[str, EndpointSpec] = {}

    def add(self, spec: EndpointSpec) -> None:
        existing = self._specs.get(spec.path)
        if existing is not None:
            raise ValueError(
                f"Route {spec.path!r} is already registered by "
                f"{existing.func.__module__}.{existing.func.__qualname__}; "
                f"pass path=... to register {spec.func.__qualname__} elsewhere"
            )
        self._specs[spec.path] = spec

    def __iter__(self):
        return iter(self._specs.values())

    def __len__(self) -> int:
        return len(self._specs)

