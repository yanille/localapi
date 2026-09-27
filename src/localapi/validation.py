"""Turn a function signature into a Pydantic request model."""

from __future__ import annotations

import inspect
import typing
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, create_model


def get_hints(func: Callable[..., Any]) -> dict[str, Any]:
    """Resolved type hints, falling back to raw annotations if they can't be resolved."""
    try:
        return typing.get_type_hints(func, include_extras=True)
    except Exception:
        return dict(getattr(func, "__annotations__", {}))


def _model_name(func: Callable[..., Any]) -> str:
    return "".join(part.capitalize() for part in func.__name__.split("_")) + "Request"


def build_request_model(func: Callable[..., Any]) -> type[BaseModel] | None:
    """Build a model with one field per parameter, or ``None`` if there are no parameters.

    Unannotated parameters accept any JSON value (D-08); parameters with defaults are optional.
    ``*args`` is rejected; ``**kwargs`` lets the model accept extra fields, which are passed through.
    """
    hints = get_hints(func)
    fields: dict[str, Any] = {}
    allow_extra = False

    for param in inspect.signature(func).parameters.values():
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            raise TypeError(f"{func.__qualname__}: *{param.name} can't be exposed as an endpoint parameter")
        if param.kind is inspect.Parameter.POSITIONAL_ONLY:
            raise TypeError(f"{func.__qualname__}: positional-only parameter {param.name!r} can't be passed by name")
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            allow_extra = True
            continue

        annotation = hints.get(param.name, Any)
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[param.name] = (annotation, default)

    if not fields and not allow_extra:
        return None

    config = ConfigDict(extra="allow" if allow_extra else "forbid", arbitrary_types_allowed=True)
    return create_model(_model_name(func), __config__=config, **fields)


def call_kwargs(model: BaseModel) -> dict[str, Any]:
    """Keyword arguments for the user function, keeping validated (not dumped) values."""
    kwargs = {name: getattr(model, name) for name in type(model).model_fields}
    if model.model_extra:
        kwargs.update(model.model_extra)
    return kwargs
