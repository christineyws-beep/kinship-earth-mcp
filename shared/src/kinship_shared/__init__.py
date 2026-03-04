"""kinship-shared: unified schema and adapter interface for Kinship Earth."""

from .adapter import EcologicalAdapter
from .ranking import rank_observations, score_observation
from .schema import (
    AdapterCapabilities,
    EcologicalObservation,
    Location,
    Provenance,
    Quality,
    SearchParams,
    SearchRelevance,
    SignalModality,
    TaxonInfo,
)

__all__ = [
    "EcologicalAdapter",
    "EcologicalObservation",
    "AdapterCapabilities",
    "SearchParams",
    "SearchRelevance",
    "SignalModality",
    "Location",
    "TaxonInfo",
    "Quality",
    "Provenance",
    "rank_observations",
    "score_observation",
]
