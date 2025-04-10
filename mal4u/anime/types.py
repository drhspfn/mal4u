from typing import Optional
from pydantic import Field, field_validator
from typing import Optional, List
from datetime import date
from .mixins import animeRatedMixin, animeStatusMixin, animeTypeMixin
from mal4u.types import AnimeBroadcast, BaseDetails, BaseSearchResult, ExternalLink, LinkItem
from mal4u.mixins import imageUrlMixin, malIdMixin, urlMixin
from .constants import AnimeType, AnimeStatus, AnimeRated

class AnimeSearchResult(BaseSearchResult, animeTypeMixin):
    """Represents a single anime item in MAL search results."""
    episodes: Optional[int] = None
    members: Optional[int] = None
    

class AnimeDetails(BaseDetails, animeTypeMixin, animeRatedMixin, animeStatusMixin):
    """Detailed information about a specific anime."""
    episodes: Optional[int] = None
    aired_from: Optional[date] = None
    aired_to: Optional[date] = None
    premiered: Optional[LinkItem] = None # (/anime/season/YYYY/season)
    broadcast: Optional[AnimeBroadcast] = None
    producers: List[LinkItem] = Field(default_factory=list)
    licensors: List[LinkItem] = Field(default_factory=list)
    studios: List[LinkItem] = Field(default_factory=list)
    source: Optional[str] = None # Manga, Original, Light Novel, etc.
    duration: Optional[str] = None # e.g., "24 min. per ep."
    opening_themes: List[str] = Field(default_factory=list) 
    ending_themes: List[str] = Field(default_factory=list) 
    streaming_platforms: List[ExternalLink] = Field(default_factory=list)
    
        
class TopAnimeItem(malIdMixin, urlMixin, imageUrlMixin, animeTypeMixin):
    """Represents an item in the MAL Top Anime list."""
    rank: int
    title: str
    score: Optional[float] = None
    episodes: Optional[int] = None
    aired_on: Optional[str] = None # String representation like "Oct 2006 - Jul 2007"
    members: Optional[int] = None
