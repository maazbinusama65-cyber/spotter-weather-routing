from functools import lru_cache

from django.conf import settings
from django.core.cache import cache

from .cached import CachedRouting, CachedWeather
from .open_meteo import OpenMeteoClient
from .ors import OrsClient
from .types import RoutingProvider, WeatherProvider


@lru_cache(maxsize=1)
def get_providers() -> tuple[RoutingProvider, WeatherProvider]:
    """The real providers, wrapped in caches. Built once per process."""
    timeout = settings.PROVIDER_TIMEOUT_SECONDS
    routing = CachedRouting(OrsClient(settings.ORS_API_KEY, timeout), cache)
    weather = CachedWeather(OpenMeteoClient(timeout), cache)
    return routing, weather
