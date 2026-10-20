"""Application entry point.

The original prototype lived in this file.  It now simply re-exports the
hardened application from :mod:`ownerai.main` so that both

    uvicorn app:app --host 127.0.0.1 --port 8000

and

    uvicorn ownerai.main:app

work.  The legacy ``/api/legacy/embeddings`` endpoint is still available, but
it requires an authenticated account and is restricted to an allow-listed
directory (see :mod:`ownerai.routers.legacy`).
"""

from __future__ import annotations

import os

from ownerai.main import create_app

app = create_app()


def main() -> None:
    """Run the development server bound to the loopback interface."""
    import uvicorn

    settings_port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run("ownerai.main:app", host=host, port=settings_port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
