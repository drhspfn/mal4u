from typing import Optional
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
from mal4u.types import AnimeBroadcast, BaseDetails, BaseSearchResult, ExternalLink, LinkItem


class AnimeSearchResult(BaseSearchResult):
    """Represents a single anime item in MAL search results."""
    episodes: Optional[int] = None
    members: Optional[int] = None
    

class AnimeDetails(BaseDetails):
    """Detailed information about a specific anime."""
    episodes: Optional[int] = None
    aired_from: Optional[date] = None
    aired_to: Optional[date] = None
    premiered: Optional[LinkItem] = None # Ссылка на сезон (/anime/season/YYYY/season)
    broadcast: Optional[AnimeBroadcast] = None
    producers: List[LinkItem] = Field(default_factory=list)
    licensors: List[LinkItem] = Field(default_factory=list)
    studios: List[LinkItem] = Field(default_factory=list)
    source: Optional[str] = None # Manga, Original, Light Novel, etc.
    duration: Optional[str] = None # e.g., "24 min. per ep."
    rating: Optional[str] = None # e.g., "PG-13 - Teens 13 or older"
    opening_themes: List[str] = Field(default_factory=list) 
    ending_themes: List[str] = Field(default_factory=list) 
    streaming_platforms: List[ExternalLink] = Field(default_factory=list)