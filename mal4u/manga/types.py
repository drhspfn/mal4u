from typing import Optional
from pydantic import Field
from typing import Optional, List
from datetime import date
from .mixins import mangaStatusMixin, mangaTypeMixin
from mal4u.types import BaseDetails, BaseSearchResult, LinkItem
from mal4u.mixins import imageUrlMixin, malIdMixin, urlMixin




class MangaSearchResult(BaseSearchResult, mangaTypeMixin):
    """Data structure for manga search result."""
    chapters: Optional[int] = None
    volumes: Optional[int] = None
    


# --- Main Manga Details Model ---

class MangaDetails(BaseDetails, mangaStatusMixin, mangaTypeMixin):
    """Detailed information about a specific manga."""
    volumes: Optional[int] = None
    chapters: Optional[int] = None
    published_from: Optional[date] = None
    published_to: Optional[date] = None
    serialization: Optional[LinkItem] = None
    authors: List[LinkItem] = Field(default_factory=list)



class TopMangaItem(malIdMixin, urlMixin, imageUrlMixin, mangaTypeMixin):
    """Represents an item in the MAL Top Manga list."""
    rank: int
    title: str
    score: Optional[float] = None
    volumes: Optional[int] = None
    published_on: Optional[str] = None 
    members: Optional[int] = None
