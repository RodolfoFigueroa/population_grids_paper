#!/usr/bin/env python
"""Discoverable entrypoint for the European census downloader.

Thin shim around :func:`popgrids.europe.cli.main`; the primary UX is the
``download-europe`` console script created by ``uv sync``.
"""

from __future__ import annotations

from popgrids.europe.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
