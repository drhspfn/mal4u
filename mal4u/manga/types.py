from typing import Optional
from pydantic import Field, field_validator
from typing import Optional, List
from datetime import date
from mal4u.types import BaseDetails, BaseSearchResult, LinkItem
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

'''class MangaDetails(urlMixin, imageUrlMixin):
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
        return None # Or raise ValueError'''