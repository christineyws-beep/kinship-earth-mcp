"""kinship-shared: unified schema and adapter interface for Kinship Earth."""

from .adapter import EcologicalAdapter
from .ecology_tools import (
    run_describe_sources,
    run_get_environmental_context,
    run_search,
)
from .geojson import observations_to_geojson
from .ranking import rank_observations, score_observation
from .retry import http_get_with_retry
from .storage import ConversationStore, ConversationTurn
from .citations import get_bibtex, get_citations
from .export import to_bibtex, to_csv, to_geojson, to_markdown
from .summarize import make_human_summary, summarize_search_result
from .storage_sqlite import SQLiteConversationStore
from .schema import (
    AdapterCapabilities,
    EcologicalAnomaly,
    EcologicalEvent,
    EcologicalObservation,
    EcosystemState,
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
    "http_get_with_retry",
    "run_describe_sources",
    "run_get_environmental_context",
    "run_search",
    "observations_to_geojson",
    "EcologicalAnomaly",
    "EcologicalEvent",
    "EcosystemState",
    "ConversationTurn",
    "ConversationStore",
    "SQLiteConversationStore",
    "summarize_search_result",
    "make_human_summary",
    "get_citations",
    "get_bibtex",
    "to_csv",
    "to_geojson",
    "to_markdown",
    "to_bibtex",
]
