from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Type

from ait.models import CapturedExchange, PluginResult, TargetConfig
from ait.plugins.base import BaseDetectorPlugin


class PluginRegistry:
    """Registry and loader for :class:`~ait.plugins.base.BaseDetectorPlugin` implementations.

    Usage::

        registry = PluginRegistry()
        registry.register(MyCustomDetector)

        # Or load from a directory
        registry.load_from_directory(Path("my_plugins/"))

        results = registry.run_all(target, exchanges)
    """

    def __init__(self) -> None:
        self._plugins: dict[str, BaseDetectorPlugin] = {}

    def register(self, plugin_class: Type[BaseDetectorPlugin]) -> None:
        """Register a plugin class (instantiates it immediately)."""
        instance = plugin_class()
        self._plugins[instance.name] = instance

    def unregister(self, name: str) -> None:
        """Remove a plugin by name."""
        self._plugins.pop(name, None)

    def list_plugins(self) -> list[str]:
        """Return a sorted list of registered plugin names."""
        return sorted(self._plugins.keys())

    def get_plugin(self, name: str) -> BaseDetectorPlugin:
        """Retrieve a registered plugin instance by name."""
        try:
            return self._plugins[name]
        except KeyError as exc:
            raise KeyError(f"Plugin '{name}' is not registered.") from exc

    def load_from_directory(self, directory: Path) -> int:
        """Scan a directory for Python files and auto-register any
        :class:`~ait.plugins.base.BaseDetectorPlugin` subclasses found.

        Returns the number of plugins newly registered.
        """
        if not directory.is_dir():
            raise NotADirectoryError(f"{directory} is not a directory")
        count = 0
        for py_file in sorted(directory.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            module_name = f"_ait_plugin_{py_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)  # type: ignore[attr-defined]
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, BaseDetectorPlugin)
                    and obj is not BaseDetectorPlugin
                    and obj.name != "unnamed_plugin"
                ):
                    self.register(obj)
                    count += 1
        return count

    def run_all(
        self,
        target: TargetConfig,
        exchanges: list[CapturedExchange],
    ) -> list[PluginResult]:
        """Run all registered plugins and return their results."""
        results = []
        for plugin in self._plugins.values():
            results.append(plugin.run(target, exchanges))
        return results


# Module-level default registry instance
default_registry = PluginRegistry()
