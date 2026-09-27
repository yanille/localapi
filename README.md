# localapi

**Turn any Python function into a local HTTP API with zero boilerplate.**

```python
from localapi import LocalAPI

app = LocalAPI()

@app.post
def add(a: int, b: int) -> int:
    return a + b

app.run()
```

```bash
curl -X POST localhost:8000/add \
  -H "Content-Type: application/json" \
  -d '{"a": 10, "b": 20}'
# → {"result": 30}
```

Interactive docs are at <http://127.0.0.1:8000/docs>.

## Install

```bash
pip install -e .            # from a checkout
pip install -e ".[test]"    # with test dependencies
```

## What you get from the signature

| Derived from | Becomes |
|---|---|
| Function name `add` | Route `/add` |
| `@app.get` | `GET`, arguments from the query string |
| `@app.post` / `@app.put` / `@app.patch` / `@app.delete` | That method, arguments from a JSON body |
| Parameters | Request fields; defaults make them optional |
| Type hints | Validation (unannotated parameters accept any JSON value) |
| Return hint | Response schema in OpenAPI |
| Docstring | Endpoint description in OpenAPI |

## Usage

```python
from localapi import LocalAPI

app = LocalAPI(title="My Tools")

@app.post                              # POST /greet
def greet(name: str, excited: bool = False) -> str:
    """Say hello."""
    return f"Hello {name}" + ("!" if excited else "")

@app.get                               # GET /status
def status() -> dict:
    return {"status": "ok"}

@app.post(path="/math/add", name="addition")
def add(a: int, b: int) -> int:
    return a + b

@app.delete(path="/files")             # DELETE /files (a path can be reused across methods)
def remove_file(name: str) -> bool:
    ...

app.run()                              # http://127.0.0.1:8000
```

Decorators return the original function, so it stays callable and testable as plain Python.
`async def` functions are awaited; regular functions run in a threadpool so slow ones don't block the server.

For one-file scripts there's a default instance, where bare `@api` means `@api.post`:

```python
from localapi import api

@api
def add(a: int, b: int):
    return a + b

api.run()
```

## Responses

Every response uses the same envelope:

```jsonc
// 200
{"result": 12}

// 422: invalid input
{"error": "validation_error", "detail": [{"field": "a", "message": "Input should be a valid integer"}]}

// 500: the function raised
{"error": "ValueError", "detail": "b must be positive"}
```

Return values can be primitives, `dict`/`list`, Pydantic models, dataclasses, `datetime`, `Path` (as a string), `bytes` (base64), enums, and anything FastAPI's `jsonable_encoder` understands.

## Testing and other ASGI servers

`app.asgi` is the underlying FastAPI app:

```python
from fastapi.testclient import TestClient

client = TestClient(app.asgi)
assert client.post("/add", json={"a": 1, "b": 2}).json() == {"result": 3}
```

## Security

`app.run()` binds to `127.0.0.1`. Passing another `host=` (for example `0.0.0.0`) exposes your functions to the network and prints a warning. There's no authentication yet, so only do that on a trusted network.
