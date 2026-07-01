#!/usr/bin/env python
"""Back-compat shim for the census downloader (use ``download-census``).

Thin wrapper around :func:`popgrids.cli.main`.
"""

from __future__ import annotations

from popgrids.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
