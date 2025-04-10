import asyncio
from datetime import date
from math import ceil
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
import aiohttp
import logging

from pydantic import ValidationError
from bs4 import Tag 
from mal4u.details_base import BaseDetailsParser
from mal4u.types import LinkItem
from ..search_base import BaseSearchParser
from .. import constants
from .types import AnimeDetails, AnimeSearchResult, TopAnimeItem
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
        query_params = {}
        if query and query.strip():
            query_params['q'] = query.replace(" ", "+")

        if anime_type:
            query_params['type'] = anime_type.value
        if anime_status:
            query_params['status'] = anime_status.value
        if rated:
            query_params['r'] = rated.value
        if score:
            query_params['score'] = score
        if producer:
            query_params['p'] = producer

        if start_date:
            query_params.update(
                {'sd': start_date.day, 'sm': start_date.month, 'sy': start_date.year})
        if end_date:
            query_params.update(
                {'ed': end_date.day, 'em': end_date.month, 'ey': end_date.year})

        genre_pairs = []

        if include_genres:
            genre_pairs += [("genre[]", genre_id)
                            for genre_id in include_genres]
        if exclude_genres:
            genre_pairs += [("genre_ex[]", genre_id)
                            for genre_id in exclude_genres]

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
        logger.info(
            f"Fetching anime details for ID {anime_id} from {details_url}")

        soup = await self._get_soup(details_url)
        if not soup:
            logger.error(
                f"Failed to fetch or parse HTML for anime ID {anime_id} from {details_url}")
            return None

        logger.info(
            f"Successfully fetched HTML for anime ID {anime_id}. Starting parsing.")
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
            logger.exception(
                f"Top-level exception during parsing details for anime ID {anime_id}: {e}")
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
            logger.warning(
                "Search limit is zero or negative, returning empty list.")
            return []

        try:
            base_search_url = self._build_anime_search_url(
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
            logger.debug(f"Searching anime using URL: {base_search_url}")
        except ValueError as e:
            logger.error(f"Failed to build anime search URL: {e}")
            return []

        all_results: List[AnimeSearchResult] = []
        num_pages_to_fetch = ceil(limit / constants.MAL_PAGE_SIZE)

        search_term_log = f"for query '{query}'" if query else "with given filters"
        logger.info(
            f"Searching {search_term_log}, limit {limit}, fetching up to {num_pages_to_fetch} page(s).")

        for page_index in range(num_pages_to_fetch):
            offset = page_index * constants.MAL_PAGE_SIZE
            if len(all_results) >= limit:
                break

            page_url = self._add_offset_to_url(base_search_url, offset)
            soup = await self._get_soup(page_url)
            if not soup:
                logger.warning(
                    f"Failed to get soup for search page offset {offset}")
                break

            parsed_results = await self._parse_search_results_page(
                soup=soup,
                limit=limit,
                result_model=AnimeSearchResult,
                id_pattern=constants.ANIME_ID_PATTERN
            )

            for result in parsed_results:
                if len(all_results) >= limit:
                    break

                all_results.append(result)

            if len(all_results) >= limit:
                logger.debug(
                    f"Reached limit {limit} after processing page {page_index + 1}.")
                break

            if page_index < num_pages_to_fetch - 1:
                await asyncio.sleep(0.5)

        return all_results 


    def _parse_anime_search_row_details(self, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parses anime-specific details from raw search row data."""
        specific_info = {
            "type": row_data.get("raw_type_text"),
            "episodes": self._parse_int(row_data.get("raw_eps_text", "").replace("-", "")),
            "aired_from": None,
            "aired_to": None,
            "members": row_data.get("members"),
        }

        row_soup: Optional[Tag] = row_data.get("row_soup")
        if row_soup:
            cells = self._safe_find_all(row_soup, "td", recursive=False)
            if len(cells) > 4:
                date_cell = cells[4]
                date_text = self._get_text(date_cell)
                if date_text and date_text != '-':
                    aired_from, aired_to = self._parse_mal_date_range(
                        date_text)
                    specific_info["aired_from"] = aired_from
                    specific_info["aired_to"] = aired_to

                if not specific_info["members"] and len(cells) > 5:
                    member_cell = cells[5]
                    member_text = self._get_text(member_cell)
                    specific_info["members"] = self._parse_int(member_text)

        return specific_info

    # -------------------

    async def get_studios(self) -> List[LinkItem]:
        target_url = constants.ANIME_URL
        logger.info(f"Fetching studios from {target_url}")

        soup = await self._get_soup(target_url)
        if not soup:
            logger.error(
                f"Failed to fetch or parse HTML from {target_url} for studios.")
            return []

        search_container = self._safe_find(
            soup, 'div', class_='anime-manga-search')
        if not search_container:
            logger.warning(
                f"Could not find the main 'anime-manga-search' container on {target_url}.")
            return []

        studio_id_pattern = re.compile(r"/anime/producer/(\d+)/")
        studios_list = await self._parse_link_section(
            container=search_container,
            header_text_exact="Studios",
            id_pattern=studio_id_pattern,
            category_name_for_logging="Studios"
        )

        if not studios_list:
            logger.warning(
                f"No studios were successfully parsed from {target_url}.")
        else:
            logger.info(
                f"Successfully parsed {len(studios_list)} themes from {target_url}.")

        return studios_list

    async def top(
        self,
        limit: int = 50,
        top_type: Optional[constants.TopType] = None
    ) -> List[TopAnimeItem]:
        """Fetches and parses the top anime list from MAL."""

        def parse_anime_top_info_string(info_text: str) -> Dict[str, Any]:
            """Parses the raw info string specific to top anime lists."""
            parsed_info = {"type": None,
                           "episodes": None, "aired_on": None}
            # TV (25 eps) Oct 2006 - Jul 2007
            # Movie (1 eps) Aug 2020 - Aug 2020
            # ONA (12 eps) Jul 2023 - Sep 2023
            type_eps_match = re.match(
                r"^(TV Special|TV|OVA|ONA|Movie|Music)\s*(?:\((\d+)\s+eps?\))?", info_text)
            if type_eps_match:

                parsed_info["type"] = type_eps_match.group(1)
                parsed_info["episodes"] = self._parse_int(
                    type_eps_match.group(2))

            date_match = re.search(
                r"(?:eps?\))?\s*([A-Za-z]{3}\s+\d{4}(?:\s+-\s+[A-Za-z]{3}\s+\d{4})?)\s*(?:[\d,]+\s+members)?", info_text)
            if date_match:
                parsed_info["aired_on"] = date_match.group(1).strip()

            return parsed_info

        if limit <= 0:
            return []

        type_value: Optional[str] = None
        if top_type:
            if constants.TopType.is_manga_specific(top_type):
                raise ValueError(
                    f"Filter '{top_type.name}' is specific to manga and cannot be used for top anime.")
            type_value = top_type.value

        all_results: List[TopAnimeItem] = []
        page_size = 50
        num_pages_to_fetch = ceil(limit / page_size)

        logger.info(
            f"Fetching top {limit} anime across {num_pages_to_fetch} page(s).")

        for page_index in range(num_pages_to_fetch):
            offset = page_index * page_size
            soup = await self._get_top_list_page("/topanime.php", type_value, offset)
            if not soup:
                break

            common_data_list = self._parse_top_list_rows(
                soup, constants.ANIME_ID_PATTERN)

            for common_data in common_data_list:
                if len(all_results) >= limit:
                    break

                specific_info = parse_anime_top_info_string(
                    common_data.get("raw_info_text", ""))

                item_data = {**common_data, **specific_info}
                try:
                    item_data.pop("raw_info_text", None)
                    top_item = TopAnimeItem(**item_data)
                    all_results.append(top_item)
                except ValidationError as e:
                    logger.warning(
                        f"Validation failed for top anime item Rank {common_data.get('rank')} (ID:{common_data.get('mal_id')}): {e}. Data: {item_data}")

            if len(all_results) >= limit:
                break
            if page_index < num_pages_to_fetch - 1:
                await asyncio.sleep(0.5)

        logger.info(
            f"Finished fetching top anime. Retrieved {len(all_results)} items.")
        return all_results[:limit]
