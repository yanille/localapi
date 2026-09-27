from typing import Any

import pytest
from pydantic import ValidationError

from localapi.validation import build_request_model, call_kwargs


def test_typed_params_become_required_fields():
    def add(a: int, b: int) -> int: ...

    model = build_request_model(add)
    assert model.__name__ == "AddRequest"
    assert model(a=1, b="2").b == 2
    with pytest.raises(ValidationError):
        model(a=1)
    with pytest.raises(ValidationError):
        model(a="x", b=1)


def test_defaults_become_optional():
    def greet(name: str, excited: bool = False): ...

    model = build_request_model(greet)
    assert model(name="Ada").excited is False
    assert not model.model_fields["excited"].is_required()


def test_unannotated_params_are_any():
    def echo(value): ...

    model = build_request_model(echo)
    assert model.model_fields["value"].annotation is Any
    assert model(value={"nested": [1, 2]}).value == {"nested": [1, 2]}


def test_no_params_means_no_model():
    def status(): ...

    assert build_request_model(status) is None


def test_unknown_fields_rejected():
    def add(a: int, b: int): ...

    with pytest.raises(ValidationError):
        build_request_model(add)(a=1, b=2, c=3)


def test_var_positional_rejected():
    def f(*args): ...

    with pytest.raises(TypeError, match=r"\*args"):
        build_request_model(f)


def test_positional_only_rejected():
    def f(a, /): ...

    with pytest.raises(TypeError, match="positional-only"):
        build_request_model(f)


def test_kwargs_allow_extra_fields():
    def f(a: int, **options): ...

    model = build_request_model(f)
    assert call_kwargs(model(a=1, colour="red")) == {"a": 1, "colour": "red"}


def test_call_kwargs_keeps_validated_objects():
    from pydantic import BaseModel

    class Point(BaseModel):
        x: int

    def f(p: Point): ...

    kwargs = call_kwargs(build_request_model(f)(p={"x": 1}))
    assert isinstance(kwargs["p"], Point)
