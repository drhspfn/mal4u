from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List

from mal4u.mixins import imageUrlMixin, malIdMixin, urlMixin
from mal4u.types import LinkItem

class RelatedMediaItem(LinkItem):
    """Represents an anime or manga appearance for a character, including their role."""
    role: str # e.g., Main, Supporting

class CharacterSearchResult(BaseModel):
    """Represents a character found via search or in top lists."""
    mal_id: int
    url: Optional[HttpUrl] = None
    image_url: Optional[HttpUrl] = None
    name: str
    nickname: Optional[str] = None 
    japanese_name: Optional[str] = None 
    favorites: Optional[int] = None 
    rank: Optional[int] = None
    animeography: List[RelatedMediaItem] = Field(default_factory=list)
    mangaography: List[RelatedMediaItem] = Field(default_factory=list)
    


class VoiceActorItem(LinkItem, imageUrlMixin):
    """Represents a voice actor for a character."""
    language: str
    image_url: Optional[HttpUrl] = None
    
class CharacterDetails(malIdMixin, urlMixin, imageUrlMixin):
    """Detailed information about a specific MAL character."""
    name: str
    name_alt: Optional[str] = None # For epithets like "Frieren the Slayer"
    name_japanese: Optional[str] = None
    favorites: Optional[int] = None
    about: Optional[str] = None
    animeography: List[RelatedMediaItem] = Field(default_factory=list)
    mangaography: List[RelatedMediaItem] = Field(default_factory=list)
    voice_actors: List[VoiceActorItem] = Field(default_factory=list)