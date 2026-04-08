"""Tests for the SQLAlchemy-backed storage layer."""
from __future__ import annotations

import pytest

from ait.models import RunRecord, TargetConfig, TestRunConfig, RunReport
from ait.storage import SQLAlchemyStore


@pytest.fixture
def store(tmp_path):
    """Create a fresh SQLite-backed store in a temp directory."""
    db_url = f"sqlite:///{tmp_path}/test.db"
    return SQLAlchemyStore(database_url=db_url)


@pytest.fixture
def sample_target():
    return TargetConfig.model_validate(
        {
            "name": "test-target",
            "base_url": "http://127.0.0.1:8001/",
            "integration_sync_url": "http://127.0.0.1:8002/sync",
            "audit_base_url": "http://127.0.0.1:8001/",
            "expected_endpoints": ["/api/v1/items"],
            "sensitive_markers": ["secret_field"],
        }
    )


@pytest.fixture
def sample_run(sample_target):
    return RunRecord(
        run_id="test-run-001",
        status="completed",
        target=sample_target,
        config=TestRunConfig(),
        report=RunReport(
            run_id="test-run-001",
            target_name="test-target",
            status="completed",
            reached_endpoints=["/api/v1/items"],
            hidden_endpoints=[],
            sensitive_fields_accessed=[],
            divergence_summary=[],
            risk_score=0,
            findings=[],
        ),
    )


def test_save_and_get_target(store, sample_target):
    store.save_target(sample_target)
    retrieved = store.get_target("test-target")
    assert retrieved.name == "test-target"
    assert retrieved.expected_endpoints == ["/api/v1/items"]


def test_get_unknown_target_raises(store):
    with pytest.raises(KeyError):
        store.get_target("does-not-exist")


def test_list_targets(store, sample_target):
    store.save_target(sample_target)
    targets = list(store.list_targets())
    assert len(targets) == 1
    assert targets[0].name == "test-target"


def test_save_and_get_run(store, sample_run):
    store.save_run(sample_run)
    retrieved = store.get_run("test-run-001")
    assert retrieved.run_id == "test-run-001"
    assert retrieved.status == "completed"


def test_get_unknown_run_raises(store):
    with pytest.raises(KeyError):
        store.get_run("no-such-run")


def test_overwrite_run(store, sample_run):
    store.save_run(sample_run)
    updated = sample_run.model_copy(update={"status": "failed"})
    store.save_run(updated)
    retrieved = store.get_run("test-run-001")
    assert retrieved.status == "failed"


def test_list_runs(store, sample_run, sample_target):
    store.save_run(sample_run)
    runs = store.list_runs()
    assert len(runs) == 1
    assert runs[0].run_id == "test-run-001"


def test_list_runs_filter_by_target(store, sample_run, sample_target):
    store.save_run(sample_run)
    runs_match = store.list_runs(target_name="test-target")
    runs_no_match = store.list_runs(target_name="other-target")
    assert len(runs_match) == 1
    assert len(runs_no_match) == 0


def test_persistence_across_instances(tmp_path, sample_target, sample_run):
    db_url = f"sqlite:///{tmp_path}/persist.db"
    store_a = SQLAlchemyStore(database_url=db_url)
    store_a.save_target(sample_target)
    store_a.save_run(sample_run)

    # Fresh instance, same DB
    store_b = SQLAlchemyStore(database_url=db_url)
    assert store_b.get_target("test-target").name == "test-target"
    assert store_b.get_run("test-run-001").run_id == "test-run-001"
