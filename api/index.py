"""Vercel Python entry point.

Vercel discovers `app` (a WSGI callable) and serves it from this file.
"""

import os
import sys

# Make the project root importable from /api/index.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: F401,E402
