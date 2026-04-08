"""Tests for the plugin architecture."""
from __future__ import annotations

from pathlib import Path
import textwrap

import pytest

from ait.models import CapturedExchange, Finding, FindingCategory, Severity, TargetConfig
from ait.plugins.base import BaseDetectorPlugin
from ait.plugins.registry import PluginRegistry


@pytest.fixture
def sample_target():
    return TargetConfig.model_validate(
        {
            "name": "demo",
            "base_url": "http://127.0.0.1:8001/",
            "integration_sync_url": "http://127.0.0.1:8002/sync",
            "audit_base_url": "http://127.0.0.1:8001/",
        }
    )


@pytest.fixture
def sample_exchanges():
    return [
        CapturedExchange(
            run_id="r1",
            phase="baseline",
            method="GET",
            path="/api/v1/customers",
            status_code=200,
        )
    ]


# ── BaseDetectorPlugin ─────────────────────────────────────────────────────────

def test_abstract_plugin_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseDetectorPlugin()  # type: ignore[abstract]


def test_concrete_plugin_run_returns_plugin_result(sample_target, sample_exchanges):
    class NoOpPlugin(BaseDetectorPlugin):
        name = "no_op"
        version = "1.0.0"
        description = "Returns no findings."

        def detect(self, target, exchanges):
            return []

    plugin = NoOpPlugin()
    result = plugin.run(sample_target, sample_exchanges)
    assert result.plugin_name == "no_op"
    assert result.findings == []
    assert result.metadata["version"] == "1.0.0"


def test_plugin_detect_findings_propagated(sample_target, sample_exchanges):
    class AlertingPlugin(BaseDetectorPlugin):
        name = "always_alert"
        version = "0.1.0"
        description = "Always returns one finding."

        def detect(self, target, exchanges):
            return [
                Finding(
                    severity=Severity.LOW,
                    category=FindingCategory.POLICY_VIOLATION,
                    endpoint="/test",
                    title="Test finding",
                    evidence="test",
                    expected_behavior="nothing",
                    observed_behavior="something",
                    remediation_note="none",
                )
            ]

    plugin = AlertingPlugin()
    result = plugin.run(sample_target, sample_exchanges)
    assert len(result.findings) == 1
    assert result.findings[0].title == "Test finding"


# ── PluginRegistry ─────────────────────────────────────────────────────────────

def test_registry_register_and_list():
    class MyPlugin(BaseDetectorPlugin):
        name = "my_plugin"

        def detect(self, target, exchanges):
            return []

    registry = PluginRegistry()
    registry.register(MyPlugin)
    assert "my_plugin" in registry.list_plugins()


def test_registry_get_plugin():
    class AnotherPlugin(BaseDetectorPlugin):
        name = "another"

        def detect(self, target, exchanges):
            return []

    registry = PluginRegistry()
    registry.register(AnotherPlugin)
    plugin = registry.get_plugin("another")
    assert plugin.name == "another"


def test_registry_get_unknown_raises():
    registry = PluginRegistry()
    with pytest.raises(KeyError):
        registry.get_plugin("ghost")


def test_registry_unregister():
    class TempPlugin(BaseDetectorPlugin):
        name = "temp"

        def detect(self, target, exchanges):
            return []

    registry = PluginRegistry()
    registry.register(TempPlugin)
    assert "temp" in registry.list_plugins()
    registry.unregister("temp")
    assert "temp" not in registry.list_plugins()


def test_registry_run_all(sample_target, sample_exchanges):
    class PluginA(BaseDetectorPlugin):
        name = "plugin_a"

        def detect(self, target, exchanges):
            return []

    class PluginB(BaseDetectorPlugin):
        name = "plugin_b"

        def detect(self, target, exchanges):
            return []

    registry = PluginRegistry()
    registry.register(PluginA)
    registry.register(PluginB)
    results = registry.run_all(sample_target, sample_exchanges)
    assert len(results) == 2
    names = {r.plugin_name for r in results}
    assert names == {"plugin_a", "plugin_b"}


def test_registry_load_from_directory(tmp_path, sample_target, sample_exchanges):
    plugin_code = textwrap.dedent(
        """
        from ait.models import CapturedExchange, TargetConfig
        from ait.plugins.base import BaseDetectorPlugin


        class FilePlugin(BaseDetectorPlugin):
            name = "file_plugin"
            version = "1.0.0"

            def detect(self, target, exchanges):
                return []
        """
    )
    plugin_file = tmp_path / "file_plugin.py"
    plugin_file.write_text(plugin_code)

    registry = PluginRegistry()
    count = registry.load_from_directory(tmp_path)
    assert count == 1
    assert "file_plugin" in registry.list_plugins()


def test_registry_load_from_nonexistent_directory_raises(tmp_path):
    registry = PluginRegistry()
    with pytest.raises(NotADirectoryError):
        registry.load_from_directory(tmp_path / "nonexistent")
