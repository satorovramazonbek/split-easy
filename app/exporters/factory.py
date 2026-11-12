"""Factory for export formats (Factory pattern, spec section 8, pattern 4).

Callers ask for a format by name (``ExporterFactory.create("csv")``) and never
name a concrete class. Adding a format = writing one class and registering it;
the service and the API do not change (Open/Closed, FR-25).
"""

from typing import ClassVar

from app.exporters.base import Exporter
from app.exporters.csv_exporter import CsvExporter
from app.exporters.json_exporter import JsonExporter


class UnknownExportFormatError(ValueError):
    """No exporter is registered under this name."""


class ExporterFactory:
    _registry: ClassVar[dict[str, type[Exporter]]] = {
        "csv": CsvExporter,
        "json": JsonExporter,
    }

    @classmethod
    def create(cls, name: str) -> Exporter:
        try:
            return cls._registry[name.lower()]()
        except KeyError:
            raise UnknownExportFormatError(
                f"Noma'lum eksport formati: {name!r}. Mavjud: {', '.join(cls._registry)}"
            ) from None

    @classmethod
    def register(cls, name: str, exporter_class: type[Exporter]) -> None:
        cls._registry[name.lower()] = exporter_class

    @classmethod
    def available_formats(cls) -> list[str]:
        return list(cls._registry)
