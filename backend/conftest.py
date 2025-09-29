import os
import sys
from pathlib import Path
import pytest

# Добавяме helpchain-backend (родител на папката src) в началото на sys.path,
# за да може `import src` да работи
_root = os.path.dirname(__file__)
_src_parent = os.path.join(_root, "helpchain-backend")
if os.path.isdir(_src_parent):
    sys.path.insert(0, _src_parent)

# Добавя текущата папка (backend) в sys.path така че 'appy' да се импортира директно
HERE = Path(__file__).parent.resolve()
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


@pytest.fixture
def session_id():
    return "test-session"


@pytest.fixture
def message():
    return "Hello, test message"
