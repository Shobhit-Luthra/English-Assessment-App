import json
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent


@pytest.fixture
def bank_dict():
    return json.loads((BACKEND_DIR / "bank.json").read_text(encoding="utf-8"))
