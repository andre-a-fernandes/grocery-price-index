import os
import urllib.request
import sys

port = os.environ.get("PORT", "7860")
try:
    urllib.request.urlopen(f"http://localhost:{port}/")
except Exception:
    sys.exit(1)