from typing import Optional
from pydantic import BaseModel, HttpUrl, field_validator, ValidationError
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
    

class RelatedItem(urlMixin):
    """Represents a related anime/manga entry."""
    mal_id: int
    type: str # e.g., "Manga", "Anime", "Light Novel"
    name: str


class CharacterItem(urlMixin, imageUrlMixin):
    """Represents a character listed on the manga page."""
    mal_id: int
    name: str
    role: str # e.g., "Main", "Supporting"
    

class ExternalLink(urlMixin):
    """Represents an external link (e.g., Wikipedia, Official Site)."""
    name: str

    