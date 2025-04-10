import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
import aiohttp
from bs4 import BeautifulSoup, Tag, NavigableString
from typing import Dict, List, Literal, Optional, Any, Tuple, Type, Union
import logging
from datetime import date, datetime
from pydantic import ValidationError

from mal4u import constants
from .types import LinkItem

logger = logging.getLogger(__name__)


class BaseParser:
    """Base class for MAL parsers."""

    def __init__(self, session: aiohttp.ClientSession):
        if session is None:
            # This should not happen when using MyAnimeListApi correctly
            raise ValueError("ClientSession cannot be None for the parser")
        self._session = session

    def _add_offset_to_url(self, base_url: str, offset: int) -> str:
        """Adds the 'show=N' parameter correctly to a URL for pagination."""
        if offset <= 0:
            return base_url

        parsed_url = urlparse(base_url)
        query_dict = parse_qs(parsed_url.query, keep_blank_values=True)
        query_dict['show'] = [str(offset)]
        new_query_string = urlencode(query_dict, doseq=True)
        page_url = urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            new_query_string,
            parsed_url.fragment
        ))
        return page_url

    async def _request(self, url: str, method: str = "GET", **kwargs) -> Optional[str]:
        """Executes an HTTP request and returns the response text."""
        try:
            async with self._session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                logger.debug(
                    f"Request to {url} succeeded (Status: {response.status})")
                return await response.text()
        except aiohttp.ClientError as e:
            logger.error(f"Query error to {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error when querying {url}: {e}")
            return None

    async def _get_soup(self, url: str, **kwargs) -> Optional[BeautifulSoup]:
        """Gets the HTML from the page and returns a BeautifulSoup object."""
        html_content = await self._request(url, method="GET", **kwargs)
        if html_content:
            return BeautifulSoup(html_content, "html.parser")
        return None

    def _safe_find(self, parent: Optional[Union[BeautifulSoup, Tag]], name: str, **kwargs: Any) -> Optional[Tag]:
        """
        Safely find a single element using find.
        Returns Tag or None.
        """
        if parent is None:
            return None
        try:
            result = parent.find(name, **kwargs)
            # Ensure we return only Tag objects or None
            return result if isinstance(result, Tag) else None
        except Exception as e:
            logger.error(
                f"Error in _safe_find (tag={name}, kwargs={kwargs}): {e}")
            return None

    def _safe_find_all(self, parent: Optional[Union[BeautifulSoup, Tag]], name: str, **kwargs: Any) -> List[Tag]:
        """
        Safely find all elements using find_all.
        Returns a list of Tags or an empty list.
        """
        if parent is None:
            return []
        try:
            # find_all returns a ResultSet which is list-like containing Tags
            return parent.find_all(name, **kwargs)
        except Exception as e:
            logger.error(
                f"Error in _safe_find_all (tag={name}, kwargs={kwargs}): {e}")
            return []

    def _safe_select(self, parent: Optional[Union[BeautifulSoup, Tag]], selector: str) -> List[Tag]:
        """
        Safely find multiple elements using a CSS selector.
        Returns a list of Tags or an empty list.
        """
        if parent is None:
            return []
        try:
            # select returns a list of Tags
            return parent.select(selector)
        except Exception as e:
            logger.error(f"Error in _safe_select (selector='{selector}'): {e}")
            return []

    def _get_text(self, element: Optional[Any], default: str = "") -> str:
        """Safely retrieve text from an element."""
        return element.get_text(strip=True) if element else default

    def _get_attr(self, element: Optional[Any], attr: str, default: str = "") -> str:
        """Securely retrieve the attribute of an element."""
        return element.get(attr, default) if element else default

    def _parse_int(self, text: Optional[str], default: Optional[int] = None) -> Optional[int]:
        if text is None:
            return default
        try:
            # Remove commas and potential unicode spaces before converting
            cleaned_text = text.replace(',', '').replace('\xa0', '').strip()
            if not cleaned_text:
                return default
            return int(cleaned_text)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse int from: '{text}'")
            return default

    def _parse_float(self, text: str, default: Optional[float] = None) -> Optional[float]:
        """Tries to convert a string to float."""
        try:
            return float(text.strip())
        except (ValueError, TypeError, AttributeError):
            return default

    def _extract_id_from_url(self, url: Optional[str], pattern: Union[str, re.Pattern] = r"/(\d+)/") -> Optional[int]:
        """Tries to extract an ID from a URL using a regular expression."""
        if not url:
            logger.debug("URL is empty, cannot extract ID.")
            return None
        try:
            match = re.search(pattern, url)
            if match:
                try:
                    id_str = match.group(1)
                    return int(id_str)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not convert extracted ID '{id_str}' to int for URL: {url} using pattern: {pattern}")
                    return None
                except IndexError:
                    logger.error(
                        f"Regex pattern '{pattern}' matched URL '{url}' but has no capturing group 1.")
                    return None
            else:
                logger.debug(
                    f"Regex pattern '{pattern}' did not match URL: {url}")
                return None
        except re.error as e:
            logger.error(
                f"Regex error while searching URL '{url}' with pattern '{pattern}': {e}")
            return None
        except Exception as e:
            logger.exception(
                f"Unexpected error in _extract_id_from_url for URL '{url}': {e}")
            return None

    def _find_nested(self, parent: Optional[Union[BeautifulSoup, Tag]],
                     *search_path: Union[Tuple[str, Dict[str, Any]], str, Tuple[str]]) -> Optional[Tag]:

        current_element = parent
        for i, step in enumerate(search_path):
            if current_element is None:
                return None
            tag_name: Optional[str] = None
            attributes: Dict[str, Any] = {}
            try:
                if isinstance(step, str):
                    tag_name = step
                elif isinstance(step, tuple):
                    if len(step) >= 1 and isinstance(step[0], str):
                        tag_name = step[0]
                        if len(step) == 2 and isinstance(step[1], dict):
                            attributes = step[1]
                        elif len(step) > 1 and not (len(step) == 2 and isinstance(step[1], dict)):
                            logger.warning(
                                f"_find_nested: Invalid tuple format at step {i}: {step}. Use (tag,) or (tag, {{attrs}}).")
                            return None
                    else:
                        logger.warning(
                            f"_find_nested: Invalid tuple format at step {i}: {step}. First element must be a string (tag name).")
                        return None
                else:
                    logger.warning(
                        f"_find_nested: Invalid step type at {i}: {type(step)}. Expected str or tuple.")
                    return None
                if tag_name is None:
                    logger.warning(
                        f"_find_nested: Tag name not defined at step {i}: {step}.")
                    return None
                found = current_element.find(tag_name, **attributes)
                current_element = found if isinstance(found, Tag) else None
            except Exception as e:
                logger.error(
                    f"_find_nested: Error at step {i} finding '{tag_name}' with {attributes}: {e}")
                return None
        return current_element

    def _parse_link_list(
        self,
        start_node: Optional[Tag],
        parent_limit: Optional[Tag] = None,  # Limit search within this parent
        pattern: Union[str, re.Pattern] = r"/(\d+)/"
    ) -> List[LinkItem]:
        """
        Parses a list of <a> tags following a start_node within an optional parent_limit.
        Extracts MAL ID from the href using the provided regex pattern.
        """
        links = []
        if not start_node:
            return links

        # Determine the effective container to search within
        container = parent_limit if parent_limit else start_node.parent
        if not container:
            return links  # Cannot search without a container

        # Find all relevant 'a' tags *after* the start_node *within* the container
        # This requires careful handling of siblings vs. descendants
        relevant_tags = []
        current_node = start_node.next_sibling
        while current_node:
            if isinstance(current_node, Tag):
                # Stop condition if we hit another major block header like H2
                # Or if we have left the original parent_limit scope (more complex check needed)
                if current_node.name == 'h2':
                    break
                # If parent_limit is defined, ensure we haven't moved outside it
                if parent_limit and current_node not in parent_limit.descendants:
                    break

                if current_node.name == 'a':
                    relevant_tags.append(current_node)
                # Check for 'a' tags inside other tags (like spans, etc.)
                else:
                    relevant_tags.extend(
                        self._safe_find_all(current_node, 'a'))

            current_node = current_node.next_sibling

        for link_tag in relevant_tags:
            href = self._get_attr(link_tag, 'href')
            name = self._get_text(link_tag)
            mal_id = None

            if href:
                mal_id = self._extract_id_from_url(href, pattern=pattern)

            if name and href and mal_id is not None:
                try:
                    link_type = None
                    if "/anime/producer/" in href or "/company/" in href:
                        link_type = "producer"  # MAL uses producer ID for studio/licensor
                    elif "/people/" in href:
                        link_type = "person"
                    elif "/character/" in href:
                        link_type = "character"
                    elif "/manga/magazine/" in href:
                        link_type = "magazine"
                    elif "/anime/genre/" in href or "/manga/genre/" in href:
                        link_type = "genre"  # Genre/Theme/Demographic

                    links.append(
                        LinkItem(mal_id=mal_id, name=name, url=href, type=link_type))
                except ValidationError as e:
                    logger.warning(
                        f"Skipping invalid link item: Name='{name}', URL='{href}', ID='{mal_id}'. Error: {e}")
            else:
                logger.debug(
                    f"Skipping link node: Name='{name}', Href='{href}', Extracted ID='{mal_id}' using pattern '{pattern}'")

        return links

    def _parse_mal_date_range(self, date_str: Optional[str]) -> Tuple[Optional[date], Optional[date]]:
        if not date_str or date_str.strip() == '?':
            return None, None
        start_date: Optional[date] = None
        end_date: Optional[date] = None
        parts = [p.strip() for p in date_str.split(" to ")]

        def parse_single_date(text: str) -> Optional[date]:
            if not text or text == '?':
                return None
            fmts = ["%b %d, %Y", "%b, %Y", "%Y"]
            for fmt in fmts:
                try:
                    cleaned_text = re.sub(r'\s+', ' ', text).strip()
                    # Special case: MAL uses '??' for unknown day
                    cleaned_text = cleaned_text.replace(
                        "??", "01")  # Replace ?? with 1st day
                    # Handle 'Aug, 1989' vs 'Aug 01, 1989' from '??'
                    if fmt == "%b %d, %Y" and "01" in cleaned_text and text.count(" ") == 1:
                        continue  # Skip day format if original was month/year only
                    dt = datetime.strptime(cleaned_text, fmt)
                    # Return only year and month if day was originally unknown
                    if fmt != "%b %d, %Y" or "01" not in cleaned_text or text.count(" ") == 2:
                        return dt.date()
                    else:  # Return only year/month if day was '??'
                        # This logic is a bit complex, maybe just returning the parsed date is fine
                        # Pydantic might need date or None, not partial date.
                        # Let's return the full parsed date (with day 1 if unknown)
                        return dt.date()

                except ValueError:
                    continue
            logger.warning(f"Could not parse date part: '{text}'")
            return None

        if len(parts) >= 1:
            start_date = parse_single_date(parts[0])
        if len(parts) == 2:
            end_date = parse_single_date(parts[1])
        return start_date, end_date

    def _get_clean_sibling_text(self, node: Optional[Tag]) -> Optional[str]:
        if node and node.next_sibling:
            sibling = node.next_sibling
            # Iterate past whitespace-only NavigableString nodes
            while isinstance(sibling, NavigableString) and not str(sibling).strip():
                sibling = sibling.next_sibling
            # Now check if the next *meaningful* sibling is text
            if isinstance(sibling, NavigableString):
                text = str(sibling).strip()
                return text if text else None
        return None

    async def _parse_link_section(self,
                                  container: Tag,
                                  header_text_exact: str,
                                  id_pattern: re.Pattern,
                                  category_name_for_logging: str) -> List[LinkItem]:
        """
        An internal method to search for a section by title text
        and parsing links inside it. Improved for title text search.
        """
        results: List[LinkItem] = []
        header: Optional[Tag] = None

        potential_headers = self._safe_find_all(
            container, 'div', class_='normal_header')

        for h in potential_headers:
            direct_texts = [str(c).strip() for c in h.contents if isinstance(
                c, NavigableString) and str(c).strip()]

            if header_text_exact in direct_texts:
                # Additional check: make sure it's not part of the text of another heading
                # For example, "Explicit Genres" contains "Genres". We want an exact match.
                # Often the desired text is the last text node.
                if direct_texts and direct_texts[-1] == header_text_exact:
                    header = h
                    logger.debug(
                        f"Found header for '{header_text_exact}' using direct text node check.")
                    break

        # If you can't find it via direct text, let's try the old method (in case of headings inside <a>)
        if not header:
            for h in potential_headers:
                header_link = self._safe_find(
                    h, 'a', string=lambda t: t and header_text_exact == t.strip())
                if header_link:
                    header = h
                    logger.debug(
                        f"Found header for '{header_text_exact}' using inner link text check.")
                    break

        if not header:
            logger.warning(
                f"Header '{header_text_exact}' not found in the container using multiple checks.")
            return results

        link_container = header.find_next_sibling('div', class_='genre-link')
        if not link_container:
            logger.warning(
                f"Could not find 'div.genre-link' container after header: '{header_text_exact}'")
            return results

        links = self._safe_find_all(
            link_container, 'a', class_='genre-name-link')
        if not links:
            logger.debug(
                f"No 'a.genre-name-link' found within the container for '{header_text_exact}'.")
            return results

        for link_tag in links:
            href = self._get_attr(link_tag, 'href')
            full_text = self._get_text(link_tag)
            name = re.sub(r'\s*\(\d{1,3}(?:,\d{3})*\)$', '', full_text).strip()
            mal_id = self._extract_id_from_url(href, pattern=id_pattern)

            if name and href and mal_id is not None:
                try:
                    item = LinkItem(mal_id=mal_id, name=name, url=href)
                    results.append(item)
                except ValidationError as e:
                    logger.warning(
                        f"Skipping invalid LinkItem data from '{category_name_for_logging}': Name='{name}', URL='{href}', ID='{mal_id}'. Error: {e}")
                except Exception as e:
                    logger.error(
                        f"Error creating LinkItem for '{name}' ({href}) in '{category_name_for_logging}': {e}", exc_info=True)
            else:
                logger.debug(
                    f"Skipping link in '{category_name_for_logging}' due to missing data: Text='{full_text}', Href='{href}', Extracted ID='{mal_id}'")

        return results

    async def _get_top_list_page(
        self,
        endpoint: Literal['/topanime.php', '/topmanga.php'],
        top_type: Optional[str] = None,
        offset: int = 10
    ) -> Optional[BeautifulSoup]:
        """Fetches a single page of a MAL top list (Anime/Manga)."""
        params = {}
        if offset > 0:
            params["limit"] = offset
        if top_type:
            params["type"] = top_type

        url = endpoint
        logger.debug(f"Requesting top list page: {url} with offset {offset}")
        soup = await self._get_soup(url, params=params)
        if not soup:
            logger.error(
                f"Failed to fetch top list page: {url} with offset {offset}")
            return None
        return soup

    def _parse_top_list_rows(
        self,
        soup: BeautifulSoup,
        id_pattern: Union[str, re.Pattern]
    ) -> List[Dict[str, Any]]:
        """
        Parses the ranking rows from a single top list page soup.
        Extracts common fields and the raw info string for type-specific parsing later.

        Args:
            soup: BeautifulSoup object of the top list page.
            id_pattern: Regex pattern to extract the MAL ID from the item URL.

        Returns:
            A list of dictionaries, each containing common data and 'raw_info_text'.
        """
        results: List[Dict[str, Any]] = []
        table = self._safe_find(soup, "table", class_="top-ranking-table")
        if not table:
            logger.error("Could not find top ranking table on the page.")
            return results

        ranking_rows = self._safe_find_all(table, "tr", class_="ranking-list")
        logger.debug(f"Found {len(ranking_rows)} ranking rows on the page.")

        for row in ranking_rows:
            try:
                # At MAL the class name is the same for anime/manga
                rank_tag = self._safe_find(
                    row, "span", class_="top-anime-rank-text")
                rank = self._parse_int(self._get_text(rank_tag))

                title_cell = self._safe_find(row, "td", class_="title")
                title_link = self._find_nested(
                    title_cell, ("div", {"class": "detail"}), "h3", "a")
                title = self._get_text(title_link)
                item_url_str = self._get_attr(title_link, 'href')
                mal_id = self._extract_id_from_url(
                    item_url_str, pattern=id_pattern)

                img_tag = self._find_nested(title_cell, "a", "img")
                image_url_str = self._get_attr(
                    img_tag, 'data-src') or self._get_attr(img_tag, 'src')

                score_td = self._safe_find(row, "td", class_="score")
                score_tag = self._safe_find(
                    score_td, "span", class_="score-label") if score_td else None
                score = self._parse_float(self._get_text(score_tag))

                info_div = self._safe_find(
                    title_cell, "div", class_="information")
                raw_info_text = self._get_text(
                    info_div, "").replace('\n', ' ').strip()

                members_match = re.search(
                    r"([\d,]+)\s+members", raw_info_text, re.IGNORECASE)
                members = self._parse_int(
                    members_match.group(1)) if members_match else None

                if mal_id is not None and rank is not None and title:
                    item_data = {
                        "mal_id": mal_id,
                        "rank": rank,
                        "title": title,
                        "url": item_url_str,
                        "image_url": image_url_str,
                        "score": score,
                        "members": members,
                        "raw_info_text": raw_info_text
                    }
                    results.append(item_data)
                else:
                    logger.warning(
                        f"Skipping row due to missing essential common data (Rank: {rank}, ID: {mal_id}, Title: {title})")

            except Exception as e:
                logger.exception(
                    f"Error parsing ranking row: {row.text[:100]}...")

        return results

    def _parse_character_page_rows(
        self,
        soup: BeautifulSoup,
        mode: Literal['top', 'search']
    ) -> List[Dict[str, Any]]:
        """
        Parses character rows from a single page soup based on the mode.
        Returns a list of dictionaries with raw data.
        """
        results_data: List[Dict[str, Any]] = []
        id_pattern = constants.CHARACTER_ID_PATTERN

        if mode == 'top':
            table = self._safe_find(
                soup, "table", class_="characters-favorites-ranking-table")
            if not table:
                logger.warning("Top characters table not found.")
                return results_data
            rows = self._safe_find_all(table, "tr", class_="ranking-list")
            logger.debug(f"[Top Mode] Found {len(rows)} ranking rows.")

            for row in rows:
                try:
                    rank_tag = self._safe_find(
                        row, "span", class_="pepole-rank-text")
                    rank = self._parse_int(self._get_text(rank_tag))

                    people_cell = self._safe_find(row, "td", class_="people")
                    if not people_cell:
                        continue

                    img_link = self._safe_find(people_cell, "a", class_="fl-l")
                    img_tag = self._safe_find(img_link, "img")
                    image_url_str = self._get_attr(
                        img_tag, 'data-src') or self._get_attr(img_tag, 'src')

                    info_div = self._safe_find(
                        people_cell, "div", class_="information")
                    name_link = self._safe_find(info_div, "a")
                    name = self._get_text(name_link)
                    url = self._get_attr(name_link, 'href')
                    mal_id = self._extract_id_from_url(url, id_pattern)
                    jp_name_tag = self._safe_find(
                        info_div, "span", class_="fn-grey6")
                    jp_name = self._get_text(jp_name_tag).strip(
                        '()') if jp_name_tag else None

                    # --- FIX: Corrected Animeography/Mangaography Parsing for Top Mode ---
                    animeography_items: List[LinkItem] = []
                    animeo_cell = self._safe_find(
                        row, "td", class_="animeography")
                    if animeo_cell:
                        # Find all 'div' with class 'title' inside the cell first
                        title_divs = self._safe_find_all(
                            animeo_cell, "div", class_="title")
                        for title_div in title_divs:
                            # Find 'a' inside 'div.title'
                            link = self._safe_find(title_div, "a")
                            if link:
                                a_url = self._get_attr(link, "href")
                                a_name = self._get_text(link)
                                a_id = self._extract_id_from_url(
                                    a_url, constants.ANIME_ID_PATTERN)
                                if a_id and a_name and a_url:
                                    try:
                                        # Ensure URL is absolute
                                        abs_a_url = f"https://myanimelist.net{a_url}" if a_url.startswith(
                                            '/') else a_url
                                        animeography_items.append(
                                            LinkItem(mal_id=a_id, name=a_name, url=abs_a_url, type="anime"))
                                    except ValidationError as e:
                                        logger.warning(
                                            f"Skipping invalid animeography link: Name='{a_name}', URL='{a_url}'. Error: {e}")

                    mangaography_items: List[LinkItem] = []
                    mangao_cell = self._safe_find(
                        row, "td", class_="mangaography")
                    if mangao_cell:
                        # Find all 'div' with class 'title' inside the cell first
                        title_divs = self._safe_find_all(
                            mangao_cell, "div", class_="title")
                        for title_div in title_divs:
                            # Find 'a' inside 'div.title'
                            link = self._safe_find(title_div, "a")
                            if link:
                                m_url = self._get_attr(link, "href")
                                m_name = self._get_text(link)
                                m_id = self._extract_id_from_url(
                                    m_url, constants.MANGA_ID_PATTERN)
                                if m_id and m_name and m_url:
                                    try:
                                        # Ensure URL is absolute
                                        abs_m_url = f"https://myanimelist.net{m_url}" if m_url.startswith(
                                            '/') else m_url
                                        mangaography_items.append(
                                            LinkItem(mal_id=m_id, name=m_name, url=abs_m_url, type="manga"))
                                    except ValidationError as e:
                                        logger.warning(
                                            f"Skipping invalid mangaography link: Name='{m_name}', URL='{m_url}'. Error: {e}")
                    # --- END OF FIX ---

                    fav_cell = self._safe_find(row, "td", class_="favorites")
                    favorites = self._parse_int(self._get_text(fav_cell))

                    if mal_id and name:
                        # Ensure URL is absolute before adding to dict
                        abs_char_url = f"https://myanimelist.net{url}" if url.startswith(
                            '/') else url
                        results_data.append({
                            "mal_id": mal_id,
                            "url": abs_char_url,
                            "image_url": image_url_str,
                            "name": name,
                            "japanese_name": jp_name,
                            "nickname": None,
                            "favorites": favorites,
                            "rank": rank,
                            "animeography": animeography_items,
                            "mangaography": mangaography_items
                        })

                except Exception as e:
                    logger.exception(
                        f"Error parsing top character row: {e}. Row: {row.text[:100]}...")

        elif mode == 'search':
            # --- FIX: Corrected Animeography/Mangaography Parsing for Search Mode ---
            # (This part also needs adjustment as the structure is different)
            result_table = self._safe_find(soup, "table")
            rows = []
            if result_table:
                rows = self._safe_find_all(result_table, "tr")
                if rows and ('Header' in self._get_text(rows[0]) or 'Character' in self._get_text(rows[0])):
                    rows = rows[1:]
            else:
                rows = soup.select("tr.borderClass, tr[class^='bgColor']")
            logger.debug(f"[Search Mode] Found {len(rows)} potential rows.")

            for row in rows:
                try:
                    cells = self._safe_find_all(row, "td", recursive=False)
                    if len(cells) < 3:
                        continue

                    pic_cell = cells[0]
                    info_cell = cells[1]
                    # The cell containing both anime and manga
                    ography_cell = cells[2]

                    img_tag = self._safe_find(pic_cell, "img")
                    image_url_str = self._get_attr(
                        img_tag, 'data-src') or self._get_attr(img_tag, 'src')

                    name_link = self._safe_find(info_cell, "a")
                    name = self._get_text(name_link)
                    url = self._get_attr(name_link, 'href')
                    mal_id = self._extract_id_from_url(url, id_pattern)

                    nickname_tag = self._safe_find(info_cell, "small")
                    nickname = self._get_text(nickname_tag).strip(
                        '()') if nickname_tag else None

                    animeography_items = []
                    mangaography_items = []
                    if ography_cell:
                        # Find all <a> tags directly within the ography cell
                        all_links = self._safe_find_all(ography_cell, "a")
                        current_list = None  # Track if we are parsing anime or manga links

                        # Check for markers like 'Anime:' or 'Manga:' if they exist as text nodes or in divs
                        anime_marker = ography_cell.find(
                            string=re.compile(r"^\s*Anime:", re.I))
                        manga_marker = ography_cell.find(
                            string=re.compile(r"^\s*Manga:", re.I))

                        # If markers exist, parse based on position relative to markers (more complex)
                        # Simpler approach: Iterate through links and guess type based on URL
                        for link in all_links:
                            link_url = self._get_attr(link, "href")
                            link_name = self._get_text(link)

                            if not (link_url and link_name):
                                continue

                            a_id = self._extract_id_from_url(
                                link_url, constants.ANIME_ID_PATTERN)
                            m_id = self._extract_id_from_url(
                                link_url, constants.MANGA_ID_PATTERN)
                            abs_link_url = f"https://myanimelist.net{link_url}" if link_url.startswith(
                                '/') else link_url

                            if a_id:  # Likely an anime link
                                try:
                                    animeography_items.append(
                                        LinkItem(mal_id=a_id, name=link_name, url=abs_link_url, type="anime"))
                                except ValidationError:
                                    pass
                            elif m_id:  # Likely a manga link
                                try:
                                    mangaography_items.append(
                                        LinkItem(mal_id=m_id, name=link_name, url=abs_link_url, type="manga"))
                                except ValidationError:
                                    pass
                            else:
                                logger.debug(
                                    f"Could not determine type for ography link: {link_name} ({link_url})")

                    if mal_id and name:
                        # Ensure URL is absolute
                        abs_char_url = f"https://myanimelist.net{url}" if url.startswith(
                            '/') else url
                        results_data.append({
                            "mal_id": mal_id,
                            "url": abs_char_url,
                            "image_url": image_url_str,
                            "name": name,
                            "nickname": nickname,
                            "japanese_name": None,
                            "favorites": None,
                            "rank": None,
                            "animeography": animeography_items,
                            "mangaography": mangaography_items
                        })

                except Exception as e:
                    logger.exception(
                        f"Error parsing search character row: {e}. Row: {row.text[:100]}...")
            # --- END OF FIX ---

        return results_data
