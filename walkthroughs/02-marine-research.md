# Walkthrough 2: Marine Species Distribution Research

**Persona:** A marine biologist studying common dolphin distribution in the North Atlantic.
**Time:** ~3 minutes

---

## The question

> "I'm researching Delphinus delphis distribution off the US East Coast. Where have they been observed near Woods Hole, and what were the ocean conditions?"

## Step by step

### Step 1: Search for dolphin occurrences with climate context

Ask Claude:

> "Search for common dolphin (Delphinus delphis) sightings within 200km of Woods Hole, Massachusetts (latitude 41.5, longitude -70.7) from 2015 to 2023."

**What happens:** Claude calls `ecology_search`, which queries OBIS for occurrence records and ERA5 for climate data — simultaneously. You get:
- Dolphin occurrence records with coordinates, dates, taxonomy, and quality flags
- Each record scored by relevance (distance from Woods Hole, taxonomic match, quality)
- Daily climate summary for the search area
- Records sorted by relevance score (closest + best quality first)

### Step 2: Examine a specific record

Ask Claude:

> "Tell me more about the highest-ranked dolphin sighting. What was the basis of record? Is this a verified observation?"

**What happens:** Claude examines the relevance scores and record details. You'll see:
- `basis_of_record`: HumanObservation, MachineObservation, or PreservedSpecimen
- `quality_tier`: 2 (community-validated)
- `license`: per-record license from the contributing institution
- Source URL linking back to the original OBIS record

### Step 3: Discover what other data exists in the area

Ask Claude:

> "What ecological data sources are available, and what monitoring exists near this location?"

**What happens:** Claude calls `ecology_describe_sources` to show all three data sources and their capabilities. You'll see that NEON doesn't have marine sites near Woods Hole (it's terrestrial), but ERA5 provides climate context for the ocean area.

---

## What this validates

- **Species search works:** OBIS returns real dolphin records near Woods Hole
- **Relevance scoring is useful:** Records sorted by distance + quality, not random order
- **Cross-source context adds value:** Climate data alongside species observations
- **Provenance supports research:** Per-record licenses, source URLs, quality flags
- **Known limitation is visible:** No sea surface temperature (SST) — documented gap
