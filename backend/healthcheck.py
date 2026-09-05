import os
import sys
import urllib.request

port = os.environ.get("PORT", "7860")
try:
    urllib.request.urlopen(f"http://localhost:{port}/")
except Exception:
    sys.exit(1)
