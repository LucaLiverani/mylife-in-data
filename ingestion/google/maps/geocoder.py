"""Provider-neutral geocoding for Maps place enrichment.

`bronze.maps_activity` rows carry free text (a place name, a search query, a
directions destination) but almost never coordinates. This module resolves that
text to coordinates + address components (neighborhood / locality / country) +
a place type, and caches every lookup in `bronze.maps_place_catalog` so each
distinct place is resolved exactly once.

The backend is pluggable via GEOCODER_PROVIDER:
  - 'geoapify' (default) — OpenStreetMap-based, generous free tier, and results
                           may be stored under ODbL (attribution required), so a
                           persistent catalog is fine. Free-text / typo tolerant.
  - 'google'             — Google Places (Find Place + Details) via PlacesAPIClient.
  - 'hybrid'             — Geoapify first, Google as a fallback for misses.

Swapping providers never touches the catalog schema or the enrichment asset —
every backend returns a PlaceLookup.
"""

from __future__ import annotations

import logging
import os
import time

import requests

from .places_api import PlaceLookup, PlacesAPIClient


log = logging.getLogger(__name__)


class GeocoderConfigError(RuntimeError):
    """Raised when the selected geocoder is missing required configuration."""


# Queries that can't resolve to a public place — skip (and negative-cache) them
# instead of spending a lookup. Conservative on purpose: downstream confidence
# gating handles the rest.
_JUNK_EXACT = {
    "weather", "time", "news", "translate", "calculator",
    "maps", "google", "home", "work", "directions", "settings",
    # bare category searches — not a specific place
    "restaurant", "restaurants", "restaurantes", "bar", "bars",
    "cafe", "cafes", "hotel", "hotels", "supermarket", "atm",
    "pharmacy", "parking",
    # virtual-meeting "locations" common on calendar events — not a place
    "zoom", "google meet", "meet", "teams", "microsoft teams", "webex",
    "skype", "phone", "call", "online", "tbd", "n/a",
}

# Substrings that mark a non-place activity title (Maps UI artifacts, app
# chrome) or a virtual-meeting calendar location. "Explored on Google Maps" is
# the single most common MyActivity title — a pan/zoom, not a place.
_JUNK_SUBSTR = (
    "near me", "explored on google maps", "notification",
    "zoom.us", "meet.google", "teams.microsoft", "webex.com", "zoom meeting",
)


def is_geocodable_text(text: str) -> bool:
    """Cheap pre-filter: is this worth a geocoding call at all?"""
    t = (text or "").strip().lower()
    if len(t) < 2:
        return False
    if t.startswith(("http://", "https://", "www.")):  # a URL, not a place
        return False
    if t in _JUNK_EXACT:
        return False
    if any(s in t for s in _JUNK_SUBSTR):
        return False
    if not any(c.isalpha() for c in t):  # pure numbers / symbols
        return False
    return True


class Geocoder:
    """Interface: text / coords -> PlaceLookup (or None)."""

    provider = "base"

    def geocode(self, text: str) -> PlaceLookup | None:  # pragma: no cover - interface
        raise NotImplementedError

    def reverse(self, lat: float, lng: float) -> PlaceLookup | None:  # pragma: no cover
        raise NotImplementedError


class GeoapifyGeocoder(Geocoder):
    """OpenStreetMap-based geocoding via Geoapify (https://www.geoapify.com)."""

    provider = "geoapify"
    SEARCH_URL = "https://api.geoapify.com/v1/geocode/search"
    REVERSE_URL = "https://api.geoapify.com/v1/geocode/reverse"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GEOAPIFY_API_KEY", "")
        if not self.api_key:
            raise GeocoderConfigError("GEOAPIFY_API_KEY not set")
        self._session = requests.Session()

    def geocode(self, text: str) -> PlaceLookup | None:
        if not text:
            return None
        return self._first(self._get(self.SEARCH_URL, {"text": text, "limit": 1}))

    def reverse(self, lat: float, lng: float) -> PlaceLookup | None:
        if not (lat and lng):
            return None
        return self._first(self._get(self.REVERSE_URL, {"lat": lat, "lon": lng, "limit": 1}))

    def _first(self, data: dict | None) -> PlaceLookup | None:
        results = (data or {}).get("results") or []
        return self._parse_result(results[0]) if results else None

    @staticmethod
    def _parse_result(r: dict) -> PlaceLookup:
        category = r.get("category", "") or ""
        # 'catering.restaurant' -> 'restaurant'; fall back to result granularity.
        primary_type = category.split(".")[-1] if category else (r.get("result_type", "") or "")
        rank = r.get("rank") or {}
        return PlaceLookup(
            place_id=str(r.get("place_id", "") or ""),
            place_name=r.get("name", "") or r.get("address_line1", "") or "",
            place_types=[category] if category else [],
            primary_type=primary_type,
            lat=float(r.get("lat") or 0.0),
            lng=float(r.get("lon") or 0.0),
            formatted_address=r.get("formatted", "") or "",
            neighborhood=r.get("neighbourhood", "") or r.get("suburb", "") or r.get("district", "") or "",
            sublocality=r.get("district", "") or r.get("suburb", "") or "",
            locality=r.get("city", "") or "",
            admin_area_1=r.get("state", "") or "",
            country=r.get("country", "") or "",
            country_code=(r.get("country_code", "") or "").upper(),
            match_confidence=float(rank.get("confidence") or 0.0),
            match_type=r.get("result_type", "") or "",
        )

    def _get(self, url: str, params: dict) -> dict | None:
        params = {**params, "apiKey": self.api_key, "format": "json"}
        for attempt in range(3):
            try:
                resp = self._session.get(url, params=params, timeout=15)
            except requests.RequestException as exc:
                log.warning("Geoapify HTTP error (attempt %d): %s", attempt + 1, exc)
                time.sleep(1 + attempt)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                log.warning("Geoapify HTTP %d (attempt %d) — backing off", resp.status_code, attempt + 1)
                time.sleep(2 + attempt * 2)
                continue
            if not resp.ok:
                log.error("Geoapify HTTP %d: %s", resp.status_code, resp.text[:200])
                return None
            return resp.json()
        return None


class GoogleGeocoder(Geocoder):
    """Google Places via the existing PlacesAPIClient (fallback / opt-in)."""

    provider = "google"

    def __init__(self, client: PlacesAPIClient | None = None):
        self._client = client or PlacesAPIClient()  # raises if GOOGLE_MAPS_API_KEY unset

    def geocode(self, text: str) -> PlaceLookup | None:
        return self._score(self._client.find_place(text)) if text else None

    def reverse(self, lat: float, lng: float) -> PlaceLookup | None:
        return self._score(self._client.reverse_geocode(lat, lng))

    @staticmethod
    def _score(result: PlaceLookup | None) -> PlaceLookup | None:
        # Google doesn't return a 0..1 score; treat a found place as
        # high-confidence so it isn't gated out downstream.
        if result is not None:
            result.match_confidence = 0.7
            result.match_type = "poi" if result.place_name else "area"
        return result


class HybridGeocoder(Geocoder):
    """Geoapify first, Google as a fallback for misses."""

    provider = "hybrid"

    def __init__(self):
        self._primary = GeoapifyGeocoder()
        try:
            self._fallback: Geocoder | None = GoogleGeocoder()
        except Exception as exc:  # GOOGLE_MAPS_API_KEY missing — run primary-only
            log.warning("hybrid: Google fallback unavailable (%s)", exc)
            self._fallback = None

    def geocode(self, text: str) -> PlaceLookup | None:
        return self._primary.geocode(text) or (self._fallback.geocode(text) if self._fallback else None)

    def reverse(self, lat: float, lng: float) -> PlaceLookup | None:
        return self._primary.reverse(lat, lng) or (self._fallback.reverse(lat, lng) if self._fallback else None)


def get_geocoder(provider: str | None = None) -> Geocoder:
    """Build the configured geocoder. Raises GeocoderConfigError if misconfigured."""
    provider = (provider or os.environ.get("GEOCODER_PROVIDER", "geoapify")).strip().lower()
    if provider == "geoapify":
        return GeoapifyGeocoder()
    if provider == "google":
        try:
            return GoogleGeocoder()
        except RuntimeError as exc:
            raise GeocoderConfigError(str(exc)) from exc
    if provider == "hybrid":
        return HybridGeocoder()
    raise GeocoderConfigError(f"unknown GEOCODER_PROVIDER: {provider!r}")


# Column order shared by the resolved-row insert and the negative-cache sentinel.
_CATALOG_COLUMNS = [
    "place_id", "lookup_key", "place_name", "place_types", "primary_type",
    "lat", "lng", "formatted_address", "neighborhood", "sublocality",
    "locality", "admin_area_1", "country", "country_code",
    "match_confidence", "match_type",
]


def _catalog_insert(ch, row: dict) -> None:
    """Insert one catalog row using the SHARED client — never open a new
    connection per call (a backfill of thousands would exhaust file
    descriptors: clickhouse_connect.get_client() builds a fresh pool each time)."""
    ch.insert(
        "maps_place_catalog",
        [[row.get(c) for c in _CATALOG_COLUMNS]],
        column_names=_CATALOG_COLUMNS,
        database="bronze",
    )


def _unresolved_row(place_id: str, lookup_key: str) -> dict:
    """An 'unresolved' sentinel — negative cache so this key leaves the worklist."""
    return {
        "place_id": place_id, "lookup_key": lookup_key, "place_name": "",
        "place_types": [], "primary_type": "", "lat": 0.0, "lng": 0.0,
        "formatted_address": "", "neighborhood": "", "sublocality": "",
        "locality": "", "admin_area_1": "", "country": "", "country_code": "",
        "match_confidence": 0.0, "match_type": "unresolved",
    }


def get_or_lookup(*, place_id="", text="", lat=0.0, lng=0.0, geocoder=None, ch=None):
    """Resolve a place, hitting bronze.maps_place_catalog first.

    Pass a shared `ch` client when looping (the enrichment asset does): every
    cache check + insert reuses it instead of opening a new ClickHouse
    connection per call, which otherwise exhausts file descriptors over a
    backfill. Misses and non-geocodable junk are negative-cached ('unresolved'
    sentinel) so the worklist converges. Returns the PlaceLookup, else None.
    """
    from ingestion._shared.clickhouse import get_client as _ch_client

    if not place_id and not text and not (lat and lng):
        return None

    if ch is None:
        ch = _ch_client()

    # Cache check by place_id (the geo_key) — most specific.
    if place_id:
        rows = ch.query(
            "SELECT place_id, place_name, place_types, primary_type, lat, lng, "
            "formatted_address, neighborhood, sublocality, locality, admin_area_1, "
            "country, country_code, match_confidence, match_type "
            "FROM bronze.maps_place_catalog FINAL WHERE place_id = %(pid)s LIMIT 1",
            parameters={"pid": place_id},
        ).result_rows
        if rows:
            r = rows[0]
            if (r[14] or "") == "unresolved":
                return None  # cached negative — don't re-fetch
            return PlaceLookup(
                place_id=r[0], place_name=r[1], place_types=list(r[2] or []), primary_type=r[3],
                lat=float(r[4]), lng=float(r[5]), formatted_address=r[6], neighborhood=r[7],
                sublocality=r[8], locality=r[9], admin_area_1=r[10], country=r[11],
                country_code=r[12], match_confidence=float(r[13] or 0.0), match_type=r[14] or "",
            )

    geocoder = geocoder or get_geocoder()
    canonical_id = place_id or text or f"{lat},{lng}"
    lookup_key = text or f"{lat},{lng}"

    # Skip + negative-cache obvious non-places (unless we have real coords).
    if text and not (lat and lng) and not is_geocodable_text(text):
        _catalog_insert(ch, _unresolved_row(canonical_id, lookup_key))
        return None

    result = geocoder.geocode(text) if text else geocoder.reverse(lat, lng)
    if result is None or (result.lat == 0 and result.lng == 0):
        _catalog_insert(ch, _unresolved_row(canonical_id, lookup_key))
        return None

    _catalog_insert(ch, {
        "place_id": canonical_id, "lookup_key": lookup_key,
        "place_name": result.place_name, "place_types": result.place_types,
        "primary_type": result.primary_type, "lat": result.lat, "lng": result.lng,
        "formatted_address": result.formatted_address, "neighborhood": result.neighborhood,
        "sublocality": result.sublocality, "locality": result.locality,
        "admin_area_1": result.admin_area_1, "country": result.country,
        "country_code": result.country_code,
        "match_confidence": result.match_confidence, "match_type": result.match_type,
    })
    return result
