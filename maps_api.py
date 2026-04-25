"""
Google Maps API for delivery distance and time calculation.
Provides routing-based distance and estimated delivery time, with a fallback to Euclidean distance.
Includes production-ready features like caching, rate limiting, and timeout handling.

Design Philosophy:
- System reduces expensive external operations (API calls) via heavy caching and geographic pruning.
- Uses Approximation -> Refinement: Fast math is used first, real-world API is only called on the very best candidates.
- Optimizes both raw performance (latency) and User Experience (UX) reliability.
"""

import math
import os
import requests
import logging
import time
from typing import Tuple, Dict

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
RATE_LIMIT_DELAY = 0.05  # 50ms delay between API calls to prevent rate limiting issues
CACHE_TTL = 600  # 10 minutes in seconds
MAX_CACHE_SIZE = 10000  # Prevent memory bloat

# Caching layer
# Key: (lat1, lon1, lat2, lon2) -> Value: (distance_km, time_hours, timestamp)
_maps_cache: Dict[Tuple[float, float, float, float], Tuple[float, float, float]] = {}

# Rate limiting state
_last_api_call_time: float = 0.0


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate Euclidean distance between two geographic coordinates.
    
    Why Fallback is needed: 
    Real-world systems cannot rely 100% on external APIs. Network issues, quota limits,
    or invalid keys can cause API failures. A local fallback ensures the system remains
    operational and reliable even when the external service is down.
    """
    lat_diff = lat2 - lat1
    lon_diff = lon2 - lon1
    distance = math.sqrt(lat_diff ** 2 + lon_diff ** 2) * 111  # ~111 km per degree
    return round(distance, 2)


def get_google_maps_data(lat1: float, lon1: float, lat2: float, lon2: float, retries: int = 2) -> Tuple[float, float]:
    """
    Call Google Maps Distance Matrix API.
    
    Why Rate Limiting is implemented:
    Cloud providers like Google Maps enforce strict queries-per-second (QPS) limits.
    Bursting too many requests concurrently can lead to HTTP 429 Too Many Requests errors
    and temporary bans. Throttling ensures smooth, continuous operation.
    """
    global _last_api_call_time

    if not GOOGLE_MAPS_API_KEY:
        raise ValueError("Google Maps API Key not set.")

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{lat1},{lon1}",
        "destinations": f"{lat2},{lon2}",
        "key": GOOGLE_MAPS_API_KEY,
    }

    last_exception = None
    for attempt in range(retries):
        # Rate Limiting: ensure minimum delay between API calls
        current_time = time.time()
        time_since_last_call = current_time - _last_api_call_time
        if time_since_last_call < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - time_since_last_call)
        
        # Update last call time after potential sleep
        _last_api_call_time = time.time()

        try:
            # Request Timeout: Prevent system hanging due to slow API responses
            response = requests.get(url, params=params, timeout=2.0)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK":
                raise ValueError(f"Google Maps API error: {data.get('status')}")

            # Parse response
            element = data["rows"][0]["elements"][0]
            if element.get("status") != "OK":
                raise ValueError(f"Route error: {element.get('status')}")

            # Distance in meters -> convert to km
            distance_km = element["distance"]["value"] / 1000.0
            
            # Duration in seconds -> convert to hours
            duration_hours = element["duration"]["value"] / 3600.0

            return round(distance_km, 2), round(duration_hours, 2)

        except (requests.exceptions.Timeout, requests.exceptions.RequestException, ValueError) as e:
            last_exception = e
            if attempt == retries - 1:
                break
            logger.warning(f"Google Maps API attempt {attempt+1} failed. Retrying...")
            time.sleep(0.1) # Small backoff before retry
            
    raise last_exception if last_exception else ValueError("API failed after retries")


def simulate_maps_api(requester_hospital, target_hospital) -> Tuple[float, float]:
    """
    Get actual distance and delivery time using Google Maps API.
    Uses caching to avoid redundant API calls and falls back to simulation on errors.
    
    Why Caching is used:
    In routing systems, many requests are often repeated (e.g., Hospital A to Hospital B).
    Caching these results dramatically reduces API costs, improves latency from hundreds of 
    milliseconds to sub-milliseconds, and lowers the risk of hitting rate limits.
    
    Args:
        requester_hospital: Hospital object requesting the item
        target_hospital: Hospital object that has the item
    
    Returns:
        Tuple[distance_km, delivery_time_hours]
    """
    # Round coordinates to 4 decimal places (approx. 11 meters) to improve cache hit rates
    # Avoid float precision cache issues (11.111100001 != 11.111100002)
    lat1 = round(requester_hospital.lat, 4)
    lon1 = round(requester_hospital.lon, 4)
    lat2 = round(target_hospital.lat, 4)
    lon2 = round(target_hospital.lon, 4)
    
    cache_key = (lat1, lon1, lat2, lon2)
    current_time = time.time()

    # STEP 1: Check cache (with TTL)
    if cache_key in _maps_cache:
        cached_dist, cached_time, timestamp = _maps_cache[cache_key]
        if current_time - timestamp < CACHE_TTL:
            logger.debug("Cache hit for coordinates %s to %s", (lat1, lon1), (lat2, lon2))
            return cached_dist, cached_time
        else:
            logger.debug("Cache expired for coordinates %s to %s", (lat1, lon1), (lat2, lon2))

    # STEP 2 & 3: Try API (if key exists), fallback on failure
    distance, delivery_time = None, None
    try:
        if GOOGLE_MAPS_API_KEY:
            distance, delivery_time = get_google_maps_data(lat1, lon1, lat2, lon2)
            logger.debug("Successfully fetched data from Google Maps API.")
    except Exception as e:
        logger.warning("Google Maps API failed: %s. Falling back to local calculation.", str(e))

    # Fallback if API was not called or failed
    if distance is None or delivery_time is None:
        distance = calculate_distance(lat1, lon1, lat2, lon2)
        # Assume constant transport speed: 40 km/h
        speed_kmh = 40.0
        delivery_time = round(distance / speed_kmh, 2)

    # Cache Memory Control: Clear cache if it exceeds max size to prevent unbounded growth
    if len(_maps_cache) >= MAX_CACHE_SIZE:
        logger.warning(f"Cache size exceeded {MAX_CACHE_SIZE}. Clearing cache to prevent memory bloat.")
        _maps_cache.clear()

    # STEP 4: Store result in cache
    _maps_cache[cache_key] = (distance, delivery_time, current_time)

    # STEP 5: Return result
    return distance, delivery_time
