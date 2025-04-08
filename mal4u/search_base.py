import re
import logging
from typing import List, Optional, Type, TypeVar
from bs4 import BeautifulSoup, Tag

from .base import BaseParser # Импортируем ваш BaseParser
from .manga.types import BaseSearchResult
from pydantic import ValidationError

logger = logging.getLogger(__name__)

T_SearchResult = TypeVar('T_SearchResult', bound=BaseSearchResult)

class BaseSearchParser(BaseParser):
    """
    Base class for MAL parsers that handle search results.
    Provides common logic for parsing search result tables.
    """

    # Patterns for ID extraction (can be overridden in child classes)
    ANIME_ID_PATTERN = re.compile(r"/anime/(\d+)/")
    MANGA_ID_PATTERN = re.compile(r"/manga/(\d+)/")

    async def _parse_search_results_page(
        self,
        soup: BeautifulSoup,
        limit: int,
        result_model: Type[T_SearchResult], # Type of Pydantic model for the outcome
        id_pattern: re.Pattern             # Pattern for ID extraction
    ) -> List[T_SearchResult]:
        """
        Parses the common structure of a MAL search results page (anime or manga).

        Args:
            soup: The BeautifulSoup object of the search results page.
            limit: The maximum number of results to parse.
            result_model: The Pydantic model class to use for each result item.
            id_pattern: The regex pattern to extract the MAL ID from the URL.

        Returns:
            A list of parsed search result objects.
        """
        results: List[T_SearchResult] = []
        table_container = self._safe_find(soup, "div", attrs={"class": "js-categories-seasonal"})
        table = self._safe_find(table_container, 'table')

        if not table:
            logger.warning("Search results table not found on the page.")
            return []

        tbody = self._safe_find(table, 'tbody')
        if not tbody:
            logger.warning("Search results table found, but no <tbody> inside. Selecting all 'tr' as fallback.")
            rows = self._safe_select(table, "tr")
        else:
            rows = tbody.find_all('tr', recursive=False)
            logger.debug(f"Found tbody, selected {len(rows)} direct child 'tr' elements.")
            

        if not rows or len(rows) < 2:
             logger.info("No result rows found in the table.")
             return []

        # Check if the first line is a header (usually contains td.fw-b)
        first_row_header_check = self._safe_find(rows[0], 'td', class_='fw-b')
        if first_row_header_check or 'Title' in self._get_text(rows[0]): 
            data_rows = rows[1:]
            logger.debug(f"Header row detected and skipped. Found {len(data_rows)} potential data rows.")
        else:
            data_rows = rows
            logger.warning("Could not reliably detect header row, processing all rows.")

        
        for row in data_rows:
            if len(results) >= limit:
                break

            cells = self._safe_find_all(row, "td")


            if len(cells) < 5:
                logger.debug(f"Skipping row: found {len(cells)} cells, expected at least 5. Row content: {row.text[:100]}...")
                continue

            try:
                # --- Retrieving data from cells (General Logic) ---
                # Cell 0: Image
                img_tag = self._safe_find(cells[0], "img")
                image_url_str = self._get_attr(img_tag, 'data-src') or self._get_attr(img_tag, 'src')

                # Cell 1: Title, URL, ID, Synopsis
                title_link_tag = self._safe_find(cells[1], "a", class_="fw-b")
                title_strong_tag = self._safe_find(title_link_tag, "strong")
                # Sometimes strong may not be present, take the text from the link
                title = self._get_text(title_strong_tag) or self._get_text(title_link_tag)
                item_url_str = self._get_attr(title_link_tag, 'href')
                mal_id = self._extract_id_from_url(item_url_str, pattern=id_pattern)

                synopsis_div = self._safe_find(cells[1], "div", class_="pt4")
                raw_synopsis = self._get_text(synopsis_div)
                synopsis = None
                if raw_synopsis:
                    read_more_link = self._safe_find(synopsis_div, 'a', string=lambda t: t and 'read more' in t.lower())
                    if read_more_link:
                        synopsis = raw_synopsis[:raw_synopsis.rfind(read_more_link.get_text())].rstrip('. ').strip()
                    else:
                        synopsis = raw_synopsis

                # Cell 2: Type (Item Type)
                item_type_text = self._get_text(cells[2]).strip()
                item_type = item_type_text if item_type_text and item_type_text != '-' else None

                # Cell 3: Episodes (Anime) / Volumes (Manga)
                count_text = self._get_text(cells[3]).strip()
                item_count = self._parse_int(count_text)

                # Cell 4: Score
                score_text = self._get_text(cells[4]).strip()
                score = self._parse_float(score_text)

                # Cell 5: Members (Anime only)
                members = None # FIXME: idk why it's not working, we'll forget it for now
                if len(cells) > 5: 
                     members_text = self._get_text(cells[5]).strip()
                     members = self._parse_int(members_text)
 
                # --- Assembling the result ---
                if title and item_url_str and mal_id is not None:
                    data_dict = {
                        "mal_id": mal_id,
                        "url": item_url_str,
                        "image_url": image_url_str if image_url_str else None,
                        "title": title,
                        "synopsis": synopsis,
                        "type": item_type,
                        "score": score,
                        "episodes": item_count if id_pattern == self.ANIME_ID_PATTERN else None,
                        "volumes": item_count if id_pattern == self.MANGA_ID_PATTERN else None,
                        "members": members if id_pattern == self.ANIME_ID_PATTERN else None,
                        "chapters": None if id_pattern == self.MANGA_ID_PATTERN else None,
                    }

                    try:
                        result_item = result_model(**data_dict)
                        results.append(result_item)
                        logger.debug(f"Successfully parsed item: ID={mal_id}, Title='{title}'")
                    except ValidationError as e:
                         logger.warning(f"Pydantic validation failed for item ID {mal_id} ('{title}'). Data: {data_dict}. Error: {e}")
                else:
                    logger.warning(f"Skipping row due to missing mandatory fields (title/url/id). Title: '{title}', URL: '{item_url_str}', Extracted ID: {mal_id}")

            except Exception as e:
                logger.exception(f"Error processing a search result row: {e}. Row content: {row.text[:150]}...")
                continue 

        logger.info(f"Search parsing complete. Found {len(results)} results (limit {limit}).")
        return results