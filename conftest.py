from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from test_fixtures import *  # noqa: F401,F403
from test_fixtures import _set_test_env  # noqa: F401


def pytest_configure(config):
    run_id = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    if getattr(config.option, "basetemp", None):
        basetemp = Path(str(config.option.basetemp))
    else:
        basetemp = Path(tempfile.gettempdir()) / f"helpchain-pytest-run-{run_id}"
        config.option.basetemp = str(basetemp)
