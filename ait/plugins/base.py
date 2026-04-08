from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ait.models import CapturedExchange, Finding, PluginResult, TargetConfig


class BaseDetectorPlugin(ABC):
    """Base class for all custom AIT finding detector plugins.

    Subclass this to add custom detection logic. Register your plugin with
    :class:`ait.plugins.registry.PluginRegistry` to have it run automatically
    during assessments.

    Example::

        class MyCustomDetector(BaseDetectorPlugin):
            name = "my_custom_detector"
            version = "1.0.0"
            description = "Detects my custom security issue."

            def detect(self, target, exchanges):
                findings = []
                # ... your logic here ...
                return findings
    """

    name: str = "unnamed_plugin"
    version: str = "0.0.0"
    description: str = ""

    @abstractmethod
    def detect(
        self,
        target: TargetConfig,
        exchanges: list[CapturedExchange],
    ) -> list[Finding]:
        """Run detection logic and return a list of findings.

        Args:
            target: The target configuration for the current run.
            exchanges: All captured HTTP exchanges for the run.

        Returns:
            A (possibly empty) list of :class:`~ait.models.Finding` objects.
        """

    def run(
        self,
        target: TargetConfig,
        exchanges: list[CapturedExchange],
    ) -> PluginResult:
        """Execute the plugin and wrap findings in a :class:`~ait.models.PluginResult`."""
        findings = self.detect(target, exchanges)
        return PluginResult(
            plugin_name=self.name,
            findings=findings,
            metadata={"version": self.version, "description": self.description},
        )
