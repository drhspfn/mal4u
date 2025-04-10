import asyncio
from math import ceil
import re
from typing import Any, Dict, List, Literal, Optional, Union
from urllib.parse import urlencode
import aiohttp
import logging
from bs4 import BeautifulSoup, Tag, NavigableString
from pydantic import ValidationError
from mal4u.types import LinkItem
from .types import CharacterDetails, CharacterSearchResult, RelatedMediaItem, VoiceActorItem
from mal4u.details_base import BaseDetailsParser
from mal4u.search_base import BaseSearchParser
from .. import constants

logger = logging.getLogger(__name__)


class MALCharactersParser(BaseSearchParser, BaseDetailsParser):
    def __init__(self, session: aiohttp.ClientSession):
        super().__init__(session)
        logger.info("Characters parser initialized")

    def _build_character_search_url(
        self,
        query: Optional[str] = None,
        letter: Optional[str] = None
    ) -> str:
        query_params = {}
        if query and query.strip():
            query_params['q'] = query.replace(" ", "+")

        if letter and not query_params and len(letter) == 1 and letter.isalpha():
            query_params['letter'] = letter.upper()

        query_list = list(query_params.items())
        return f"{constants.CHARACTER_URL}?{urlencode(query_list)}" if query_list else constants.CHARACTER_URL

    async def search(
        self,
        query: Optional[str],
        limit: int = 5,
        letter: Optional[str] = None,
    ) -> List[CharacterSearchResult]:
        """
        Searches for characters or lists top characters with pagination.

        Args:
            query: Search term. If None and letter is None, fetches top favorited.
            limit: Maximum number of characters to retrieve.
            letter: Single letter to filter by (only used if query is None).

        Returns:
            A list of CharacterSearchResult objects.
        """

        if limit <= 0:
            logger.warning(
                "Search limit is zero or negative, returning empty list.")
            return []

        is_search_mode = bool(query and query.strip()) or bool(
            letter and len(letter) == 1 and letter.isalpha())
        mode = 'search' if is_search_mode else 'top'

        try:
            base_search_url = self._build_character_search_url(
                query=query, letter=letter)
            logger.debug(f"Searching anime using URL: {base_search_url}")
        except ValueError as e:
            logger.error(f"Failed to build anime search URL: {e}")
            return []

        all_results: List[CharacterSearchResult] = []
        num_pages_to_fetch = ceil(limit / constants.MAL_PAGE_SIZE)

        search_term_log = f"for query '{query}'" if query else f"by letter '{letter}'" if letter else "top favorited"
        logger.info(
            f"Fetching {search_term_log} characters, limit {limit}, mode '{mode}', up to {num_pages_to_fetch} page(s).")

        for page_index in range(num_pages_to_fetch):
            offset = page_index * constants.MAL_PAGE_SIZE
            if len(all_results) >= limit:
                break

            if mode == 'top':
                page_url = self._add_offset_to_url(
                    base_search_url, offset).replace("show=", "limit=")
            else:  # mode == 'search'
                page_url = self._add_offset_to_url(base_search_url, offset)

            soup = await self._get_soup(page_url)
            if not soup:
                logger.warning(
                    f"Failed to get soup for character page offset {offset} (endpoint: {page_url})")
                break

            next_button = self._safe_find(
                soup, "a", class_="link-blue-box next")
            has_next_page = bool(next_button)
            page_rows_data = self._parse_character_page_rows(soup, mode)

            if not page_rows_data:
                logger.info(
                    f"No more character results found on page {page_index + 1} (offset {offset}).")
                break

            for row_data in page_rows_data:
                if len(all_results) >= limit:
                    break
                try:
                   #  if row_data.get('url') and row_data['url'].startswith('/'):
                   #      row_data['url'] = f"https://myanimelist.net{row_data['url']}"

                    img_url = row_data.get('image_url')
                    if img_url and img_url.startswith('https://cdn.myanimelist.net'):
                        row_data['image_url'] = img_url
                    elif img_url:  # If different format or relative (unlikely)
                        logger.warning(
                            f"Unexpected image URL format: {img_url}")
                        row_data['image_url'] = None

                    result_item = CharacterSearchResult(**row_data)
                    all_results.append(result_item)
                except ValidationError as e:
                    log_data = {k: v for k, v in row_data.items()
                                if k != 'row_soup'}
                    logger.warning(
                        f"Validation failed for character result (ID:{row_data.get('mal_id')}): {e}. Data: {log_data}")

            if len(all_results) >= limit:
                break
            # If there was no "Next" button, there is no point in requesting the next page
            if not has_next_page:
                logger.info("No 'Next 50' button found, stopping pagination.")
                break
            if page_index < num_pages_to_fetch - 1:
                await asyncio.sleep(0.5)

        logger.info(
            f"Finished character search {search_term_log}. Retrieved {len(all_results)} items (limit {limit}).")
        return all_results[:limit]

    async def get(self, character_id: int) -> Optional[CharacterDetails]:
        """Fetches and parses the MAL character details page."""
        url = constants.ANIME_DETAILS_URL.format(character_id=character_id)
        soup = await self._get_soup(url)
        if not soup:
            return None
        return self._parse_character_details_page(soup, character_id, url)

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
                    animeography_items: List[RelatedMediaItem] = []
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
                            if a_id:  # Likely an anime link
                                try:
                                    animeography_items.append(
                                        LinkItem(mal_id=a_id, name=link_name, url=link_url, type="anime"))
                                except ValidationError:
                                    pass
                            elif m_id:  # Likely a manga link
                                try:
                                    mangaography_items.append(
                                        LinkItem(mal_id=m_id, name=link_name, url=link_url, type="manga"))
                                except ValidationError:
                                    pass
                            else:
                                logger.debug(
                                    f"Could not determine type for ography link: {link_name} ({link_url})")

                    if mal_id and name:
                        # Ensure URL is absolute
                        results_data.append({
                            "mal_id": mal_id,
                            "url": url,
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



    def _parse_character_details_page(
        self,
        soup: BeautifulSoup,
        character_id: int,
        character_url: str
    ) -> Optional[CharacterDetails]:
        """Parses the content of a character detail page."""
        logger.info(f"Starting detail parsing for character ID {character_id}")
        data: Dict[str, Any] = {"mal_id": character_id, "url": character_url}

        try:
            # --- Find main columns ---
            content_div = self._safe_find(soup, "div", id="content")
            # Find the immediate table child of div#content
            main_table = self._safe_find(content_div, "table", recursive=False)
            main_tr = self._safe_find(main_table, "tr", recursive=False)
            main_tds = self._safe_find_all(
                main_tr, "td", recursive=False) if main_tr else []

            left_sidebar = main_tds[0] if len(main_tds) > 0 else None
            right_content = main_tds[1] if len(main_tds) > 1 else None
            # --- End of structural column finding ---

            # Check if successful, log error if not
            if not left_sidebar:
                logger.error("Could not find left sidebar TD structurally.")
            if not right_content:
                # Specific log
                logger.error("Could not find right content TD structurally.")
            if not (left_sidebar and right_content):
                logger.error(
                    f"Essential layout columns missing for character ID {character_id}. Cannot proceed.")
                return None
            logger.debug("Successfully identified left and right columns.")

            with open("debug.html", "w", encoding="utf-8") as f:
                # f.write(str(soup))
                f.write(str(left_sidebar))
                f.write("\n\n\n---------------------------\n\n\n")
                f.write(str(right_content))

            # --- Parse Left Sidebar ---
            logger.debug("Parsing left sidebar...")
            # Image
            img_link = self._safe_find(
                left_sidebar, "a", href=lambda h: h and "/pics" in h)
            img_tag = self._safe_find(
                img_link, "img", class_="portrait-225x350")
            if not img_tag:  # Fallback if not directly under link
                img_tag = self._safe_find(
                    left_sidebar, "img", class_="portrait-225x350")
            data['image_url'] = self._get_attr(
                img_tag, 'data-src') or self._get_attr(img_tag, 'src')
            logger.debug(
                f"Parsed Image URL: {data.get('image_url', 'Not Found')}")

            # Favorites
            fav_text_node = left_sidebar.find(
                string=re.compile(r"Member Favorites:\s*([\d,]+)"))
            if fav_text_node:
                fav_match = re.search(
                    r"Member Favorites:\s*([\d,]+)", fav_text_node)
                if fav_match:
                    data['favorites'] = self._parse_int(fav_match.group(1))
                    logger.debug(f"Parsed Favorites: {data['favorites']}")

            # Animeography & Mangaography
            data['animeography'] = []
            data['mangaography'] = []
            # Find headers *within the left sidebar*
            ography_headers = self._safe_find_all(
                left_sidebar, "div", class_="normal_header")
            for header in ography_headers:
                header_text = self._get_text(header)
                current_list = None
                id_pattern = None
                item_type = None

                if "Animeography" in header_text:
                    current_list = data['animeography']
                    id_pattern = constants.ANIME_ID_PATTERN
                    item_type = "anime"
                elif "Mangaography" in header_text:
                    current_list = data['mangaography']
                    id_pattern = constants.MANGA_ID_PATTERN
                    item_type = "manga"
                else:
                    continue

                # Table immediately after header
                table = header.find_next_sibling("table")
                if not table:
                    continue

                for row in self._safe_find_all(table, "tr"):
                    cells = self._safe_find_all(row, "td")
                    if len(cells) != 2:
                        continue

                    info_cell = cells[1]
                    link_tag = self._safe_find(info_cell, "a")
                    role_tag = self._safe_find(info_cell, "small")

                    media_url = self._get_attr(link_tag, 'href')
                    media_name = self._get_text(link_tag)
                    media_id = self._extract_id_from_url(
                        media_url, id_pattern) if media_url and id_pattern else None
                    role = self._get_text(role_tag).capitalize()

                    if media_id and media_name and media_url and role:
                        try:
                            abs_url = f"https://myanimelist.net{media_url}" if media_url.startswith(
                                '/') else media_url
                            current_list.append(RelatedMediaItem(
                                mal_id=media_id, name=media_name, url=abs_url, role=role, type=item_type))
                        except ValidationError as e:
                            logger.warning(
                                f"Skipping invalid {item_type}ography item: {media_name}. Error: {e}")
            logger.debug(
                f"Parsed Animeography: {len(data['animeography'])} items")
            logger.debug(
                f"Parsed Mangaography: {len(data['mangaography'])} items")
            # --- Finished Left Sidebar ---

            # --- Parse Right Content ---
            logger.debug("Parsing right content area...")
            # Name (uses right_content as parent)
            # Search within right_content
            name_h2 = self._safe_find(right_content, "h2", class_="normal_header")
            if name_h2:
                texts = list(name_h2.stripped_strings)
                data['name'] = texts[0] if texts else None
                # main_name_tag = self._safe_find(name_h2, "strong")
                # data['name'] = self._get_text(name_h2).strip('()')

                full_h1_text = self._get_text(name_h2)
                if data['name'] and data['name'] in full_h1_text:
                    alt_name_part = full_h1_text.replace(
                        data['name'], '').strip()
                    alt_name_part = re.sub(
                        r'^[\s("]*', '', alt_name_part).strip()
                    alt_name_part = re.sub(
                        r'[\s)"]*$', '', alt_name_part).strip()
                    if alt_name_part:
                        data['name_alt'] = alt_name_part

                jp_name_tag = self._safe_find(name_h2, "small")
                data['name_japanese'] = self._get_text(
                    jp_name_tag).strip('()') if jp_name_tag else None
                logger.debug(
                    f"Parsed Name: {data.get('name')} (Alt: {data.get('name_alt')}, JP: {data.get('name_japanese')})")
            else:
                logger.error("Could not find H1 title tag in right content.")
                data['name'] = f"Unknown Name (ID: {character_id})"

            # About section (starts after H1 found within right_content)
            about_parts = []
            current_node: Union[Tag, NavigableString,
                                None] = name_h2.next_sibling if name_h2 else None
            va_header_found = False
            while current_node:
                # Stop conditions
                if isinstance(current_node, Tag):
                    if 'normal_header' in current_node.get('class', []) and "Voice Actors" in self._get_text(current_node):
                        va_header_found = True  # Mark header found
                        break  # Stop before VA header
                    if 'ad-unit' in current_node.get('id', '') or 'sUaidzctQfngSNMH-pdatla' in current_node.get('class', []):
                        break  # Stop at ad blocks
                    # Check if we've gone outside the right_content parent (unlikely with this structure, but safe)
                    if current_node.parent != right_content and current_node.parent.parent != right_content:
                        break

                # Process node content
                if isinstance(current_node, NavigableString):
                    about_parts.append(str(current_node))
                elif isinstance(current_node, Tag):
                    if current_node.name == 'br':
                        about_parts.append('\n')
                    elif current_node.name == 'div' and 'spoiler' in current_node.get('class', []):
                        spoiler_content_tag = self._safe_find(
                            current_node, "span", class_="spoiler_content")
                        if spoiler_content_tag:
                            spoiler_text = spoiler_content_tag.get_text(
                                separator='\n', strip=True)
                            about_parts.append(
                                f"\n[SPOILER]\n{spoiler_text}\n[/SPOILER]\n")
                    elif current_node.name not in ['input', 'script', 'style']:
                        # Get text content
                        about_parts.append(current_node.get_text())

                current_node = current_node.next_sibling

            full_about = "".join(about_parts)
            data['about'] = re.sub(r'\n\s*\n', '\n\n', full_about).strip()
            logger.debug(
                f"Parsed About section (length: {len(data['about']) if data['about'] else 0})")

            # Voice Actors (search starting from right_content)
            data['voice_actors'] = []
            # Find the VA header *within* right_content
            va_header = right_content.find(
                "div", class_="normal_header", string="Voice Actors")
            if va_header:
                current_va_table = va_header.find_next_sibling("table")
                while current_va_table:
                    # Ensure we haven't somehow gone past the right_content boundary
                    if current_va_table.find_parent("td") != right_content:
                        break

                    va_row = self._safe_find(current_va_table, "tr")
                    if not va_row:
                        current_va_table = current_va_table.find_next_sibling(
                            "table")
                        continue

                    cells = self._safe_find_all(va_row, "td")
                    if len(cells) != 2:
                        current_va_table = current_va_table.find_next_sibling(
                            "table")
                        continue

                    img_cell = cells[0]
                    info_cell = cells[1]

                    img_tag = self._safe_find(img_cell, "img")
                    va_image_url = self._get_attr(
                        img_tag, 'data-src') or self._get_attr(img_tag, 'src')

                    va_link = self._safe_find(info_cell, "a")
                    va_name = self._get_text(va_link)
                    va_url = self._get_attr(va_link, 'href')
                    va_id = self._extract_id_from_url(
                        va_url, constants.PERSON_ID_PATTERN) if va_url else None

                    lang_tag = self._safe_find(info_cell, "small")
                    language = self._get_text(lang_tag)

                    if va_id and va_name and va_url and language:
                        try:
                            abs_va_url = f"https://myanimelist.net{va_url}" if va_url.startswith(
                                '/') else va_url
                            data['voice_actors'].append(VoiceActorItem(
                                mal_id=va_id, name=va_name, url=abs_va_url,
                                language=language, image_url=va_image_url, type="person"
                            ))
                        except ValidationError as e:
                            logger.warning(
                                f"Skipping invalid VA item: {va_name}. Error: {e}")

                    current_va_table = current_va_table.find_next_sibling(
                        "table")
                logger.debug(
                    f"Parsed Voice Actors: {len(data['voice_actors'])} items")
            else:
                logger.warning(
                    "Voice Actors header not found in right content.")
            # --- Finished Right Content ---

            # --- Final Validation ---
            try:
                # Ensure URLs are absolute before validation
                if data.get('url') and data['url'].startswith('/'):
                    data['url'] = f"https://myanimelist.net{data['url']}"
                if data.get('image_url') and data['image_url'].startswith('/'):
                    # Unlikely, but safe
                    data['image_url'] = f"https://myanimelist.net{data['image_url']}"

                details_object = CharacterDetails(**data)
                logger.info(
                    f"Successfully parsed and validated details for character ID {character_id}: {details_object.name}")
                return details_object
            except ValidationError as e:
                error_details = e.errors()
                problematic_fields = {err['loc'][0]: data.get(
                    err['loc'][0], '<Field Missing>') for err in error_details if err['loc']}
                logger.error(f"Pydantic validation failed for character ID {character_id}: {e}\n"
                             f"Problematic fields data: {problematic_fields}")
                return None

        except Exception as e:
            logger.exception(
                f"An critical unexpected error occurred during detail parsing for character ID {character_id}: {e}")
            return None

        except Exception as e:
            logger.exception(
                f"An critical unexpected error occurred during detail parsing for character ID {character_id}: {e}")
            return None
