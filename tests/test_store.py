from ait.models import RunRecord, TargetConfig, TestRunConfig
from ait.store import InMemoryStore


def test_store_clear_removes_targets_and_runs():
    store = InMemoryStore()
    target = TargetConfig.model_validate(
        {
            "name": "demo",
            "base_url": "http://127.0.0.1:8001/",
            "integration_sync_url": "http://127.0.0.1:8002/sync",
            "audit_base_url": "http://127.0.0.1:8001/",
        }
    )
    store.save_target(target)
    store.save_run(
        RunRecord(
            run_id="run-1",
            status="completed",
            target=target,
            config=TestRunConfig(),
        )
    )
    assert list(store.list_targets())
    assert store.get_run("run-1").run_id == "run-1"

    store.clear()

    assert list(store.list_targets()) == []
    assert store.runs == {}
