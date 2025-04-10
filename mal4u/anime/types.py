from typing import Optional, Set
from pydantic import Field
from typing import Optional, List
from datetime import date, time
from .mixins import animeRatedMixin, animeStatusMixin, animeTypeMixin
from mal4u.types import AnimeBroadcast, BaseDetails, BaseSearchResult, ExternalLink, LinkItem
from mal4u.mixins import imageUrlMixin, malIdMixin, urlMixin

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


class SeasonalAnimeItem(malIdMixin, urlMixin, imageUrlMixin, animeTypeMixin):
    """Represents a single anime entry on a seasonal page."""
    title: str = Field(...)
    synopsis: Optional[str] = Field(None)
    start_date: Optional[date] = Field(None)
    episodes: Optional[int] = Field(None)
    duration_min_per_ep: Optional[int] = Field(None)
    genres: List[LinkItem] = Field(default_factory=list)
    themes: List[LinkItem] = Field(default_factory=list)
    demographics: List[LinkItem] = Field(default_factory=list)
    all_genre_ids: Set[int] = Field(default_factory=set)
    studios: List[LinkItem] = Field(default_factory=list)
    source: Optional[str] = Field(None)
    score: Optional[float] = Field(None)
    members: Optional[int] = Field(None)
    season_year: Optional[int] = Field(None)
    season_name: Optional[str] = Field(None)
    continuing: bool = Field(False)
    
class ScheduleAnimeItem(SeasonalAnimeItem):
    """Extends SeasonalAnimeItem with schedule-specific info."""
    airing_time_jst: Optional[time] = Field(None)
    next_episode_num: Optional[int] = Field(None)
    # Remove fields irrelevant to the schedule, if necessary
    season_year: Optional[int] = None
    season_name: Optional[str] = None
    continuing: Optional[bool] = None # Less relevant here