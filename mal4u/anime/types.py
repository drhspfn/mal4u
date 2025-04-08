from typing import Optional
from mal4u.types import BaseSearchResult


class AnimeSearchResult(BaseSearchResult):
    """Represents a single anime item in MAL search results."""
    episodes: Optional[int] = None
    members: Optional[int] = None