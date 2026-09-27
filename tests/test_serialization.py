import dataclasses
import datetime as dt
import enum
from pathlib import Path

from pydantic import BaseModel

from localapi.serialization import error, success, to_jsonable


class Colour(enum.Enum):
    RED = "red"


class User(BaseModel):
    name: str
    joined: dt.date


@dataclasses.dataclass
class Point:
    x: int
    tags: tuple[str, ...]


def test_primitives_pass_through():
    for value in (None, True, 3, 1.5, "hi"):
        assert to_jsonable(value) == value


def test_containers_recurse():
    assert to_jsonable({"a": (1, 2), 3: [Path("/tmp")]}) == {"a": [1, 2], "3": ["/tmp"]}


def test_rich_types():
    assert to_jsonable(User(name="Ada", joined=dt.date(2026, 1, 2))) == {"name": "Ada", "joined": "2026-01-02"}
    assert to_jsonable(Point(1, ("a",))) == {"x": 1, "tags": ["a"]}
    assert to_jsonable(dt.datetime(2026, 1, 2, 3, 4, 5)) == "2026-01-02T03:04:05"
    assert to_jsonable(b"hi") == "aGk="
    assert to_jsonable(Colour.RED) == "red"


def test_envelopes():
    assert success(12) == {"result": 12}
    assert error("ValueError", "bad") == {"error": "ValueError", "detail": "bad"}
