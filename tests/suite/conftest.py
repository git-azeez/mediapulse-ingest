from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from suite.tools.reporting.scoring import load_obligations
from suite.tools.trial import TrialSession


SPEC = load_obligations(Path(__file__).with_name("obligations.yaml"))
ORDER = {item["id"]: index for index, item in enumerate(SPEC["obligations"])}


@pytest.fixture(scope="session")
def trial() -> Any:
    session = TrialSession()
    try:
        yield session
    finally:
        session.finish()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    items.sort(key=lambda item: ORDER.get(getattr(item.obj, "obligation_id", ""), len(ORDER)))
