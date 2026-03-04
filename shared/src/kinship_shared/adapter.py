"""
Abstract base class for all Kinship Earth ecological data adapters.

Every data source — NEON, OBIS, ERA5, Xeno-canto, eBird, citizen science sensors —
implements this interface. Adding a new source = write one adapter.
"""

from abc import ABC, abstractmethod
from typing import Optional

from .schema import AdapterCapabilities, EcologicalObservation, SearchParams


class EcologicalAdapter(ABC):
    """
    Base class for all ecological data source adapters.

    Each adapter translates a specific API's data format into the unified
    EcologicalObservation schema. The adapter registry routes queries to the
    right adapters based on capabilities and search parameters.
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """
        Unique adapter identifier.
        E.g. "neonscience", "obis", "xeno-canto", "ebird", "gbif"
        """

    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        """
        Self-description of what this adapter provides.
        Used by the registry to route queries and by agents to discover sources.
        """

    @abstractmethod
    async def search(self, params: SearchParams) -> list[EcologicalObservation]:
        """
        Search for observations matching the given parameters.
        Returns an empty list if no results found — never raises for no results.
        """

    @abstractmethod
    async def get_by_id(self, source_id: str) -> Optional[EcologicalObservation]:
        """
        Fetch a specific observation by its source system ID.
        Returns None if not found.
        """

    def __repr__(self) -> str:
        return f"<EcologicalAdapter id={self.id!r}>"
