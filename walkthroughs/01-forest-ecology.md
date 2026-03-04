# Walkthrough 1: Forest Ecology Site Characterization

**Persona:** A forest ecologist studying old-growth Douglas-fir at Wind River, WA.
**Time:** ~3 minutes

---

## The question

> "I'm planning fieldwork at NEON's Wind River site for next summer. What were conditions like during the 2023 breeding season, and what monitoring data is available there?"

## Step by step

### Step 1: Get the environmental context

Ask Claude:

> "What were the environmental conditions at Wind River Experimental Forest (latitude 45.82, longitude -121.95) during June 15-21, 2023?"

**What happens:** Claude calls `ecology_get_environmental_context`, which hits ERA5 for climate data and NEON for nearby monitoring sites — in parallel. You get:
- Daily temperature (min/max/mean), precipitation, wind, radiation
- Soil temperature and moisture at the surface
- The WREF NEON site with its 156+ available data products
- Full provenance (ERA5 DOI, NEON portal link)

### Step 2: Explore what NEON collects there

Ask Claude:

> "What data products does the WREF NEON site collect? I'm especially interested in bird surveys and soil data."

**What happens:** Claude calls `neon_get_site` and `neon_list_data_products` to show the full catalog. You'll see bird point counts (DP1.10003), soil sensors, canopy structure, and more.

### Step 3: Check for marine context nearby

Ask Claude:

> "Are there any marine biodiversity records within 200km of Wind River? I'm curious about the ecological connection between forest and coastal systems."

**What happens:** Claude calls `ecology_search` with the coordinates and a 200km radius. OBIS may return records from the Pacific coast (Puget Sound, Oregon coast). This demonstrates the cross-source value — terrestrial monitoring + marine biodiversity in one query.

---

## What this validates

- **Cross-source orchestration works:** ERA5 climate + NEON sites in one call
- **Data is scientifically plausible:** PNW June temperatures should be 10-30°C
- **Provenance is complete:** ERA5 DOI, NEON portal URLs, quality tiers
- **Response is useful for planning:** A real ecologist could use this to prepare for fieldwork
