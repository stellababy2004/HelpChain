# Optional: skip if Ollama env/model not available
import os

import pytest

if not os.getenv("OLLAMA_BASE_URL"):
    pytest.skip("Ollama tests are optional", allow_module_level=True)

print("ollama test stub")
