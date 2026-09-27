"""Convert return values into JSON-safe payloads and response envelopes (D-04)."""

from __future__ import annotations

import base64
import dataclasses
import datetime as dt
import decimal
import enum
import uuid
from pathlib import PurePath
from typing import Any

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(to_jsonable(k)): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, enum.Enum):
        return to_jsonable(value.value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, decimal.Decimal):
        return float(value)
    return jsonable_encoder(value)


def success(value: Any) -> dict[str, Any]:
    return {"result": to_jsonable(value)}


def error(kind: str, detail: Any) -> dict[str, Any]:
    return {"error": kind, "detail": detail}
