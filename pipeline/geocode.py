"""Geocoding helper for training providers.

Uses Nominatim (OpenStreetMap) via geopy — no API key required.
Results are cached in pipeline/_scratch/geocode_cache.json so that
each (city, region, country) tuple is only geocoded once.

Usage::

    from pipeline.geocode import geocode_providers
    enriched = geocode_providers(valid_providers)

If geopy is not installed a warning is logged and providers get
lat=None / lng=None unchanged.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_PATH = Path(__file__).parent / "_scratch" / "geocode_cache.json"
_USER_AGENT = "IdRatherBeSailing/1.0"
_SLEEP_SECS = 1.1  # Nominatim ToS: max 1 req/s


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_cache() -> dict[str, dict[str, Any] | None]:
    if _CACHE_PATH.exists():
        try:
            return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_cache(cache: dict[str, dict[str, Any] | None]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def _cache_key(city: str | None, region: str | None, country: str | None) -> str:
    return "|".join(str(v or "") for v in (city, region, country))


def _geocode_one(
    geocoder: Any,
    city: str | None,
    region: str | None,
    country: str | None,
) -> dict[str, float] | None:
    """Try progressively coarser queries until we get a hit or give up."""
    queries: list[str] = []

    # Build query candidates from most specific to least specific
    parts_full = [p for p in (city, region, country) if p]
    if parts_full:
        queries.append(", ".join(parts_full))

    if city and country:
        queries.append(f"{city}, {country}")
    if region and country:
        queries.append(f"{region}, {country}")
    if country:
        queries.append(country)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_queries: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique_queries.append(q)

    for query in unique_queries:
        try:
            time.sleep(_SLEEP_SECS)
            location = geocoder.geocode(query, exactly_one=True, timeout=10)
            if location is not None:
                return {"lat": location.latitude, "lng": location.longitude}
        except Exception as exc:
            logger.warning("Geocode error for %r: %s", query, exc)

    return None


def geocode_providers(providers: list[dict]) -> list[dict]:
    """Add lat/lng to each provider dict, using a local cache.

    Returns the same list (mutated in-place) with lat and lng set.
    Providers that already have non-None lat/lng are left untouched.
    """
    try:
        from geopy.geocoders import Nominatim  # type: ignore[import]
    except ImportError:
        logger.warning(
            "geopy not installed — skipping geocoding. "
            "Run: pip install geopy"
        )
        for p in providers:
            p.setdefault("lat", None)
            p.setdefault("lng", None)
        return providers

    geocoder = Nominatim(user_agent=_USER_AGENT)
    cache = _load_cache()
    cache_dirty = False

    # Collect unique location tuples that need geocoding
    unique_keys: set[str] = set()
    for p in providers:
        if p.get("lat") is not None:
            continue  # already geocoded
        key = _cache_key(p.get("city"), p.get("region"), p.get("country"))
        unique_keys.add(key)

    # Geocode those not in cache
    for key in sorted(unique_keys):
        if key in cache:
            continue
        city, region, country = (part if part else None for part in key.split("|", 2))
        logger.info("Geocoding: %r", key)
        result = _geocode_one(geocoder, city, region, country)
        cache[key] = result
        cache_dirty = True
        _save_cache(cache)

    if cache_dirty:
        _save_cache(cache)

    # Apply cached results to providers
    hit = miss = skip = 0
    for p in providers:
        if p.get("lat") is not None:
            skip += 1
            continue
        key = _cache_key(p.get("city"), p.get("region"), p.get("country"))
        result = cache.get(key)
        if result:
            p["lat"] = result["lat"]
            p["lng"] = result["lng"]
            hit += 1
        else:
            p.setdefault("lat", None)
            p.setdefault("lng", None)
            miss += 1

    logger.info(
        "Geocoding complete: %d placed, %d unresolved, %d already had coordinates",
        hit, miss, skip,
    )
    return providers
