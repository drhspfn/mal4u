import asyncio
from datetime import date
from math import ceil
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
import aiohttp
import logging
import re
from pydantic import ValidationError
from mal4u.details_base import BaseDetailsParser
from mal4u.search_base import BaseSearchParser
from .  import constants as mangaConstants
from mal4u.types import LinkItem
from .types import MangaDetails, MangaSearchResult, TopMangaItem 
from .. import constants

logger = logging.getLogger(__name__)

class MALMangaParser(BaseSearchParser, BaseDetailsParser):
    """A parser to search and retrieve information about manga from MyAnimeList."""

    def __init__(self, session: aiohttp.ClientSession):
        super().__init__(session)
        logger.info("Manga parser initialized")


    async def get(self, manga_id: int) -> Optional[MangaDetails]:
        """
        Fetches and parses the details page for a specific manga ID.
        """
        if not manga_id or manga_id <= 0:
            logger.error("Invalid manga ID provided.")
            return None

        details_url = constants.MANGA_DETAILS_URL.format(manga_id=manga_id)
        logger.info(f"Fetching manga details for ID {manga_id} from {details_url}")

        soup = await self._get_soup(details_url)
        if not soup:
            logger.error(f"Failed to fetch or parse HTML for manga ID {manga_id} from {details_url}")
            return None

        logger.info(f"Successfully fetched HTML for manga ID {manga_id}. Starting parsing.")
        try:
            parsed_details = await self._parse_details_page(
                soup=soup,
                item_id=manga_id,
                item_url=details_url,
                item_type="manga",    
                details_model=MangaDetails
            )
            return parsed_details
        except Exception as e:
            logger.exception(f"Top-level exception during parsing details for manga ID {manga_id}: {e}")
            return None


    

    # ---
    
    def _build_manga_search_url(
        self,
        query: str, 
        manga_type:Optional[mangaConstants.MangaType] = None,
        manga_status:Optional[mangaConstants.MangaStatus] = None,
        manga_magazine:Optional[int] = None,
        manga_score:Optional[int] = None,
        include_genres: Optional[List[int]] = None,  
        exclude_genres: Optional[List[int]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ):
        if not query or query == "": raise ValueError("The required parameter `query` must be passed.")
        query_params = {"q": query.replace(" ", "+")}
        if manga_type:
            query_params['type'] = manga_type.value
        if manga_status:
            query_params['status'] = manga_status.value
        if manga_magazine:
            query_params['mid'] = manga_magazine
        if manga_score:
            query_params['score'] = manga_score
        if start_date:
            query_params['sd'] = start_date.day 
            query_params['sy'] = start_date.year 
            query_params['sm'] = start_date.month
        if end_date:
            query_params['ed'] = end_date.day
            query_params['ey'] = end_date.year 
            query_params['em'] = end_date.month 

            
        genre_pairs = []

        if include_genres:
            genre_pairs += [("genre[]", genre_id) for genre_id in include_genres]
        if exclude_genres:
            genre_pairs += [("genre_ex[]", genre_id) for genre_id in exclude_genres]

        query_list = list(query_params.items()) + genre_pairs

        return f"{constants.MANGA_URL}?{urlencode(query_list)}"

    async def search(
        self,
        query: str,
        limit: int = 5,
        manga_type:Optional[mangaConstants.MangaType] = None,
        manga_status:Optional[mangaConstants.MangaStatus] = None,
        manga_magazine:Optional[int] = None,
        manga_score:Optional[int] = None,
        include_genres: Optional[List[int]] = None,
        exclude_genres: Optional[List[int]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[MangaSearchResult]:
        """
        Searches for manga on MyAnimeList using a query, parsing the HTML table of search results.
        """
        if not query:
            logger.warning("Search query is empty, returning empty list.")
            return []
        if limit <= 0:
            logger.warning("Search limit is zero or negative, returning empty list.")
            return []


        try:
            search_url = self._build_manga_search_url(
                query, manga_type, manga_status, manga_magazine,
                manga_score, include_genres, exclude_genres,
                start_date, end_date
            )
            logger.debug(f"Searching manga using URL: {search_url}")
        except ValueError as e:
             logger.error(f"Failed to build search URL: {e}")
             return []

        soup = await self._get_soup(search_url)
        if not soup:
            logger.warning(f"Failed to retrieve or parse search page content for query '{query}' from {search_url}")
            return []

        try:
            parsed_results = await self._parse_search_results_page(
                soup=soup,
                limit=limit,
                result_model=MangaSearchResult,
                id_pattern=self.MANGA_ID_PATTERN 
            )
            return parsed_results
        except Exception as e:
            logger.exception(f"An unexpected error occurred during parsing search results for query '{query}': {e}")
            return []
 
    # ---
    
    async def top(
        self, 
        limit: int = 50,
        top_type: Optional[constants.TopType] = None
    ) -> List[TopMangaItem]:
        """Fetches and parses the top manga list from MAL."""
        
        def parse_manga_top_info_string(info_text: str) -> Dict[str, Any]:
            """Parses the raw info string specific to top manga lists."""
            parsed_info = {"manga_type": None, "volumes": None, "published_on": None}
            # Manga (18 vols) Aug 1989 - Mar 1995
            # Novel (? vols) Aug 2006 - ?
            # One-shot (1 ch) 2005
            type_match = re.match(r"^(Manga|Novel|Light Novel|One-shot|Manhwa|Manhua|Doujinshi)\s*(?:\(([\d?]+)\s+vols?\))?\s*(?:\(([\d?]+)\s+chaps?\))?", info_text)
            if type_match:
                parsed_info["manga_type"] = type_match.group(1)

                parsed_info["volumes"] = self._parse_int(type_match.group(2).strip('?')) if type_match.group(2) else None
                parsed_info["chapters"] = self._parse_int(type_match.group(3).strip('?')) if type_match.group(3) else None

            date_match = re.search(r"(?:vols?\))?(?:\s*\(?[\d?]+\s+chaps?\)?\))?\s*([A-Za-z]{3}\s+\d{4}(?:\s+-\s+[A-Za-z]{3}\s+\d{4})?)\s*(?:[\d,]+\s+members)?", info_text)
            if date_match:
                parsed_info["published_on"] = date_match.group(1).strip()
            else:
    
                date_fallback_match = re.search(r"^(?:Manga|Novel|Light Novel|One-shot|Manhwa|Manhua|Doujinshi)\s*([A-Za-z]{3}\s+\d{4}(?:\s+-\s+[A-Za-z]{3}\s+\d{4})?|\d{4})\s*(?:[\d,]+\s+members)?", info_text)
                if date_fallback_match:
                    parsed_info["published_on"] = date_fallback_match.group(1).strip()


            return parsed_info
    
        
        if limit <= 0: return []
        type_value: Optional[str] = None
        if top_type:
            if constants.TopType.is_anime_specific(top_type):
                raise ValueError(f"Filter '{top_type.name}' is specific to anime and cannot be used for top manga.")
            type_value = top_type.value

        all_results: List[TopMangaItem] = []
        page_size = 50
        num_pages_to_fetch = ceil(limit / page_size)

        logger.info(f"Fetching top {limit} manga across {num_pages_to_fetch} page(s).")

        for page_index in range(num_pages_to_fetch):
            offset = page_index * page_size
            soup = await self._get_top_list_page("/topmanga.php", type_value, offset) 
            if not soup: break

            common_data_list = self._parse_top_list_rows(soup, mangaConstants.RE_MANGA_ID) 

            for common_data in common_data_list:
                if len(all_results) >= limit: break

                specific_info = parse_manga_top_info_string(common_data.get("raw_info_text", ""))
                item_data = {**common_data, **specific_info}

                try:
                    item_data.pop("raw_info_text", None)
                    top_item = TopMangaItem(**item_data)
                    all_results.append(top_item)
                except ValidationError as e:
                    logger.warning(f"Validation failed for top manga item Rank {common_data.get('rank')} (ID:{common_data.get('mal_id')}): {e}. Data: {item_data}")

            if len(all_results) >= limit: break
            if page_index < num_pages_to_fetch - 1: await asyncio.sleep(0.5)

        logger.info(f"Finished fetching top manga. Retrieved {len(all_results)} items.")
        return all_results[:limit]
    
    # --- Metadata, genres, themes etc.
    async def get_genres(self, include_explicit: bool = False) -> List[LinkItem]:
        """
        Fetches and parses genre links from the main MAL manga page (manga.php).

        Args:
            include_explicit: Whether to include Explicit Genres (Ecchi, Erotica, Hentai).
                            Defaults to False.

        Returns:
            A list of LinkItem objects representing the genres,
            or an empty list if fetching fails or the section is not found.
        """
        target_url = constants.MANGA_URL
        logger.info(f"Fetching genres from {target_url} (explicit={include_explicit})")

        soup = await self._get_soup(target_url)
        if not soup:
            logger.error(f"Failed to fetch or parse HTML from {target_url} for genres.")
            return []

        search_container = self._safe_find(soup, 'div', class_='anime-manga-search')
        if not search_container:
            logger.warning(f"Could not find the main 'anime-manga-search' container on {target_url}.")
            return []

        genre_id_pattern = re.compile(r"/genre/(\d+)/")
        all_genres: List[LinkItem] = []

        logger.debug("Parsing 'Genres' section...")
        genres_list = await self._parse_link_section(
            container=search_container,
            header_text_exact="Genres",
            id_pattern=genre_id_pattern,
            category_name_for_logging="Genres"
        )
        all_genres.extend(genres_list)

        if include_explicit:
            logger.debug("Parsing 'Explicit Genres' section...")
            explicit_genres_list = await self._parse_link_section(
                container=search_container,
                header_text_exact="Explicit Genres",
                id_pattern=genre_id_pattern,
                category_name_for_logging="Explicit Genres"
            )
            all_genres.extend(explicit_genres_list)

        if not all_genres:
            logger.warning(f"No genres were successfully parsed from {target_url} (check flags and HTML structure).")
        else:
            logger.info(f"Successfully parsed {len(all_genres)} genres from {target_url}.")

        return all_genres

    async def get_themes(self) -> List[LinkItem]:
        """
        Fetches and parses theme links (Isekai, School, etc.) from the main MAL manga page.

        Returns:
            A list of LinkItem objects representing the themes,
            or an empty list if fetching fails or the section is not found.
        """
        target_url = constants.MANGA_URL
        logger.info(f"Fetching themes from {target_url}")

        soup = await self._get_soup(target_url)
        if not soup:
            logger.error(f"Failed to fetch or parse HTML from {target_url} for themes.")
            return []

        search_container = self._safe_find(soup, 'div', class_='anime-manga-search')
        if not search_container:
            logger.warning(f"Could not find the main 'anime-manga-search' container on {target_url}.")
            return []

        theme_id_pattern = re.compile(r"/genre/(\d+)/")

        themes_list = await self._parse_link_section(
            container=search_container,
            header_text_exact="Themes",
            id_pattern=theme_id_pattern,
            category_name_for_logging="Themes"
        )

        if not themes_list:
            logger.warning(f"No themes were successfully parsed from {target_url}.")
        else:
            logger.info(f"Successfully parsed {len(themes_list)} themes from {target_url}.")

        return themes_list

    async def get_demographics(self) -> List[LinkItem]:
        """
        Fetches and parses demographic links (Shounen, Shoujo, etc.) from the main MAL manga page.

        Returns:
            A list of LinkItem objects representing the demographics,
            or an empty list if fetching fails or the section is not found.
        """
        target_url = constants.MANGA_URL
        logger.info(f"Fetching demographics from {target_url}")

        soup = await self._get_soup(target_url)
        if not soup:
            logger.error(f"Failed to fetch or parse HTML from {target_url} for demographics.")
            return []

        search_container = self._safe_find(soup, 'div', class_='anime-manga-search')
        if not search_container:
            logger.warning(f"Could not find the main 'anime-manga-search' container on {target_url}.")
            return []

        demographic_id_pattern = re.compile(r"/genre/(\d+)/") 

        demographics_list = await self._parse_link_section(
            container=search_container,
            header_text_exact="Demographics",
            id_pattern=demographic_id_pattern,
            category_name_for_logging="Demographics"
        )

        if not demographics_list:
            logger.warning(f"No demographics were successfully parsed from {target_url}.")
        else:
            logger.info(f"Successfully parsed {len(demographics_list)} demographics from {target_url}.")

        return demographics_list

    async def get_magazines_preview(self) -> List[LinkItem]:
        """
        Fetches and parses the preview list of magazine links from the main MAL manga page.
        Note: This is NOT the full list from the dedicated magazines page.

        Returns:
            A list of LinkItem objects representing the magazines shown in the preview,
            or an empty list if fetching fails or the section is not found.
        """
        target_url = constants.MANGA_URL
        logger.info(f"Fetching magazines preview from {target_url}")

        soup = await self._get_soup(target_url)
        if not soup:
            logger.error(f"Failed to fetch or parse HTML from {target_url} for magazines preview.")
            return []

        search_container = self._safe_find(soup, 'div', class_='anime-manga-search')
        if not search_container:
            logger.warning(f"Could not find the main 'anime-manga-search' container on {target_url}.")
            return []

        # Important: the pattern for ID logs is different!
        magazine_id_pattern = re.compile(r"/magazine/(\d+)/")

        # The title of the magazines section often contains a "View More" link, so look for the text "Magazines"
        # Use the _parse_link_section helper method, specifying the exact text of the heading
        magazines_list = await self._parse_link_section(
            container=search_container,
            header_text_exact="Magazines", 
            id_pattern=magazine_id_pattern,
            category_name_for_logging="Magazines Preview"
        )

        if not magazines_list:
            logger.warning(f"No magazines preview were successfully parsed from {target_url}.")
        else:
            logger.info(f"Successfully parsed {len(magazines_list)} magazines (preview) from {target_url}.")

        return magazines_list
    
    