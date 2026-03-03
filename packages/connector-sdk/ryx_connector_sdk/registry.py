"""Registre des connecteurs DMI disponibles."""

from .interfaces import BaseConnector, ConnectorConfig


class ConnectorRegistry:
    """
    Registre des connecteurs disponibles.

    Usage :
        registry = ConnectorRegistry()
        registry.register("fhir", FhirConnector)
        registry.register("openmrs", OpenMrsConnector)

        connector = registry.create("fhir", config)
    """

    def __init__(self):
        self._connectors: dict[str, type[BaseConnector]] = {}

    def register(self, name: str, connector_class: type[BaseConnector]) -> None:
        self._connectors[name] = connector_class

    def create(self, name: str, config: ConnectorConfig) -> BaseConnector:
        if name not in self._connectors:
            raise ValueError(f"Unknown connector: {name}. Available: {list(self._connectors)}")
        return self._connectors[name](config)

    def list_available(self) -> list[str]:
        return list(self._connectors.keys())


# Registre global
registry = ConnectorRegistry()
