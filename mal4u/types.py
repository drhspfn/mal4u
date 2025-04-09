from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator, ValidationError
from typing import Optional
from mal4u import constants


class imageUrlMixin(BaseModel):
    image_url: Optional[HttpUrl] = None
    
    @field_validator("image_url", mode="before")
    def validate_image_url(cls, v) -> HttpUrl:
        if isinstance(v, HttpUrl): return v
        elif isinstance(v, str):
            if v == "": return None
            if v.startswith('/'):
                v = constants.MAL_DOMAIN + v
            
            return HttpUrl(v)
        else:
            raise ValueError()

class urlMixin(BaseModel):
    url: HttpUrl
    
    @field_validator("url", mode="before")
    def validate_url(cls, v) -> HttpUrl:
        if isinstance(v, HttpUrl): return v
        elif isinstance(v, str):
            if v.startswith('/'):
                v = constants.MAL_DOMAIN + v
            
            return HttpUrl(v)
        else:
            raise ValueError()

class LinkItem(urlMixin):
    """Represents an item with a name, URL, and MAL ID (e.g., genre, author)."""
    mal_id: int
    name: str
    type: Optional[Literal['season', 'producer']] = None 
    

class RelatedItem(urlMixin):
    """Represents a related anime/manga entry."""
    mal_id: int
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
    

class BaseSearchResult(BaseModel):
    mal_id: Optional[int] 
    title: str
    url: str
    image_url: Optional[str] = None
    synopsis: Optional[str] = None
    score: Optional[float] = None
    type: Optional[str] = None 
     

# -- New base model for parts --
class BaseDetails(urlMixin, imageUrlMixin):
    """Base model for common fields in Anime/Manga details."""
    mal_id: int
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