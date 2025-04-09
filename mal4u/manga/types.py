from typing import Optional
from pydantic import Field, field_validator
from typing import Optional, List
from datetime import date
from mal4u.types import BaseDetails, BaseSearchResult, LinkItem, imageUrlMixin, malIdMixin, urlMixin
from .constants import MangaType, MangaStatus


class MangaSearchResult(BaseSearchResult):
    """Data structure for manga search result."""
    chapters: Optional[int] = None
    volumes: Optional[int] = None


# --- Main Manga Details Model ---

class MangaDetails(BaseDetails):
    """Detailed information about a specific manga."""
    volumes: Optional[int] = None
    chapters: Optional[int] = None
    published_from: Optional[date] = None
    published_to: Optional[date] = None
    serialization: Optional[LinkItem] = None
    authors: List[LinkItem] = Field(default_factory=list)
    type: Optional[MangaType] = None 
    status: Optional[MangaStatus] = None 
    
    @field_validator('type', mode='before')
    def validate_type(cls, v:str) -> MangaType:
        if isinstance(v, MangaType): return v
        elif isinstance(v, str): return MangaType.from_str(v)
        elif isinstance(v, int): return MangaType(v)
        else: return None
        
    @field_validator('status', mode='before')
    def validate_status(cls, v:str) -> MangaStatus:
        if isinstance(v, MangaStatus): return v
        elif isinstance(v, str): return MangaStatus.from_str(v)
        elif isinstance(v, int): return MangaStatus(v)
        else: return None


class TopMangaItem(malIdMixin, urlMixin, imageUrlMixin):
    """Represents an item in the MAL Top Manga list."""
    rank: int
    title: str
    score: Optional[float] = None
    manga_type: Optional[MangaType] = None 
    volumes: Optional[int] = None
    published_on: Optional[str] = None 
    members: Optional[int] = None
    
    @field_validator('manga_type', mode='before')
    def validate_manga_type(cls, v:str) -> MangaType:
        if isinstance(v, MangaType): return v
        elif isinstance(v, str): return MangaType.from_str(v)
        elif isinstance(v, int): return MangaType(v)
        else: return None