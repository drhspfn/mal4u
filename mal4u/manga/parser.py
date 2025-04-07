from typing import Any, Dict, List, Optional
import aiohttp
import logging
import re

from bs4 import BeautifulSoup, Tag
from pydantic import ValidationError
from mal4u.types import CharacterItem, ExternalLink, LinkItem, RelatedItem

from .types import MangaDetails, MangaSearchResult 
from ..base import BaseParser
from .. import constants

logger = logging.getLogger(__name__)

class MALMangaParser(BaseParser):
    """A parser to search and retrieve information about manga from MyAnimeList."""

    def __init__(self, session: aiohttp.ClientSession):
        super().__init__(session)
        logger.info("Manga parser initialized")


    async def get(self, manga_id: int) -> Optional[MangaDetails]:
        """
        Fetches and parses the details page for a specific manga ID.

        Args:
            manga_id: The MyAnimeList ID of the manga.

        Returns:
            A MangaDetails object if successful, None otherwise.
        """
        if not manga_id or manga_id <= 0:
            logger.error("Invalid manga ID provided.")
            return None

        details_url = constants.MANGA_DETAILS_URL.format(manga_id=manga_id)
        logger.info(f"Fetching manga details for ID {manga_id} from {details_url}")

        soup = await self._get_soup(details_url)
        if not soup:
            logger.error(f"Failed to fetch or parse HTML for manga ID {manga_id}")
            return None

        logger.info(f"Successfully fetched HTML for manga ID {manga_id}. Starting parsing.")
        try:
            parsed_data = self._parse_manga_details(soup, manga_id, details_url)
            if parsed_data:
                 logger.info(f"Successfully parsed details for manga ID {manga_id}")
            else:
                 logger.warning(f"Parsing completed but no data extracted for manga ID {manga_id}")
            return parsed_data
        except Exception as e:
            logger.exception(f"An unexpected error occurred during parsing for manga ID {manga_id}: {e}")
            return None

    def _parse_manga_details(self, soup: BeautifulSoup, manga_id: int, manga_url: str) -> Optional[MangaDetails]:
        """Helper method to parse the BeautifulSoup object of a manga details page."""

        try:
            data: Dict[str, Any] = {"mal_id": manga_id, "url": manga_url}

            # --- Main Title ---
            title_span = self._find_nested(soup, ("h1", {"class": "h1"}), ("span", {"itemprop": "name"}))
            data['title'] = self._get_text(title_span, f"Title not found for ID {manga_id}")
            if not title_span: logger.warning("Could not find main title span.")

            # --- Left Sidebar ---
            left_sidebar = self._safe_find(soup, "td", attrs={"class": "borderClass", "width": "225"})
            if not left_sidebar:
                logger.warning("Could not find left sidebar. Some data might be missing.")
            else:
                 # --- Image ---
                img_tag = self._safe_find(left_sidebar, "img", attrs={"itemprop": "image"})
                data['image_url'] = self._get_attr(img_tag, 'data-src')

                # --- Alternative Titles ---
                alt_titles = {"english": None, "synonyms": [], "japanese": None}
                # Find the h2 first
                alt_title_h2 = self._safe_find(left_sidebar, "h2", string="Alternative Titles")
                current_node = alt_title_h2.find_next_sibling() if alt_title_h2 else None
                while current_node and current_node.name != 'h2': # Stop at next h2
                    if isinstance(current_node, Tag) and current_node.has_attr('class') and 'spaceit_pad' in current_node.get('class', []):
                        dark_text_span = self._safe_find(current_node, "span", class_="dark_text")
                        if dark_text_span:
                            label = self._get_text(dark_text_span).lower()
                            value = self._get_clean_sibling_text(dark_text_span)
                            if value:
                                if "synonyms" in label:
                                    # Synonyms might be comma-separated or multiple divs
                                    alt_titles["synonyms"].extend([s.strip() for s in value.split(',') if s.strip()])
                                elif "japanese" in label:
                                    alt_titles["japanese"] = value
                                elif "english" in label: # Check inside hidden div too
                                     alt_titles["english"] = value

                    # Check for the hidden English title section
                    elif isinstance(current_node, Tag) and current_node.has_attr('class') and 'js-alternative-titles' in current_node.get('class', []):
                         english_div = self._safe_find(current_node, "div", class_="spaceit_pad")
                         if english_div:
                              dark_text_span = self._safe_find(english_div, "span", class_="dark_text")
                              if dark_text_span and "english" in self._get_text(dark_text_span).lower():
                                   alt_titles["english"] = self._get_clean_sibling_text(dark_text_span)

                    current_node = current_node.next_sibling

                data['title_english'] = alt_titles['english']
                data['title_japanese'] = alt_titles['japanese']
                data['title_synonyms'] = alt_titles['synonyms']


                # --- Information Block ---
                info_h2 = self._safe_find(left_sidebar, "h2", string="Information")
                current_node = info_h2.find_next_sibling() if info_h2 else None
                while current_node and current_node.name != 'h2': # Stop at Statistics h2
                    if isinstance(current_node, Tag) and current_node.has_attr('class') and 'spaceit_pad' in current_node.get('class', []):
                         dark_text_span = self._safe_find(current_node, "span", class_="dark_text")
                         if dark_text_span:
                              label = self._get_text(dark_text_span).lower()
                              value_text = self._get_clean_sibling_text(dark_text_span)

                              if "type:" in label:
                                   type_link = self._safe_find(current_node, "a")
                                   data['type'] = self._get_text(type_link)
                              elif "volumes:" in label and value_text:
                                   data['volumes'] = self._parse_int(value_text)
                              elif "chapters:" in label and value_text:
                                   data['chapters'] = self._parse_int(value_text)
                              elif "status:" in label and value_text:
                                   data['status'] = value_text
                              elif "published:" in label and value_text:
                                   pub_from, pub_to = self._parse_mal_date_range(value_text)
                                   data['published_from'] = pub_from
                                   data['published_to'] = pub_to
                              elif "genres:" in label:
                                   data['genres'] = self._parse_link_list(dark_text_span)
                              elif "themes:" in label:
                                   data['themes'] = self._parse_link_list(dark_text_span)
                              elif "demographic:" in label:
                                   data['demographics'] = self._parse_link_list(dark_text_span)
                              elif "serialization:" in label:
                                   ser_link_tag = self._safe_find(dark_text_span.parent, "a")
                                   ser_name = self._get_text(ser_link_tag)
                                   ser_url = self._get_attr(ser_link_tag, 'href')
                                   ser_id_match = re.search(r"/manga/magazine/(\d+)/", ser_url or "")
                                   ser_id = self._parse_int(ser_id_match.group(1)) if ser_id_match else None
                                   if ser_id and ser_name and ser_url:
                                       try:
                                           data['serialization'] = LinkItem(mal_id=ser_id, name=ser_name, url=ser_url)
                                       except ValidationError as e:
                                            logger.warning(f"Skipping invalid serialization: {ser_name}, {ser_url}. Error: {e}")
                              elif "authors:" in label:
                                   data['authors'] = self._parse_link_list(dark_text_span)

                    current_node = current_node.next_sibling

                # --- Statistics Block ---
                stats_h2 = self._safe_find(left_sidebar, "h2", string="Statistics")
                current_node = stats_h2.find_next_sibling() if stats_h2 else None
                while current_node and current_node.name != 'h2': # Stop at Available At h2
                    if isinstance(current_node, Tag) and current_node.has_attr('class') and 'spaceit_pad' in current_node.get('class', []):
                        dark_text_span = self._safe_find(current_node, "span", class_="dark_text")
                        if dark_text_span:
                            label = self._get_text(dark_text_span).lower()
                            # Need careful extraction for stats as values are not direct siblings
                            if "score:" in label:
                                score_val_span = self._safe_find(dark_text_span.parent, "span", attrs={"itemprop": "ratingValue"})
                                score_count_span = self._safe_find(dark_text_span.parent, "span", attrs={"itemprop": "ratingCount"})
                                data['score'] = self._parse_float(self._get_text(score_val_span))
                                data['scored_by'] = self._parse_int(self._get_text(score_count_span))
                            elif "ranked:" in label:
                                rank_text = self._get_clean_sibling_text(dark_text_span) # Gets "#12..."
                                data['rank'] = self._parse_int(rank_text.split('#')[-1].split('2')[0] if rank_text else None) # Extract number part
                            elif "popularity:" in label:
                                pop_text = self._get_clean_sibling_text(dark_text_span)
                                data['popularity'] = self._parse_int(pop_text.split('#')[-1] if pop_text else None)
                            elif "members:" in label:
                                data['members'] = self._parse_int(self._get_clean_sibling_text(dark_text_span))
                            elif "favorites:" in label:
                                data['favorites'] = self._parse_int(self._get_clean_sibling_text(dark_text_span))

                    current_node = current_node.next_sibling

                # --- External Links ---
                data['external_links'] = []
                avail_h2 = self._safe_find(left_sidebar, "h2", string="Available At")
                if avail_h2:
                    ext_links_div = avail_h2.find_next_sibling("div", class_="external_links")
                    for link_tag in self._safe_find_all(ext_links_div, "a"):
                         name = self._get_text(self._safe_find(link_tag, "div", class_="caption")) or self._get_text(link_tag)
                         url = self._get_attr(link_tag, 'href')
                         if name and url:
                             try:
                                 link = ExternalLink(name=name, url=url)
                                 data['external_links'].append(link)
                                 if "official site" in name.lower():
                                      data['official_site'] = url
                             except ValidationError as e:
                                 logger.warning(f"Skipping invalid external link: {name}, {url}. Error: {e}")


                res_h2 = self._safe_find(left_sidebar, "h2", string="Resources")
                if res_h2:
                    ext_links_div = res_h2.find_next_sibling("div", class_="external_links")
                    for link_tag in self._safe_find_all(ext_links_div, "a"):
                         name = self._get_text(self._safe_find(link_tag, "div", class_="caption")) or self._get_text(link_tag)
                         url = self._get_attr(link_tag, 'href')
                         if name and url:
                              try:
                                 data['external_links'].append(ExternalLink(name=name, url=url))
                              except ValidationError as e:
                                 logger.warning(f"Skipping invalid resource link: {name}, {url}. Error: {e}")

            # --- Right Content Area ---
            right_content = self._safe_find(soup, "td", attrs={"style": "padding-left: 5px;"})
            if not right_content:
                 logger.warning("Could not find right content area. Synopsis, Background, Related, Characters might be missing.")
            else:
                 # --- Synopsis ---
                 synopsis_span = self._safe_find(right_content, "span", attrs={"itemprop": "description"})
                 # Extract text carefully, handling <br> tags appropriately
                 synopsis_text = ""
                 if synopsis_span:
                     for content in synopsis_span.contents:
                         if isinstance(content, str):
                             synopsis_text += content.strip() + " "
                         elif isinstance(content, Tag) and content.name == 'br':
                             synopsis_text += "\n" # Keep line breaks
                 data['synopsis'] = synopsis_text.strip() if synopsis_text else None
                 # Clean included one-shot text if present and desired
                 if data['synopsis'] and 'Included one-shot:' in data['synopsis']:
                     data['synopsis'] = data['synopsis'].split('Included one-shot:')[0].strip()


                 # --- Background ---
                 background_h2 = self._safe_find(right_content, "h2", string="Background")
                 background_text = ""
                 if background_h2:
                     current_node = background_h2.next_sibling
                     while current_node:
                         if isinstance(current_node, Tag) and current_node.name == 'h2': # Stop at next h2
                             break
                         if isinstance(current_node, str):
                              background_text += current_node.strip() + " "
                         elif isinstance(current_node, Tag) and current_node.name == 'br':
                              background_text += "\n"
                         elif isinstance(current_node, Tag): # Get text from other tags like <i> if needed
                              background_text += current_node.get_text(strip=True) + " "

                         current_node = current_node.next_sibling
                 data['background'] = background_text.strip() if background_text else None


                 # --- Related Entries ---
                 data['related'] = {}
                 related_div = self._safe_find(right_content, "div", class_="related-entries")
                 if related_div:
                      # Entries in divs
                      for entry_div in self._safe_find_all(related_div, "div", class_="entry"):
                          relation_type = self._get_text(self._safe_find(entry_div, "div", class_="relation")).strip('(): ')
                          title_tag = self._safe_find(entry_div, "div", class_="title").find('a') if self._safe_find(entry_div, "div", class_="title") else None
                          name = self._get_text(title_tag)
                          url = self._get_attr(title_tag, 'href')
                          rel_id_match = re.search(r"/(?:anime|manga)/(\d+)/", url or "")
                          rel_id = self._parse_int(rel_id_match.group(1)) if rel_id_match else None
                          rel_type_guess = "Anime" if "/anime/" in (url or "") else "Manga" # Simple guess

                          if relation_type and name and url and rel_id is not None:
                               try:
                                   item = RelatedItem(mal_id=rel_id, type=rel_type_guess, name=name, url=url)
                                   if relation_type not in data['related']:
                                       data['related'][relation_type] = []
                                   data['related'][relation_type].append(item)
                               except ValidationError as e:
                                    logger.warning(f"Skipping invalid related item (div): {name}, {url}. Error: {e}")

                      # Entries in table (sometimes used for spin-offs etc.)
                      rel_table = self._safe_find(related_div, "table", class_="entries-table")
                      for row in self._safe_find_all(rel_table, "tr"):
                           cells = self._safe_find_all(row, "td")
                           if len(cells) == 2:
                                relation_type = self._get_text(cells[0]).strip(': ')
                                for link_tag in self._safe_find_all(cells[1], "li > a"): # Find links inside list items
                                     name = self._get_text(link_tag)
                                     url = self._get_attr(link_tag, 'href')
                                     # Extract type from text like "(Light Novel)"
                                     type_match = re.search(r'\(([^)]+)\)$', name)
                                     entry_type = type_match.group(1).strip() if type_match else "Unknown"
                                     clean_name = re.sub(r'\s*\([^)]+\)$', '', name).strip() # Remove type from name
                                     rel_id_match = re.search(r"/(?:manga|anime)/(\d+)/", url or "")
                                     rel_id = self._parse_int(rel_id_match.group(1)) if rel_id_match else None

                                     if relation_type and clean_name and url and rel_id is not None:
                                         try:
                                             item = RelatedItem(mal_id=rel_id, type=entry_type, name=clean_name, url=url)
                                             if relation_type not in data['related']:
                                                 data['related'][relation_type] = []
                                             data['related'][relation_type].append(item)
                                         except ValidationError as e:
                                             logger.warning(f"Skipping invalid related item (table): {name}, {url}. Error: {e}")


                 # --- Characters ---
                 data['characters'] = []
                 char_list_div = self._safe_find(right_content, "div", class_="detail-characters-list")
                 if char_list_div:
                      # Characters are in tables within two columns
                      for table_tag in self._safe_find_all(char_list_div, "table"):
                          cells = self._safe_find_all(table_tag, "td")
                          if len(cells) == 2: # Expecting image cell and info cell
                              # Image Cell (index 0)
                              img_link = self._safe_find(cells[0], "a")
                              img_tag_char = self._safe_find(img_link, "img")
                              char_img_url = self._get_attr(img_tag_char, 'data-src') or self._get_attr(img_tag_char, 'src')

                              # Info Cell (index 1)
                              name_link = self._safe_find(cells[1], "a")
                              char_name = self._get_text(name_link)
                              char_url = self._get_attr(name_link, 'href')
                              char_id = self._extract_id_from_url(char_url, r"/character/(\d+)/")
                              char_role = self._get_text(self._safe_find(cells[1], "small"))

                              if char_id is not None and char_name and char_url and char_role:
                                   try:
                                        char_item = CharacterItem(
                                            mal_id=char_id,
                                            name=char_name,
                                            url=char_url,
                                            role=char_role,
                                            image_url=char_img_url
                                        )
                                        data['characters'].append(char_item)
                                   except ValidationError as e:
                                       logger.warning(f"Skipping invalid character item: {char_name}, {char_url}. Error: {e}")


            # --- Final Validation and Return ---
            try:
                manga_details = MangaDetails(**data)
                return manga_details
            except ValidationError as e:
                logger.error(f"Pydantic validation failed for manga ID {manga_id}: {e}")
                # Optionally log the problematic data: logger.debug(f"Problematic data: {data}")
                return None

        except Exception as e:
            logger.exception(f"An unexpected error occurred within _parse_manga_details for manga ID {manga_id}: {e}")
            return None

    async def search(self, query: str, limit: int = 5) -> List[MangaSearchResult]:
        """
        Searches for manga on MyAnimeList by query, parsing the HTML table of results.
        """
        if not query:
            return []

        search_url = constants.SEARCH_MANGA_URL.format(query=query.replace(" ", "+"))
        logger.debug(f"Search for manga by URL: {search_url}")

        soup = await self._get_soup(search_url)
        
        if not soup:
            logger.warning(f"Failed to retrieve the contents of the search page for'{query}'")
            return []

        results: List[MangaSearchResult] = []
        table = soup.find("div", {"class": "js-categories-seasonal"}).find('table')
        if not table:
            logger.warning("Table with search results not found on the page.")
            return []
        rows = self._safe_select(table, "tr")

        if not rows or len(rows) < 2:
             logger.info(f"No result rows found for the query '{query}'.")
             return []

        first_row_header_check = self._safe_find(rows[0], 'td', class_='fw-b')
        if first_row_header_check:
            data_rows = rows[1:]
            logger.debug(f"Missing header line. Found {len(data_rows)} rows with data.")
        else:
            data_rows = rows
            logger.warning("The first line is not defined as a header, all lines are processed.")


        for row in data_rows:
            if len(results) >= limit:
                break

            cells = row.find_all("td")

            if len(cells) < 5:
                logger.debug(f"Line skip: {len(cells)} cells found, expected 5.")
                continue

            # Cell 0: Image
            img_tag = self._safe_find(cells[0], "img")
            image_url = self._get_attr(img_tag, 'data-src') or self._get_attr(img_tag, 'src')

            # Cell 1: Title, URL, ID, Synopsis
            title_link_tag = self._safe_find(cells[1], "a", class_="fw-b") 
            title = self._get_text(self._safe_find(title_link_tag, "strong")) 
            manga_url = self._get_attr(title_link_tag, 'href')
            mal_id = self._extract_id_from_url(manga_url, r"/manga/(\d+)/") 

            synopsis_div = self._safe_find(cells[1], "div", class_="pt4")
            raw_synopsis = self._get_text(synopsis_div)
            if raw_synopsis.endswith("read more."):
                 synopsis = raw_synopsis[:-len("read more.")].strip()
            elif self._safe_find(synopsis_div, 'a', string='read more.'): 
                 last_a = synopsis_div.find_all('a')[-1] if synopsis_div.find_all('a') else None
                 if last_a and last_a.get_text(strip=True) == 'read more.':
                    last_a.extract() 
                 synopsis = self._get_text(synopsis_div)
            else:
                 synopsis = raw_synopsis

            # Cell 2: Type
            manga_type_text = self._get_text(cells[2]).strip()
            manga_type = manga_type_text if manga_type_text != '-' else None

            # Cell 3: Toma
            volumes_text = self._get_text(cells[3]).strip()
            volumes = self._parse_int(volumes_text) 

            # Cell 4: Assessment
            score_text = self._get_text(cells[4]).strip()
            score = self._parse_float(score_text)

            # --- Assembling the result ---
            if title and manga_url: 
                result = MangaSearchResult(
                    mal_id=mal_id,
                    title=title,
                    url=manga_url,
                    image_url=image_url if image_url else None, 
                    synopsis=synopsis if synopsis else None,
                    manga_type=manga_type,
                    chapters=None,
                    volumes=volumes,
                    score=score,
                )
                results.append(result)
                logger.debug(f"Successfully extracted manga: ID={mal_id}, Title='{title}'")
            else:
                logger.warning("Line skip: failed to retrieve mandatory fields (title/URL).")

        logger.info(f"The search for '{query}' has been completed. Found {len(results)} results (limit {limit}).")
        return results
