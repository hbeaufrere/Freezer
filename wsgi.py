"""PythonAnywhere WSGI entry point.

To deploy on PythonAnywhere:
1. Replace USERNAME below with your PythonAnywhere username
2. In the Web tab, point the WSGI configuration file to this content
   (or paste this into the auto-generated WSGI file)
"""

import sys
import os

# Update this path to match your PythonAnywhere home directory
path = '/home/USERNAME/Freezer'

if path not in sys.path:
    sys.path.insert(0, path)

os.chdir(path)

from app import create_app

application = create_app()
