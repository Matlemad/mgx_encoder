"""Registry for contextual palette modules."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .selection_analyzer import SelectionType


@runtime_checkable
class PaletteModule(Protocol):
    id: str
    title: str
    supported_types: list[SelectionType]

    def run(self, text: str, context: dict[str, Any]) -> dict[str, Any]: ...


_REGISTRY: list[PaletteModule] = []


def register(module: PaletteModule) -> None:
    _REGISTRY.append(module)


def get_modules_for(sel_type: SelectionType) -> list[PaletteModule]:
    return [m for m in _REGISTRY if sel_type in m.supported_types]


def get_all_modules() -> list[PaletteModule]:
    return list(_REGISTRY)
