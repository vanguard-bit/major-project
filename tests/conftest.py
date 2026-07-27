from __future__ import annotations

import copy

import pytest

import ait.mock_saas as mock_saas
from ait.store import store

_BASELINE_CUSTOMERS = copy.deepcopy(mock_saas.CUSTOMERS)


@pytest.fixture(autouse=True)
def reset_mutable_state():
    mock_saas.CUSTOMERS.clear()
    mock_saas.CUSTOMERS.update(copy.deepcopy(_BASELINE_CUSTOMERS))
    mock_saas.AUDIT_LOGS.clear()
    store.clear()
    yield
    mock_saas.CUSTOMERS.clear()
    mock_saas.CUSTOMERS.update(copy.deepcopy(_BASELINE_CUSTOMERS))
    mock_saas.AUDIT_LOGS.clear()
    store.clear()
