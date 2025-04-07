from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import date
import re
from mal4u.types import LinkItem, RelatedItem, ExternalLink, CharacterItem, imageUrlMixin, urlMixin

@dataclass
class MangaSearchResult:
    """Структура данных для результата поиска манги."""
    mal_id: Optional[int] 
    title: str
    url: str
    image_url: Optional[str] = None
    synopsis: Optional[str] = None
    manga_type: Optional[str] = None # Manga, Manhwa, Manhua, Novel, One-shot
    chapters: Optional[int] = None
    volumes: Optional[int] = None
    score: Optional[float] = None


# --- Main Manga Details Model ---

class MangaDetails(urlMixin, imageUrlMixin):
    """Detailed information about a specific manga."""
    mal_id: int
    title: str

    # Titles
    title_english: Optional[str] = None
    title_japanese: Optional[str] = None
    title_synonyms: List[str] = Field(default_factory=list)

    # Core Info
    type: Optional[str] = None
    volumes: Optional[int] = None
    chapters: Optional[int] = None
    status: Optional[str] = None # e.g., "Publishing", "Finished", "On Hiatus"
    published_from: Optional[date] = None
    published_to: Optional[date] = None # Can be None if ongoing or unknown

    # Taxonomies
    genres: List[LinkItem] = Field(default_factory=list)
    themes: List[LinkItem] = Field(default_factory=list)
    demographics: List[LinkItem] = Field(default_factory=list)

    # Credits
    authors: List[LinkItem] = Field(default_factory=list)
    serialization: Optional[LinkItem] = None

    # Statistics
    score: Optional[float] = None
    scored_by: Optional[int] = None
    rank: Optional[int] = None
    popularity: Optional[int] = None
    members: Optional[int] = None
    favorites: Optional[int] = None

    # Descriptions
    synopsis: Optional[str] = None
    background: Optional[str] = None

    # Connections
    related: Dict[str, List[RelatedItem]] = Field(default_factory=dict) # Keyed by relation type (e.g., "Adaptation")
    characters: List[CharacterItem] = Field(default_factory=list)
    external_links: List[ExternalLink] = Field(default_factory=list)
    official_site: Optional[HttpUrl] = None # Extracted from external_links for convenience

    @field_validator('synopsis', 'background', mode='before')
    @classmethod
    def clean_text(cls, value: Optional[str]) -> Optional[str]:
        """Basic cleaning for text fields."""
        if value:
            # Remove potential MAL Rewrite/Source tags if desired, or just strip
            # Example: Remove "[Written by MAL Rewrite]"
            value = re.sub(r'\[Written by MAL Rewrite\]', '', value, flags=re.IGNORECASE).strip()
            # Add more cleaning rules if needed
            return value.strip() if value else None
        return None

    @field_validator('published_from', 'published_to', mode='before')
    @classmethod
    def parse_date_flexible(cls, value: Any) -> Optional[date]:
        """Handle potential date parsing if needed (though parser should handle it)."""
        if isinstance(value, date):
            return value
        # Add specific parsing logic here if the BaseParser helper isn't used upstream
        return None # Or raise ValueError