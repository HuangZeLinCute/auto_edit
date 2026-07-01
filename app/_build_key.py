"""Build-time API key injection.

This file is used ONLY during PyInstaller packaging.
The actual key is read from environment variable BUILD_API_KEY
and injected into the exe at build time.

For local development, use .env file.
"""

import os

# During build, set BUILD_API_KEY=sk-xxx before running pyinstaller
# The runtime_hook will inject this into the environment
BUILD_API_KEY = os.environ.get("BUILD_API_KEY", "")
