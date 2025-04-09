from datetime import date
import re
from typing import List, Optional
from urllib.parse import urlencode
import aiohttp
import logging

from mal4u.details_base import BaseDetailsParser
from mal4u.types import LinkItem
from ..search_base import BaseSearchParser
from .. import constants
from .types import AnimeDetails, AnimeSearchResult
from . import constants as animeConstants


logger = logging.getLogger(__name__)

class MALAnimeParser(BaseSearchParser, BaseDetailsParser):
    def __init__(self, session: aiohttp.ClientSession):
        super().__init__(session)
        logger.info("Anime parser initialized")
        
    def _build_anime_search_url(
        self,
        query: str,
        anime_type: Optional[animeConstants.AnimeType] = None,
        anime_status: Optional[animeConstants.AnimeStatus] = None,
        rated: Optional[animeConstants.AnimeRated] = None,
        score: Optional[int] = None,
        producer: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_genres: Optional[List[int]] = None,
        exclude_genres: Optional[List[int]] = None,
    ) -> str:
        if not query or not query.strip():
             raise ValueError("Search query cannot be empty.")

        query_params = {"q": query.replace(" ", "+")} 

        if anime_type: query_params['type'] = anime_type.value
        if anime_status: query_params['status'] = anime_status.value
        if rated: query_params['p'] = rated.value
        if score: query_params['score'] = score
        if producer: query_params['p'] = producer
        
        if start_date:
            query_params.update({'sd': start_date.day, 'sm': start_date.month, 'sy': start_date.year})
        if end_date:
            query_params.update({'ed': end_date.day, 'em': end_date.month, 'ey': end_date.year})

        genre_pairs = []

        if include_genres:
            genre_pairs += [("genre[]", genre_id) for genre_id in include_genres]
        if exclude_genres:
            genre_pairs += [("genre_ex[]", genre_id) for genre_id in exclude_genres]

        query_list = list(query_params.items()) + genre_pairs

        return f"{constants.ANIME_URL}?{urlencode(query_list)}"
    
    
    async def get(self, anime_id: int) -> Optional[AnimeDetails]:
        """
        Fetches and parses the details page for a specific anime ID.
        """
        if not anime_id or anime_id <= 0:
            logger.error("Invalid anime ID provided.")
            return None

        details_url = constants.ANIME_DETAILS_URL.format(anime_id=anime_id)
        logger.info(f"Fetching anime details for ID {anime_id} from {details_url}")

        soup = await self._get_soup(details_url)
        if not soup:
            logger.error(f"Failed to fetch or parse HTML for anime ID {anime_id} from {details_url}")
            return None

        logger.info(f"Successfully fetched HTML for anime ID {anime_id}. Starting parsing.")
        try:
            parsed_details = await self._parse_details_page(
                soup=soup,
                item_id=anime_id,
                item_url=details_url,
                item_type="anime",
                details_model=AnimeDetails 
            )
            return parsed_details
        except Exception as e:
            logger.exception(f"Top-level exception during parsing details for anime ID {anime_id}: {e}")
            return None
    
    async def search(
        self,
        query: str,
        limit: int = 5,
        anime_type: Optional[animeConstants.AnimeType] = None,
        anime_status: Optional[animeConstants.AnimeStatus] = None,
        rated: Optional[animeConstants.AnimeRated] = None,
        score: Optional[int] = None,
        producer: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_genres: Optional[List[int]] = None,
        exclude_genres: Optional[List[int]] = None,
    ) -> List[AnimeSearchResult]:
        """Searches for anime on MyAnimeList."""
        if not query:
            logger.warning("Search query is empty, returning empty list.")
            return []
        if limit <= 0:
            logger.warning("Search limit is zero or negative, returning empty list.")
            return []


        try:
            search_url = self._build_anime_search_url(
                query=query,
                anime_type=anime_type,
                anime_status=anime_status,
                rated=rated,
                score=score,
                producer=producer,
                start_date=start_date,
                end_date=end_date,
                include_genres=include_genres,
                exclude_genres=exclude_genres,
            )
            logger.debug(f"Searching anime using URL: {search_url}")
        except ValueError as e:
             logger.error(f"Failed to build anime search URL: {e}")
             return []

        soup = await self._get_soup(search_url)
        if not soup:
            logger.warning(f"Failed to retrieve or parse search page content for query '{query}' from {search_url}")
            return []

        try:
            parsed_results = await self._parse_search_results_page(
                soup=soup,
                limit=limit,
                result_model=AnimeSearchResult, 
                id_pattern=self.ANIME_ID_PATTERN 
            )
            return parsed_results
        except Exception as e:
            logger.exception(f"An unexpected error occurred during parsing anime search results for query '{query}': {e}")
            return []
        
    async def get_studios(self) -> List[LinkItem]:
        target_url = constants.ANIME_URL
        logger.info(f"Fetching studios from {target_url}")
        
        soup = await self._get_soup(target_url)
        if not soup:
            logger.error(f"Failed to fetch or parse HTML from {target_url} for studios.")
            return []
        
        search_container = self._safe_find(soup, 'div', class_='anime-manga-search')
        if not search_container:
            logger.warning(f"Could not find the main 'anime-manga-search' container on {target_url}.")
            return []

        studio_id_pattern = re.compile(r"/anime/producer/(\d+)/")
        studios_list = await self._parse_link_section(
            container=search_container,
            header_text_exact="Studios",
            id_pattern=studio_id_pattern,
            category_name_for_logging="Studios"
        )
        
        if not studios_list:
            logger.warning(f"No studios were successfully parsed from {target_url}.")
        else:
            logger.info(f"Successfully parsed {len(studios_list)} themes from {target_url}.")

        return studios_list