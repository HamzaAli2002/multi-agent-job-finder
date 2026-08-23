"""
Tests never need real API keys — none of them call Gemini or Tavily.
But importing src.pipeline (and src.config) requires GOOGLE_API_KEY /
TAVILY_API_KEY to be present because Settings() validates on import.
Set harmless dummy values before any test module imports src.*.
"""

import os

os.environ.setdefault("GOOGLE_API_KEY", "test-dummy-key")
os.environ.setdefault("TAVILY_API_KEY", "test-dummy-key")
