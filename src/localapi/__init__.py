"""localapi: turn any Python function into a local HTTP API with zero boilerplate."""

from localapi.routing import EndpointSpec
from localapi.server import LocalAPI

__version__ = "0.2.0"

# Module-level default instance for one-file scripts (see D-05).
api = LocalAPI()

__all__ = ["LocalAPI", "EndpointSpec", "api", "__version__"]
