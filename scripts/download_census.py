#!/usr/bin/env python
"""Discoverable entrypoint for the census downloader.

Thin shim around :func:`popgrids.cli.main`; the primary UX is the
``download-census`` console script created by ``uv sync``.
"""

from __future__ import annotations

from popgrids.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
