"""Try it: python examples/demo.py, then open http://127.0.0.1:8000/docs"""

from localapi import LocalAPI

app = LocalAPI(title="Demo Tools")


@app.post
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@app.post
def greet(name: str, excited: bool = False) -> str:
    """Say hello to someone."""
    return f"Hello {name}" + ("!" if excited else "")


@app.post
def divide(a: float, b: float) -> float:
    """Divide a by b (try b = 0 to see an error)."""
    return a / b


@app.get
def status() -> dict:
    """Check the server is up."""
    return {"status": "ok", "version": "1.0"}


if __name__ == "__main__":
    app.run()
