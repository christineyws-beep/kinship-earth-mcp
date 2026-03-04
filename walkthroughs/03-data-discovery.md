# Walkthrough 3: Ecological Data Discovery

**Persona:** A graduate student or journalist who doesn't know what ecological data exists.
**Time:** ~2 minutes

---

## The question

> "I'm writing about biodiversity loss in the Pacific Northwest. What ecological data is out there that I could use?"

## Step by step

### Step 1: Discover available data sources

Ask Claude:

> "What ecological data sources does Kinship Earth have access to?"

**What happens:** Claude calls `ecology_describe_sources`. You get a structured overview of all three data sources:
- **NEON:** 81 US sites, sensor/occurrence/acoustic/geospatial data, quality tier 1
- **OBIS:** Global oceans, 168M+ occurrence records, quality tier 2
- **ERA5:** Global climate from 1940, hourly at 25km resolution, quality tier 1

Each includes: what modalities it covers, geographic scope, whether auth is needed, and search capabilities.

### Step 2: Explore what's near a specific location

Ask Claude:

> "What ecological data exists near Seattle, Washington (latitude 47.6, longitude -122.3)?"

**What happens:** Claude calls `ecology_search` with just the coordinates. You get:
- NEON sites within range (may find sites in the Pacific Northwest domain)
- OBIS marine records from Puget Sound
- A count of what each source returned

### Step 3: Zoom into climate trends

Ask Claude:

> "What was the climate like in this area during the record heat dome in late June 2021? Show me June 25-30."

**What happens:** Claude calls `era5_get_daily_summary` for those specific dates. During the 2021 Pacific Northwest heat dome, temperatures hit 46°C in some areas. The ERA5 data should show the dramatic temperature spike — a real, verifiable climate event.

---

## What this validates

- **Discovery works for non-experts:** Someone who doesn't know NEON/OBIS/ERA5 can find them
- **Natural language queries work:** No need to know API parameters
- **Climate data captures real events:** The 2021 heat dome is a known-answer test
- **The tool is genuinely useful for journalism/education:** Not just researchers
