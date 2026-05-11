"""
Conversation → Graph extraction pipeline.

Converts stored conversation turns and their tool results into
knowledge graph entities and relationships. Every query a user
makes creates nodes and edges that compound over time.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

from .graph_schema import (
    GraphEntity,
    GraphRelationship,
    TemporalFact,
    make_location_id,
    make_neon_site_id,
    make_query_id,
    make_source_id,
    make_species_id,
    make_user_id,
)
from .storage import ConversationTurn

logger = logging.getLogger(__name__)


class ExtractedGraph(BaseModel):
    """Output of entity extraction from a conversation turn."""
    entities: list[GraphEntity] = []
    relationships: list[GraphRelationship] = []
    facts: list[TemporalFact] = []


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class EntityExtractor:
    """Extracts entities and relationships from tool calls and results."""

    def extract_from_turn(
        self, turn: ConversationTurn, result: dict
    ) -> ExtractedGraph:
        """Extract entities and relationships from a single conversation turn."""
        tool = turn.tool_name
        now = datetime.now(tz=timezone.utc)

        if tool in ("ecology_search", "ecology_whats_around_me", "ecology_biodiversity_assessment"):
            return self._extract_from_search(turn, result, now)
        elif tool == "ecology_get_environmental_context":
            return self._extract_from_env_context(turn, result, now)
        elif tool == "ecology_temporal_comparison":
            return self._extract_from_temporal(turn, result, now)
        else:
            return ExtractedGraph()

    def _extract_from_search(
        self, turn: ConversationTurn, result: dict, now: datetime
    ) -> ExtractedGraph:
        entities: list[GraphEntity] = []
        relationships: list[GraphRelationship] = []
        facts: list[TemporalFact] = []

        # Query entity
        query_id = make_query_id(turn.id)
        entities.append(GraphEntity(
            id=query_id,
            entity_type="query",
            name=f"{turn.tool_name}: {turn.tool_params.get('scientificname', '')} @ ({turn.lat}, {turn.lng})",
            properties={
                "tool_name": turn.tool_name,
                "params": turn.tool_params,
                "timestamp": now.isoformat(),
            },
        ))

        # Researcher entity (if user_id present)
        if turn.user_id:
            user_id = make_user_id(turn.user_id)
            entities.append(GraphEntity(
                id=user_id,
                entity_type="researcher",
                name=turn.user_id,
            ))
            relationships.append(GraphRelationship(
                source_id=query_id,
                target_id=user_id,
                relationship_type="QUERIED_BY",
            ))

        # Location entity
        location_id = None
        if turn.lat is not None and turn.lng is not None:
            location_id = make_location_id(turn.lat, turn.lng)
            entities.append(GraphEntity(
                id=location_id,
                entity_type="location",
                name=f"({turn.lat:.2f}, {turn.lng:.2f})",
                properties={"lat": turn.lat, "lng": turn.lng},
            ))
            relationships.append(GraphRelationship(
                source_id=query_id,
                target_id=location_id,
                relationship_type="QUERIED_ABOUT",
            ))

        # Species from observations
        species_locations: dict[str, list[str]] = {}  # species_id -> [location_ids]

        for occ in result.get("species_occurrences", []):
            sci_name = occ.get("scientific_name")
            if not sci_name:
                continue

            species_id = make_species_id(sci_name)
            entities.append(GraphEntity(
                id=species_id,
                entity_type="species",
                name=sci_name,
                properties={
                    "common_name": occ.get("common_name", ""),
                },
            ))

            # Link query to species
            relationships.append(GraphRelationship(
                source_id=query_id,
                target_id=species_id,
                relationship_type="QUERIED_ABOUT",
            ))

            # Species observed at location
            occ_lat = occ.get("lat")
            occ_lng = occ.get("lng")
            if occ_lat is not None and occ_lng is not None:
                occ_loc_id = make_location_id(occ_lat, occ_lng)
                if occ_loc_id != location_id:
                    entities.append(GraphEntity(
                        id=occ_loc_id,
                        entity_type="location",
                        name=f"({occ_lat:.2f}, {occ_lng:.2f})",
                        properties={"lat": occ_lat, "lng": occ_lng},
                    ))

                relationships.append(GraphRelationship(
                    source_id=species_id,
                    target_id=occ_loc_id,
                    relationship_type="OBSERVED_AT",
                    properties={
                        "observed_at": occ.get("observed_at", ""),
                        "source": occ.get("source", ""),
                        "quality_tier": occ.get("quality_tier"),
                    },
                ))

                # Track for co-occurrence
                if species_id not in species_locations:
                    species_locations[species_id] = []
                species_locations[species_id].append(occ_loc_id)

        # Co-occurrence detection: species at same location
        loc_to_species: dict[str, list[str]] = {}
        for sp_id, locs in species_locations.items():
            for loc_id in locs:
                if loc_id not in loc_to_species:
                    loc_to_species[loc_id] = []
                loc_to_species[loc_id].append(sp_id)

        for loc_id, sp_ids in loc_to_species.items():
            unique_species = list(set(sp_ids))
            for i in range(len(unique_species)):
                for j in range(i + 1, len(unique_species)):
                    relationships.append(GraphRelationship(
                        source_id=unique_species[i],
                        target_id=unique_species[j],
                        relationship_type="CORRELATES_WITH",
                        properties={"shared_location": loc_id},
                    ))

        # NEON sites
        for site in result.get("neon_sites", []):
            site_code = site.get("site_code")
            if site_code:
                site_id = make_neon_site_id(site_code)
                entities.append(GraphEntity(
                    id=site_id,
                    entity_type="neon_site",
                    name=site.get("site_name", site_code),
                    properties={
                        "lat": site.get("lat"),
                        "lng": site.get("lng"),
                        "state": site.get("state"),
                        "data_products": site.get("data_products"),
                    },
                ))
                if location_id:
                    relationships.append(GraphRelationship(
                        source_id=location_id,
                        target_id=site_id,
                        relationship_type="MONITORED_BY",
                    ))

        # Data sources used
        for source in result.get("search_context", {}).get("sources_queried", []):
            src_id = make_source_id(source)
            entities.append(GraphEntity(
                id=src_id,
                entity_type="data_source",
                name=source,
            ))
            relationships.append(GraphRelationship(
                source_id=query_id,
                target_id=src_id,
                relationship_type="SOURCED_FROM",
            ))

        return ExtractedGraph(entities=entities, relationships=relationships, facts=facts)

    def _extract_from_env_context(
        self, turn: ConversationTurn, result: dict, now: datetime
    ) -> ExtractedGraph:
        entities: list[GraphEntity] = []
        relationships: list[GraphRelationship] = []
        facts: list[TemporalFact] = []

        # Location
        location_id = None
        if turn.lat is not None and turn.lng is not None:
            location_id = make_location_id(turn.lat, turn.lng)
            entities.append(GraphEntity(
                id=location_id,
                entity_type="location",
                name=f"({turn.lat:.2f}, {turn.lng:.2f})",
                properties={"lat": turn.lat, "lng": turn.lng},
            ))

        # NEON sites
        for site in result.get("nearby_neon_sites", []):
            site_code = site.get("site_code")
            if site_code:
                site_id = make_neon_site_id(site_code)
                entities.append(GraphEntity(
                    id=site_id,
                    entity_type="neon_site",
                    name=site.get("site_name", site_code),
                    properties={"lat": site.get("lat"), "lng": site.get("lng")},
                ))
                if location_id:
                    relationships.append(GraphRelationship(
                        source_id=location_id,
                        target_id=site_id,
                        relationship_type="MONITORED_BY",
                    ))

        # Climate as temporal facts
        climate = result.get("climate", {})
        daily = climate.get("daily", {})
        temps = daily.get("temperature_2m_mean", [])
        if location_id and temps:
            query = result.get("query", {})
            start = query.get("climate_window", {}).get("start", now.isoformat()[:10])
            end = query.get("climate_window", {}).get("end", now.isoformat()[:10])

            facts.append(TemporalFact(
                id=f"climate:{location_id}:{start}:{end}",
                entity_id=location_id,
                fact_type="climate_observation",
                value={
                    "temp_mean": round(sum(temps) / len(temps), 2) if temps else None,
                    "temp_min": round(min(temps), 2) if temps else None,
                    "temp_max": round(max(temps), 2) if temps else None,
                    "period": f"{start} to {end}",
                },
                valid_from=datetime.fromisoformat(start) if start else now,
                source="era5",
            ))

        return ExtractedGraph(entities=entities, relationships=relationships, facts=facts)

    def _extract_from_temporal(
        self, turn: ConversationTurn, result: dict, now: datetime
    ) -> ExtractedGraph:
        """Extract from temporal comparison — captures species gained/lost."""
        entities: list[GraphEntity] = []
        relationships: list[GraphRelationship] = []

        location_id = None
        if turn.lat is not None and turn.lng is not None:
            location_id = make_location_id(turn.lat, turn.lng)
            entities.append(GraphEntity(
                id=location_id,
                entity_type="location",
                name=f"({turn.lat:.2f}, {turn.lng:.2f})",
            ))

        deltas = result.get("deltas", {})

        # Species gained and lost are interesting entities
        for name in deltas.get("species_gained", []):
            sp_id = make_species_id(name)
            entities.append(GraphEntity(id=sp_id, entity_type="species", name=name))
            if location_id:
                relationships.append(GraphRelationship(
                    source_id=sp_id, target_id=location_id,
                    relationship_type="OBSERVED_AT",
                    properties={"context": "gained_in_period_b"},
                ))

        for name in deltas.get("species_lost", []):
            sp_id = make_species_id(name)
            entities.append(GraphEntity(id=sp_id, entity_type="species", name=name))

        return ExtractedGraph(entities=entities, relationships=relationships)
