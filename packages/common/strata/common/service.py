"""Starting an app from the environment, and refusing to start degraded.

A service that comes up missing something essential looks like a working
process from the outside. So the consumer's ``build()`` raises, and this
turns the raise into a message on stderr and exit status 2 — a failed
start, which a supervisor reports rather than restarting forever.
"""

import os
import sys
from collections.abc import Callable
from typing import Any

#: Where a service listens, for every service. 0.0.0.0 so another machine
#: can reach it; the port is each consumer's own default.
HOST_ENV = "STRATA_SERVE_HOST"
PORT_ENV = "STRATA_SERVE_PORT"


def serve(build: Callable[[], Any], *, prog: str, port: int, error: type[Exception]) -> None:
    """Build the app, then serve it until stopped.

    ``error`` is what ``build`` raises when a setting it cannot start
    without is absent; anything else is a bug and propagates as one.
    """
    import uvicorn  # pyright: ignore[reportMissingImports]  (the service extra)

    try:
        app = build()
    except error as e:
        print(f"{prog}: {e}", file=sys.stderr)
        raise SystemExit(2) from None

    uvicorn.run(
        app,
        host=os.environ.get(HOST_ENV, "0.0.0.0"),  # noqa: S104
        port=int(os.environ.get(PORT_ENV, str(port))),
    )


__all__ = ["HOST_ENV", "PORT_ENV", "serve"]
