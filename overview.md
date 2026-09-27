# localapi — Project Overview

> **Turn any Python function into a local HTTP API with zero boilerplate.**

| | |
|---|---|
| **Status** | v0.1.0 on PyPI; v0.2.0 (breaking API cleanup) ready to release |
| **Language** | Python 3.10+ |
| **Built on** | FastAPI / Starlette + Uvicorn |
| **Target milestone** | v0.2: `@app.<method>` decorators, title-only `LocalAPI(...)` |
| **Last updated** | September 2026 |

---

## Table of Contents

1. [What It Is](#1-what-it-is)
2. [Why It Exists](#2-why-it-exists)
3. [Current Focus](#3-current-focus)
4. [Status: Done / In Progress / To Do](#4-status-done--in-progress--to-do)
5. [Public API Design](#5-public-api-design)
6. [Architecture](#6-architecture)
7. [Request Lifecycle](#7-request-lifecycle)
8. [Design Decisions](#8-design-decisions)
9. [Open Questions](#9-open-questions)
10. [Roadmap](#10-roadmap)
11. [Non-Goals](#11-non-goals)
12. [Use Cases](#12-use-cases)
13. [Glossary](#13-glossary)

---

## 1. What It Is

`localapi` is a small Python library that inspects ordinary Python functions and exposes them as HTTP endpoints on `localhost`. The developer writes the function; the library works out the route, method, parameters, types, validation, serialization, and documentation.

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

From the function signature alone, `localapi` derives:

| Derived from | Becomes |
|---|---|
| Function name `add` | Route `/add` |
| Decorator `@app.post` | HTTP method `POST` |
| Parameters `a`, `b` | JSON body fields |
| Type hints `int` | Request validation |
| Return hint `-> int` | Response schema |
| Docstring | Endpoint description in OpenAPI |

The long-term "killer feature" is a CLI that needs no code changes at all:

```bash
localapi myscript.py
```

---

## 2. Why It Exists

**The problem.** Wrapping a script in an HTTP API today means learning a web framework, writing handler functions, parsing request bodies, and mapping errors, even when all you want is for another program to call `take_screenshot()`.

```python
# What you have to write today
@app.post("/add")
async def add_endpoint(request):
    data = await request.json()
    ...
```

**The value proposition.** `localapi` is *not* another web framework. It is a thin function-to-API layer on top of a proven one. Its value is entirely in removing boilerplate for the local, personal, and automation use case.

**Target users**

- Developers with personal automation scripts they want to trigger from other tools (Raycast, Alfred, Stream Deck, shell scripts, browser extensions, home automation).
- People prototyping integrations who need a callable endpoint in seconds.
- Anyone who wants a Python tool reachable from another language without writing bindings.

---

## 3. Current Focus

v0.1.0 is published on PyPI. v0.2.0 is a breaking cleanup of the public API and is ready to release. Next:

1. Publish v0.2.0 to PyPI and tag it in git.
2. Start v0.3 (async docs, auth, CORS, better error messages).

---

## 4. Status: Done / In Progress / To Do

### ✅ Done

- [x] Core concept and value proposition defined
- [x] Target API sketched (`LocalAPI`, `@app.<method>` decorators, `app.run()`)
- [x] Module layout proposed
- [x] Decision to build on FastAPI/Starlette rather than a custom HTTP layer
- [x] Long-term feature list and CLI vision captured
- [x] Response envelope (D-04) and default-app shorthand (D-05) implemented as proposed
- [x] Package scaffolding (`pyproject.toml`, `src/` layout, CI workflow)
- [x] v0.1 MVP: everything under "Done: v0.1" below
- [x] Repo on GitHub, CI passing on Python 3.10–3.13
- [x] v0.1.0 published to PyPI

### 🚧 In Progress: v0.2.0 (breaking)

- [x] Decorators renamed to one per HTTP method (`@app.get/post/put/patch/delete`); `@app.endpoint` removed
- [x] `LocalAPI(...)` takes only `title` (`version` and `description` removed)
- [ ] Publish to PyPI and tag `v0.2.0`

### ✅ Done: v0.1 (MVP)

- [x] `LocalAPI` class wrapping a FastAPI app
- [x] `@app.post` / `@app.put` / `@app.patch` / `@app.delete` decorators → `<METHOD> /<function_name>` with a JSON body
- [x] `@app.get` decorator → `GET /<function_name>`
- [x] Signature inspection (`inspect.signature` + `typing.get_type_hints`)
- [x] Dynamic Pydantic request model generation
- [x] Automatic validation with clean `422` errors
- [x] Automatic JSON serialization of return values
- [x] Default values → optional fields
- [x] Exceptions raised in user code → `500` with a readable JSON error
- [x] `app.run(host="127.0.0.1", port=8000)`
- [x] OpenAPI docs at `/docs` (comes free from FastAPI)
- [x] Unit tests for inspection, routing, validation, serialization
- [x] README with the 5-line quickstart

### 📋 To Do: later

See the [Roadmap](#10-roadmap): async, CLI, auth, CORS, hot reload, background tasks, WebSockets.

---

## 5. Public API Design

### 5.1 Explicit app (primary API)

```python
from localapi import LocalAPI

app = LocalAPI(title="My Tools")

@app.post                     # POST /add
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

@app.post                     # POST /greet
def greet(name: str, excited: bool = False) -> str:
    return f"Hello {name}" + ("!" if excited else "")

@app.get                      # GET /status
def status() -> dict:
    return {"status": "ok", "version": "1.0"}

app.run()                     # http://127.0.0.1:8000
```

### 5.2 Shorthand default app (convenience API)

For one-file scripts, a module-level default instance:

```python
from localapi import api

@api
def add(a: int, b: int):
    return a + b

api.run()
```

`api` is a pre-built `LocalAPI` instance whose `__call__` is an alias for `.post`. See [D-05](#d-05-default-app-shorthand).

### 5.3 Decorator options (planned)

Decorators work bare *and* with arguments:

```python
@app.post(path="/math/add", name="Addition")
def add(a: int, b: int) -> int: ...
```

### 5.4 Response format

```json
// Request
POST /add
{"a": 5, "b": 7}

// Response 200
{"result": 12}

// Response 422 (validation)
{"error": "validation_error", "detail": [{"field": "a", "message": "Input should be a valid integer"}]}

// Response 500 (function raised)
{"error": "ValueError", "detail": "b must be positive"}
```

---

## 6. Architecture

### 6.1 Layers

```
┌─────────────────────────────────────────────┐
│  User code:  plain Python functions         │
├─────────────────────────────────────────────┤
│  localapi                                   │
│   ├─ routing.py        decorators, registry │
│   ├─ validation.py     signature → model    │
│   ├─ serialization.py  return → JSON        │
│   └─ server.py         LocalAPI, run()      │
├─────────────────────────────────────────────┤
│  FastAPI / Starlette   routing, OpenAPI     │
├─────────────────────────────────────────────┤
│  Uvicorn               ASGI server          │
└─────────────────────────────────────────────┘
```

### 6.2 Package layout

```
localapi/
├── pyproject.toml
├── README.md
├── src/
│   └── localapi/
│       ├── __init__.py        # exports LocalAPI, api (default instance)
│       ├── server.py          # LocalAPI class, run(), FastAPI app construction
│       ├── routing.py         # EndpointSpec + registry (decorators live on LocalAPI)
│       ├── validation.py      # inspect signature → Pydantic model
│       ├── serialization.py   # convert return values → JSON-safe payloads
│       └── cli.py             # (v0.4) `localapi myscript.py`
└── tests/
    ├── test_routing.py
    ├── test_validation.py
    ├── test_serialization.py
    └── test_integration.py    # uses FastAPI TestClient
```

### 6.3 Module responsibilities

**`routing.py`**: Decorators capture functions and store an `EndpointSpec` (function, path, method, name, docstring) in the app's registry. Decorators return the **original function unchanged**, so it stays directly callable and testable in Python.

**`validation.py`**: Reads `inspect.signature(fn)` and `typing.get_type_hints(fn)`, then builds a request model with `pydantic.create_model(...)`. Parameters without hints default to `Any`; parameters with defaults become optional fields.

**`serialization.py`**: Wraps the return value in the response envelope. Handles primitives, `dict`/`list`, Pydantic models, dataclasses, `datetime`, `Path`, `bytes` (base64), and falls back to FastAPI's `jsonable_encoder`.

**`server.py`**: `LocalAPI` owns a FastAPI instance. Endpoints are registered lazily; on `run()` (or when the ASGI app is first accessed) each `EndpointSpec` is turned into a FastAPI route with a generated handler. `run()` starts Uvicorn bound to `127.0.0.1`.

### 6.4 Core data structure

```python
@dataclass
class EndpointSpec:
    func: Callable
    path: str              # "/add"
    method: str            # "POST" | "GET"
    name: str              # "add"
    description: str | None
    request_model: type[BaseModel] | None
    is_async: bool
```

---

## 7. Request Lifecycle

```
Client                    localapi / FastAPI                  User function
  │  POST /add {"a":5,"b":7}  │                                     │
  │──────────────────────────▶│                                     │
  │                           │ 1. Route match (/add, POST)         │
  │                           │ 2. Parse JSON body                  │
  │                           │ 3. Validate against AddRequest      │
  │                           │    ✗ → 422 error envelope           │
  │                           │ 4. Call add(a=5, b=7) ─────────────▶│
  │                           │    (sync → threadpool, async → await)
  │                           │◀──────────────────────── returns 12 │
  │                           │ 5. Serialize → {"result": 12}       │
  │                           │    exception → 500 error envelope   │
  │◀──────────────────────────│                                     │
```

Sync functions run in Starlette's threadpool so a slow function (e.g. taking a screenshot) doesn't block the event loop.

---

## 8. Design Decisions

Lightweight decision records. Status: **Accepted**, **Proposed**, or **Open**.

### D-01: Build on FastAPI/Starlette, don't write an HTTP layer
**Status:** Accepted
**Context:** HTTP parsing, routing, OpenAPI generation, and ASGI serving are solved problems.
**Decision:** Use FastAPI (and therefore Starlette, Pydantic, Uvicorn).
**Consequences:** OpenAPI docs, validation, and async support come essentially free. Adds a dependency footprint, which is acceptable because the value of `localapi` is the zero-boilerplate layer, not the server.

### D-02: Function name is the route
**Status:** Accepted
**Decision:** `def add` → `/add`. Overridable via `@app.<method>(path=...)`.
**Consequences:** Two functions with the same name raise an error at registration rather than silently shadowing each other.

### D-03: One decorator per HTTP method
**Status:** Accepted (revised September 2026; originally `@app.endpoint` for POST plus `@app.get`)
**Context:** Functions take arbitrary typed arguments; JSON bodies express these far better than query strings. Naming decorators after HTTP methods matches FastAPI/Flask and makes the method obvious at the call site.
**Decision:** `@app.get`, `@app.post`, `@app.put`, `@app.patch`, `@app.delete`. `GET` takes parameters from the query string and is intended for read-only functions such as `status()`; every other method takes a JSON body. Routes are unique per (method, path), so one path can serve several methods.
**Consequences:** GET endpoints are limited to simple scalar parameters. Bare `@api` on the default app means `@api.post`.

### D-04: Response envelope
**Status:** Accepted (implemented in v0.1)
**Context:** The early sketches were inconsistent: one returned `{"result": 12}`, another returned a bare `30`.
**Decision (proposed):** Always wrap in `{"result": ...}`, and errors in `{"error": ..., "detail": ...}`.
**Rationale:** A bare string response (e.g. from `greet`) isn't a JSON object, and a consistent envelope lets clients tell success from failure with one check and leaves room for metadata later.
**Alternative:** Bare values by default with an `envelope=False` flag. Revisit if users find the wrapper annoying for simple cases.

### D-05: Default-app shorthand (`from localapi import api`)
**Status:** Accepted (implemented in v0.1)
**Decision:** Provide a module-level `LocalAPI` instance named `api`, callable as a decorator. The explicit `LocalAPI()` class remains the primary, documented-first API.
**Consequences:** Great for one-file scripts; global state means it's not recommended for libraries or tests.

### D-06: Bind to `127.0.0.1` by default
**Status:** Accepted
**Context:** Endpoints like `launch_app` or `screenshot` are powerful. Exposing them on the network by accident would be dangerous.
**Decision:** Default host is `127.0.0.1`, never `0.0.0.0`. Binding to all interfaces requires an explicit `host=` argument and prints a warning.

### D-07: Decorators return the original function
**Status:** Accepted
**Decision:** Every `@app.<method>` decorator registers the function and returns it untouched.
**Consequences:** Functions remain normal Python: callable, testable, importable, with no hidden wrapper behaviour.

### D-08: Missing type hints → `Any`
**Status:** Accepted (implemented in v0.1)
**Decision:** Unannotated parameters are accepted as any JSON value rather than rejected. Validation is only as strict as the annotations.
**Consequences:** Keeps the "zero boilerplate" promise; typed code gets full validation and better docs.

### D-09: Sync functions run in a threadpool
**Status:** Accepted
**Decision:** Follow Starlette's default: `def` runs in a worker thread, `async def` is awaited directly.

---

## 9. Open Questions

| # | Question | Notes |
|---|---|---|
| Q-1 | ~~Is the name `localapi` available on PyPI?~~ | **Resolved:** published as `localapi` (0.1.0). |
| Q-2 | Should zero-argument `@app.post` functions also answer `GET`? | Would make `curl localhost:8000/bluetooth_devices` work without `-X POST`. Convenient but blurs D-03. |
| Q-3 | ~~How should `*args` / `**kwargs` be handled?~~ | **Resolved in v0.1:** `*args` and positional-only params are rejected at registration; `**kwargs` on POST accepts extra JSON fields and passes them through; `**kwargs` on GET is rejected. |
| Q-4 | Should a single-parameter function accept a bare body? | e.g. `POST /greet` with body `"Ada"` instead of `{"name": "Ada"}`. |
| Q-5 | How should binary/file returns work? | `screenshot()` might return image bytes; consider returning `Path` → file response. |
| Q-6 | Auth model for v0.3? | Simple bearer token generated on startup and printed to the console is the leading idea. |
| Q-7 | CLI discovery: which functions get exposed? | Options: all public top-level functions, only decorated ones, or a `--only` flag. |
| Q-8 | Minimum Python version? | 3.10 enables `X | Y` unions in hints; 3.9 would widen reach. |

---

## 10. Roadmap

```
v0.1  MVP (released) ──────────────────────────────────
      ├── LocalAPI, @app.endpoint, @app.get, app.run()
      ├── automatic validation
      ├── automatic JSON serialization
      └── OpenAPI docs at /docs

v0.2  API cleanup (breaking) ──────────────────────────
      ├── @app.get/post/put/patch/delete replace @app.endpoint
      └── LocalAPI(title=...) only; version/description removed

v0.3  Everyday use ────────────────────────────────────
      ├── async functions (first-class, documented)
      ├── decorator options (path, name, tags)
      ├── authentication (token)
      ├── CORS configuration
      └── better error messages

v0.4  The killer feature ──────────────────────────────
      ├── CLI: `localapi myscript.py`
      └── hot reload (`localapi myscript.py --reload`)

v0.5+ Advanced ────────────────────────────────────────
      ├── background tasks (fire-and-forget + job status)
      ├── WebSockets / streaming (generators → streamed responses)
      └── file uploads & file responses
```

### Milestone definitions of done

**v0.1** is done when the quickstart in this document works exactly as written, `/docs` shows every registered endpoint with correct schemas, invalid input returns a `422` envelope, and the test suite passes on CI.

**v0.4** is done when `localapi myscript.py` exposes the functions in an unmodified script with no imports from `localapi` required.

---

## 11. Non-Goals

- **Not a general web framework.** No templates, sessions, ORMs, or middleware ecosystem. Use FastAPI directly for that.
- **Not for production internet-facing services.** Built for localhost and trusted networks.
- **No custom HTTP server.** Serving is delegated to Uvicorn.
- **No magic beyond the signature.** Behaviour should be predictable from reading the function.

---

## 12. Use Cases

```python
@app.post
def screenshot() -> str:
    """Take a screenshot and return the saved file path."""
    ...

@app.post
def launch_app(name: str):
    """Open an application by name."""
    ...

@app.post
def bluetooth_devices() -> list[dict]:
    """List nearby Bluetooth devices."""
    ...
```

Any program that can make an HTTP request (shell scripts, launchers, macro pads, browser extensions, other languages) can now call these tools without a web application being built around them.

---

## 13. Glossary

| Term | Meaning |
|---|---|
| **Endpoint** | A Python function registered with `localapi` and exposed at a URL. |
| **EndpointSpec** | Internal record describing one endpoint (function, path, method, model). |
| **Request model** | Pydantic model generated from a function's signature, used for validation. |
| **Envelope** | The `{"result": ...}` / `{"error": ...}` wrapper around every response. |
| **Default app** | The module-level `api` instance used by the shorthand API. |
