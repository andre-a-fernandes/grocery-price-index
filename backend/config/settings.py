import os

# google-genai automatically reads GEMINI_API_KEY or the Vertex AI env vars.
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")