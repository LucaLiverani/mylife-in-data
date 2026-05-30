"""Google Maps Platform — Places API (Find Place from Text) + Geocoding API.

Used to enrich `bronze.maps_activity` rows with neighborhood, primary place
type, and country. Caching is essential: each unique place is looked up
exactly once and persisted in `bronze.maps_place_catalog`. Subsequent activity
referencing the same place hits the catalog, not the API.

Auth: GOOGLE_MAPS_API_KEY (server-side key, separate from the OAuth flow).

Cost (May 2026 pricing):
  Find Place from Text   $17 / 1k calls
  Geocoding (reverse)    $5  / 1k calls
  $200/mo free credit → ~11k Places + ~40k Geocoding free for personal use.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import requests


log = logging.getLogger(__name__)


# Place types Google returns are often a stack of generic to specific:
#   ['restaurant', 'food', 'point_of_interest', 'establishment']
# We want 'restaurant'. So we filter out these generic catch-alls.
GENERIC_TYPES = {
    "point_of_interest",
    "establishment",
    "place_of_worship",  # too generic — usually paired with church/mosque/etc
    "food",              # paired with restaurant/cafe/bakery
    "premise",
    "subpremise",
    "political",
    "geocode",
    "street_address",
    "route",
}


@dataclass
class PlaceLookup:
    """Result shape from places_api lookups — maps 1:1 to bronze.maps_place_catalog."""

    place_id: str
    place_name: str
    place_types: list[str]
    primary_type: str
    lat: float
    lng: float
    formatted_address: str
    neighborhood: str
    sublocality: str
    locality: str
    admin_area_1: str
    country: str
    country_code: str
    # Quality signals from the geocoder (e.g. Geoapify rank.confidence /
    # result_type). Defaulted so existing constructors keep working unchanged.
    match_confidence: float = 0.0
    match_type: str = ""


def _pick_primary_type(types: list[str]) -> str:
    """First non-generic type wins. Falls back to first type or empty."""
    for t in types:
        if t not in GENERIC_TYPES:
            return t
    return types[0] if types else ""


def _extract_address_components(components: list[dict[str, Any]]) -> dict[str, str]:
    """Pull neighborhood / sublocality / locality / country from a Geocoding
    or Places API address_components array."""
    out: dict[str, str] = {
        "neighborhood": "",
        "sublocality": "",
        "locality": "",
        "admin_area_1": "",
        "country": "",
        "country_code": "",
    }
    for c in components or []:
        types = set(c.get("types") or [])
        long_name = c.get("long_name", "") or ""
        short_name = c.get("short_name", "") or ""
        if "neighborhood" in types and not out["neighborhood"]:
            out["neighborhood"] = long_name
        elif "sublocality" in types and not out["sublocality"]:
            out["sublocality"] = long_name
        elif "locality" in types and not out["locality"]:
            out["locality"] = long_name
        elif "administrative_area_level_1" in types and not out["admin_area_1"]:
            out["admin_area_1"] = long_name
        elif "country" in types:
            out["country"] = long_name
            out["country_code"] = short_name
    return out


class PlacesAPIClient:
    """Thin wrapper around Find Place from Text + Geocoding reverse."""

    FIND_PLACE_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

    FIND_PLACE_FIELDS = "place_id,name,types,geometry,formatted_address"
    PLACE_DETAILS_FIELDS = "place_id,name,types,geometry,formatted_address,address_component"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY not set — required for Places/Geocoding lookups")

    # ── Public API ────────────────────────────────────────────────────────
    def find_place(self, text: str) -> PlaceLookup | None:
        """Resolve a text query (e.g., 'African Queen Zurich') to a place."""
        if not text:
            return None
        resp = self._get(
            self.FIND_PLACE_URL,
            {
                "input": text,
                "inputtype": "textquery",
                "fields": self.FIND_PLACE_FIELDS,
            },
        )
        if not resp:
            return None
        candidates = resp.get("candidates") or []
        if not candidates:
            return None
        candidate = candidates[0]
        # Find Place doesn't return address_components; chase Place Details for those.
        place_id = candidate.get("place_id", "")
        if place_id:
            details = self._place_details(place_id)
            if details:
                return self._lookup_from_details(details)
        # Fallback: build from candidate alone (no neighborhood).
        return self._lookup_from_candidate(candidate)

    def reverse_geocode(self, lat: float, lng: float) -> PlaceLookup | None:
        """Resolve a lat/lng to a place + administrative areas."""
        if not (lat and lng):
            return None
        resp = self._get(
            self.GEOCODE_URL,
            {"latlng": f"{lat},{lng}"},
        )
        if not resp:
            return None
        results = resp.get("results") or []
        if not results:
            return None
        # Use the most-specific result (first item, typically a street_address).
        # Walk results to find one with the most useful address_components.
        best = results[0]
        components = _extract_address_components(best.get("address_components") or [])
        return PlaceLookup(
            place_id=best.get("place_id", ""),
            place_name="",
            place_types=list(best.get("types") or []),
            primary_type=_pick_primary_type(list(best.get("types") or [])),
            lat=lat,
            lng=lng,
            formatted_address=best.get("formatted_address", ""),
            **components,
        )

    # ── Internals ─────────────────────────────────────────────────────────
    def _place_details(self, place_id: str) -> dict[str, Any] | None:
        resp = self._get(
            self.PLACE_DETAILS_URL,
            {
                "place_id": place_id,
                "fields": self.PLACE_DETAILS_FIELDS,
            },
        )
        if not resp:
            return None
        return resp.get("result")

    def _get(self, url: str, params: dict[str, str]) -> dict[str, Any] | None:
        params = {**params, "key": self.api_key}
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=15)
            except requests.RequestException as exc:
                log.warning("HTTP error on %s (attempt %d): %s", url, attempt + 1, exc)
                time.sleep(1 + attempt)
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                log.warning("HTTP %d on %s (attempt %d) — retrying", r.status_code, url, attempt + 1)
                time.sleep(2 + attempt * 2)
                continue
            if not r.ok:
                log.error("HTTP %d on %s: %s", r.status_code, url, r.text[:200])
                return None
            data = r.json()
            status = data.get("status", "")
            if status == "OVER_QUERY_LIMIT":
                log.warning("OVER_QUERY_LIMIT — backing off")
                time.sleep(5)
                continue
            if status not in ("OK", "ZERO_RESULTS"):
                log.warning("API status=%s message=%s", status, data.get("error_message", ""))
                return None
            return data
        return None

    def _lookup_from_details(self, details: dict[str, Any]) -> PlaceLookup:
        geom = (details.get("geometry") or {}).get("location") or {}
        types = list(details.get("types") or [])
        components = _extract_address_components(details.get("address_components") or [])
        return PlaceLookup(
            place_id=details.get("place_id", ""),
            place_name=details.get("name", ""),
            place_types=types,
            primary_type=_pick_primary_type(types),
            lat=float(geom.get("lat") or 0.0),
            lng=float(geom.get("lng") or 0.0),
            formatted_address=details.get("formatted_address", ""),
            **components,
        )

    def _lookup_from_candidate(self, candidate: dict[str, Any]) -> PlaceLookup:
        geom = (candidate.get("geometry") or {}).get("location") or {}
        types = list(candidate.get("types") or [])
        return PlaceLookup(
            place_id=candidate.get("place_id", ""),
            place_name=candidate.get("name", ""),
            place_types=types,
            primary_type=_pick_primary_type(types),
            lat=float(geom.get("lat") or 0.0),
            lng=float(geom.get("lng") or 0.0),
            formatted_address=candidate.get("formatted_address", ""),
            neighborhood="",
            sublocality="",
            locality="",
            admin_area_1="",
            country="",
            country_code="",
        )


# The catalog-backed `get_or_lookup()` and the provider-neutral geocoder
# abstraction now live in geocoder.py — this module stays a pure Google client.
