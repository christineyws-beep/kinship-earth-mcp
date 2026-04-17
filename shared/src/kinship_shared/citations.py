"""
Citation registry for all Kinship Earth data sources.

Provides properly formatted citations (BibTeX, APA) with DOIs,
licenses, and access information for scientific use.
"""

from __future__ import annotations

from datetime import datetime, timezone

CITATIONS: dict[str, dict] = {
    "obis": {
        "name": "Ocean Biodiversity Information System (OBIS)",
        "bibtex": (
            "@misc{obis,\n"
            "  title = {Ocean Biodiversity Information System},\n"
            "  url = {https://obis.org},\n"
            "  note = {Intergovernmental Oceanographic Commission of UNESCO},\n"
            "  year = {2024},\n"
            "}"
        ),
        "apa": "OBIS (2024). Ocean Biodiversity Information System. Intergovernmental Oceanographic Commission of UNESCO. https://obis.org",
        "doi": None,
        "license": "CC-BY 4.0 (varies by dataset)",
        "homepage": "https://obis.org",
    },
    "neonscience": {
        "name": "National Ecological Observatory Network (NEON)",
        "bibtex": (
            "@misc{neon,\n"
            "  title = {National Ecological Observatory Network},\n"
            "  url = {https://www.neonscience.org},\n"
            "  note = {Battelle, managed by the National Science Foundation},\n"
            "  year = {2024},\n"
            "}"
        ),
        "apa": "National Ecological Observatory Network (NEON). (2024). https://www.neonscience.org. Battelle, managed by NSF.",
        "doi": None,
        "license": "CC0 1.0 (data), varies (derived products)",
        "homepage": "https://www.neonscience.org",
    },
    "era5": {
        "name": "ERA5 Global Reanalysis (ECMWF/Copernicus)",
        "bibtex": (
            "@article{era5,\n"
            "  author = {Hersbach, Hans and Bell, Bill and Berrisford, Paul and others},\n"
            "  title = {The ERA5 global reanalysis},\n"
            "  journal = {Quarterly Journal of the Royal Meteorological Society},\n"
            "  volume = {146},\n"
            "  number = {730},\n"
            "  pages = {1999--2049},\n"
            "  year = {2020},\n"
            "  doi = {10.1002/qj.3803},\n"
            "}"
        ),
        "apa": "Hersbach, H., Bell, B., Berrisford, P., et al. (2020). The ERA5 global reanalysis. Q.J.R. Meteorol. Soc., 146(730), 1999-2049. https://doi.org/10.1002/qj.3803",
        "doi": "10.1002/qj.3803",
        "license": "CC-BY-4.0",
        "homepage": "https://cds.climate.copernicus.eu",
    },
    "ebird": {
        "name": "eBird Basic Dataset (Cornell Lab of Ornithology)",
        "bibtex": (
            "@misc{ebird,\n"
            "  author = {{Cornell Lab of Ornithology}},\n"
            "  title = {eBird Basic Dataset},\n"
            "  url = {https://ebird.org},\n"
            "  year = {2024},\n"
            "}"
        ),
        "apa": "Cornell Lab of Ornithology. (2024). eBird Basic Dataset. https://ebird.org",
        "doi": None,
        "license": "eBird Terms of Use",
        "homepage": "https://ebird.org",
    },
    "inaturalist": {
        "name": "iNaturalist",
        "bibtex": (
            "@misc{inaturalist,\n"
            "  title = {iNaturalist},\n"
            "  url = {https://www.inaturalist.org},\n"
            "  note = {California Academy of Sciences and National Geographic Society},\n"
            "  year = {2024},\n"
            "}"
        ),
        "apa": "iNaturalist. (2024). California Academy of Sciences and National Geographic Society. https://www.inaturalist.org",
        "doi": None,
        "license": "CC-BY-NC 4.0 (varies by observation)",
        "homepage": "https://www.inaturalist.org",
    },
    "gbif": {
        "name": "Global Biodiversity Information Facility (GBIF)",
        "bibtex": (
            "@misc{gbif,\n"
            "  title = {Global Biodiversity Information Facility},\n"
            "  url = {https://www.gbif.org},\n"
            "  year = {2024},\n"
            "}"
        ),
        "apa": "GBIF.org (2024). Global Biodiversity Information Facility. https://www.gbif.org",
        "doi": None,
        "license": "CC-BY 4.0 (varies by dataset)",
        "homepage": "https://www.gbif.org",
    },
    "usgs-nwis": {
        "name": "USGS National Water Information System",
        "bibtex": (
            "@misc{usgs_nwis,\n"
            "  author = {{U.S. Geological Survey}},\n"
            "  title = {National Water Information System},\n"
            "  url = {https://waterdata.usgs.gov/nwis},\n"
            "  year = {2024},\n"
            "}"
        ),
        "apa": "U.S. Geological Survey. (2024). National Water Information System. https://waterdata.usgs.gov/nwis",
        "doi": None,
        "license": "Public Domain (U.S. Government)",
        "homepage": "https://waterdata.usgs.gov/nwis",
    },
    "xeno-canto": {
        "name": "Xeno-canto Foundation",
        "bibtex": (
            "@misc{xenocanto,\n"
            "  title = {Xeno-canto: Sharing bird sounds from around the world},\n"
            "  url = {https://xeno-canto.org},\n"
            "  year = {2024},\n"
            "}"
        ),
        "apa": "Xeno-canto Foundation. (2024). Xeno-canto: Sharing bird sounds from around the world. https://xeno-canto.org",
        "doi": None,
        "license": "CC (varies by recording)",
        "homepage": "https://xeno-canto.org",
    },
    "soilgrids": {
        "name": "SoilGrids (ISRIC World Soil Information)",
        "bibtex": (
            "@article{soilgrids,\n"
            "  author = {Poggio, Laura and de Sousa, Luis M. and Batjes, Niels H. and others},\n"
            "  title = {SoilGrids 2.0: producing soil information for the globe},\n"
            "  journal = {SOIL},\n"
            "  volume = {7},\n"
            "  pages = {217--240},\n"
            "  year = {2021},\n"
            "  doi = {10.5194/soil-7-217-2021},\n"
            "}"
        ),
        "apa": "Poggio, L., de Sousa, L. M., Batjes, N. H., et al. (2021). SoilGrids 2.0: producing soil information for the globe. SOIL, 7, 217-240. https://doi.org/10.5194/soil-7-217-2021",
        "doi": "10.5194/soil-7-217-2021",
        "license": "CC-BY 4.0",
        "homepage": "https://soilgrids.org",
    },
}


def get_citations(source_ids: list[str] | None = None) -> dict:
    """Get citations for specified sources, or all if none specified."""
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    if source_ids is None:
        source_ids = list(CITATIONS.keys())

    results = {}
    for sid in source_ids:
        if sid in CITATIONS:
            entry = CITATIONS[sid].copy()
            entry["accessed"] = today
            results[sid] = entry

    return {
        "citations": results,
        "count": len(results),
        "access_date": today,
        "generated_by": "Kinship Earth MCP",
    }


def get_bibtex(source_ids: list[str] | None = None) -> str:
    """Get combined BibTeX entries for sources."""
    data = get_citations(source_ids)
    entries = []
    for sid, citation in data["citations"].items():
        entries.append(citation["bibtex"])
    return "\n\n".join(entries)
