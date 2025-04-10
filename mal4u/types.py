from typing import Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from mal4u.constants import LinkItemType
from mal4u.mixins import imageUrlMixin, malIdMixin, optionalMalIdMixin, urlMixin


class LinkItem(malIdMixin, urlMixin):
    """Represents an item with a name, URL, and MAL ID (e.g., genre, author)."""
    name: str
    type: Optional[LinkItemType] = None 
    

class RelatedItem(malIdMixin, urlMixin):
    """Represents a related anime/manga entry."""
    type: str # e.g., "Manga", "Anime", "Light Novel"
    name: str


class CharacterItem(LinkItem, imageUrlMixin):
    """Represents a character listed on the manga page."""
    role: str

class ExternalLink(urlMixin):
    """Represents an external link (e.g., Wikipedia, Official Site)."""
    name: str

class AnimeBroadcast(BaseModel):
    """Represents broadcast information."""
    day: Optional[str] = None
    time: Optional[str] = None
    timezone: Optional[str] = None
    string: Optional[str] = None 
    

class BaseSearchResult(optionalMalIdMixin, urlMixin, imageUrlMixin):
    title: str
    synopsis: Optional[str] = None
    score: Optional[float] = None
    
     

# -- New base model for parts --
class BaseDetails(malIdMixin,urlMixin, imageUrlMixin):
    """Base model for common fields in Anime/Manga details."""
    title: str
    title_english: Optional[str] = None
    title_japanese: Optional[str] = None
    title_synonyms: List[str] = Field(default_factory=list)
    score: Optional[float] = None
    scored_by: Optional[int] = None
    rank: Optional[int] = None
    popularity: Optional[int] = None
    members: Optional[int] = None
    favorites: Optional[int] = None
    synopsis: Optional[str] = None
    background: Optional[str] = None
    genres: List[LinkItem] = Field(default_factory=list)
    themes: List[LinkItem] = Field(default_factory=list)
    demographics: List[LinkItem] = Field(default_factory=list)
    related: Dict[str, List[RelatedItem]] = Field(default_factory=dict)
    characters: List[CharacterItem] = Field(default_factory=list)
    external_links: List[ExternalLink] = Field(default_factory=list)
    official_site: Optional[HttpUrl] = None 