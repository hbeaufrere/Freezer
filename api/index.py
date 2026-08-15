"""Vercel entrypoint.

Vercel's Python runtime discovers Serverless Functions inside `api/`, so the
Flask app is re-exported here and `vercel.json` rewrites every path onto it.
Going through `api/` rather than relying on framework auto-detection means the
deployment works whatever the project's framework preset happens to be.

The app itself still lives in `app.py` at the repository root, next to
`templates/`, and `python app.py` runs it locally exactly as before.
"""

import os
import sys

# The application modules live one level up, alongside templates/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402  (path setup has to happen first)

# Vercel looks for a module-level WSGI callable named `app`.
__all__ = ['app']
