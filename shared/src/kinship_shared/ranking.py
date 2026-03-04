"""
Federated ranking layer for Kinship Earth.

Every adapter gets consistent ranking for free. The core principle:
retrieval and ranking are separate problems. Adapters fetch raw records.
This module scores them.

Design decisions (2026-03-03):
- Wide net + post-ranking: fetch 5x limit, rank, return top N
- Never silently filter: tag quality issues, score them lower, return them
- Expose components, not just a scalar: agents can reason about tradeoffs
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from .schema import EcologicalObservation, SearchParams, SearchRelevance


def score_observation(
    obs: EcologicalObservation,
    params: SearchParams,
) -> SearchRelevance:
    """
    Score an observation against search parameters.

    Returns a SearchRelevance with component scores and a composite.
    Components are weighted: geo (0.35), taxon (0.30), temporal (0.15), quality (0.20).
    """
    geo_km = None
    geo_score = 1.0
    taxon_match = None
    taxon_score = 1.0
    temporal_days = None
    temporal_score = 1.0
    quality_score = _quality_score(obs)
    explanation_parts = []

    # --- Geographic distance ---
    if params.lat is not None and params.lng is not None:
        geo_km = _haversine_km(
            params.lat, params.lng,
            obs.location.lat, obs.location.lng,
        )
        if params.radius_km and params.radius_km > 0:
            # Score: 1.0 at center, 0.0 at edge, linear decay
            geo_score = max(0.0, 1.0 - (geo_km / params.radius_km))
        else:
            # No radius specified — use 500km as default decay
            geo_score = max(0.0, 1.0 - (geo_km / 500.0))
        explanation_parts.append(f"{geo_km:.1f}km")

    # --- Taxon match ---
    if params.taxon and obs.taxon:
        taxon_match = _taxon_match_score(params.taxon, obs.taxon)
        taxon_score = taxon_match
        match_level = {1.0: "exact species", 0.8: "genus", 0.6: "family", 0.4: "order"}
        explanation_parts.append(match_level.get(taxon_match, f"taxon={taxon_match:.1f}"))

    # --- Temporal distance ---
    if params.start_date and params.end_date:
        try:
            query_mid = datetime.fromisoformat(params.start_date)
            temporal_days = abs((obs.observed_at.replace(tzinfo=None) - query_mid).days)
            # Score: 1.0 for same day, 0.5 at 30 days, 0.0 at 365 days
            temporal_score = max(0.0, 1.0 - (temporal_days / 365.0))
            explanation_parts.append(obs.observed_at.strftime("%Y-%m-%d"))
        except (ValueError, TypeError):
            pass

    # --- Quality ---
    tier = obs.quality.tier or 4
    explanation_parts.append(f"tier-{tier}")

    # --- Composite ---
    composite = (
        0.35 * geo_score
        + 0.30 * taxon_score
        + 0.15 * temporal_score
        + 0.20 * quality_score
    )

    return SearchRelevance(
        score=round(composite, 3),
        geo_distance_km=round(geo_km, 2) if geo_km is not None else None,
        taxon_match=taxon_match,
        temporal_distance_days=temporal_days,
        quality_score=round(quality_score, 2),
        explanation="; ".join(explanation_parts),
    )


def rank_observations(
    observations: list[EcologicalObservation],
    params: SearchParams,
) -> list[tuple[EcologicalObservation, SearchRelevance]]:
    """
    Rank a list of observations by relevance to search parameters.

    Returns (observation, relevance) tuples sorted by score descending.
    """
    scored = [
        (obs, score_observation(obs, params))
        for obs in observations
    ]
    scored.sort(key=lambda x: x[1].score, reverse=True)
    return scored


# ---------------------------------------------------------------------------
# Component scoring helpers
# ---------------------------------------------------------------------------

def _quality_score(obs: EcologicalObservation) -> float:
    """Score based on quality tier: 1=1.0, 2=0.75, 3=0.5, 4=0.25."""
    tier = obs.quality.tier or 4
    return {1: 1.0, 2: 0.75, 3: 0.5, 4: 0.25}.get(tier, 0.25)


def _taxon_match_score(query_name: str, taxon) -> float:
    """
    Score taxonomic match between a query name and an observation's taxon.

    Exact species match = 1.0
    Genus match = 0.8
    Family match = 0.6 (future: when we have GBIF backbone resolution)
    No match = 0.0
    """
    query_lower = query_name.lower().strip()
    sci_name = (taxon.scientific_name or "").lower().strip()

    # Exact species match
    if query_lower == sci_name:
        return 1.0

    # Genus match (first word of binomial)
    query_genus = query_lower.split()[0] if query_lower else ""
    obs_genus = sci_name.split()[0] if sci_name else ""
    if query_genus and obs_genus and query_genus == obs_genus:
        return 0.8

    # Check common name
    common = (taxon.common_name or "").lower()
    if query_lower and query_lower in common:
        return 0.9

    return 0.0


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine distance between two points in kilometres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))
