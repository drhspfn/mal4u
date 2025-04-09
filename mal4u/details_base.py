import re
import logging
from typing import Dict, List, Optional, Tuple, Type, TypeVar, Any

from bs4 import BeautifulSoup, Tag, NavigableString
from pydantic import ValidationError, HttpUrl

from .base import BaseParser 
from .types import AnimeBroadcast, LinkItem, RelatedItem, CharacterItem, ExternalLink, BaseDetails

logger = logging.getLogger(__name__)

T_Details = TypeVar('T_Details', bound=BaseDetails)

class BaseDetailsParser(BaseParser):
    """
    Base class for parsing MAL Anime/Manga details pages.
    """

    # --- Helpers for parsing specific sections ---

    def _parse_alternative_titles(self, sidebar: Tag) -> Dict[str, Any]:
        """Parses the Alternative Titles block."""
        data = {"title_english": None, "title_synonyms": [], "title_japanese": None}
        alt_title_h2 = self._safe_find(sidebar, "h2", string="Alternative Titles")
        current_node = alt_title_h2.find_next_sibling() if alt_title_h2 else None

        while current_node and current_node.name != 'h2':
            node_classes = current_node.get('class', []) if isinstance(current_node, Tag) else []

            if isinstance(current_node, Tag) and 'spaceit_pad' in node_classes:
                dark_text_span = self._safe_find(current_node, "span", class_="dark_text")
                if dark_text_span:
                    label = self._get_text(dark_text_span).lower()
                    value = self._get_clean_sibling_text(dark_text_span)
                    if value:
                        if "synonyms:" in label:
                            data["title_synonyms"].extend([s.strip() for s in value.split(',') if s.strip()])
                        elif "japanese:" in label:
                            data["title_japanese"] = value
                        elif "english:" in label:
                            data["title_english"] = value

            # Hidden block for other languages (including English sometimes)
            elif isinstance(current_node, Tag) and 'js-alternative-titles' in node_classes:
                 # Looking for English explicitly inside the hidden block
                 english_div = current_node.find("div", class_="spaceit_pad", string=lambda t: t and "English:" in t)
                 if english_div:
                     dark_text_span = self._safe_find(english_div, "span", class_="dark_text")
                     english_title = self._get_clean_sibling_text(dark_text_span)
                     if english_title:
                          data["title_english"] = english_title 

                    #   TODO:?

            current_node = current_node.next_sibling
        return data

    def _parse_information_block(self, sidebar: Tag, item_type: str) -> Dict[str, Any]:
        """Parses the Information block (handles differences between anime/manga)."""
        data: Dict[str, Any] = {
            # Manga-specific defaults None
            "volumes": None, "chapters": None, "published_from": None,
            "published_to": None, "serialization": None, "authors": [],
            # Anime-specific default None
            "episodes": None, "aired_from": None, "aired_to": None,
            "premiered": None, "broadcast": None, "producers": [],
            "licensors": [], "studios": [], "source": None, "duration": None,
            "rating": None,
            # General
            "type": None, "status": None, "genres": [], "themes": [], "demographics": []
        }
        info_h2 = self._safe_find(sidebar, "h2", string="Information")
        current_node = info_h2.find_next_sibling() if info_h2 else None

        while current_node and current_node.name != 'h2': # Stop at Statistics
            if isinstance(current_node, Tag) and 'spaceit_pad' in current_node.get('class', []):
                 dark_text_span = self._safe_find(current_node, "span", class_="dark_text")
                 if dark_text_span:
                      label = self._get_text(dark_text_span).lower()
                      value_text = self._get_clean_sibling_text(dark_text_span)
                      parent_div = dark_text_span.parent # Parent div.spaceit_pad

                      # --- Common fields ---
                      if "type:" in label:
                           type_link = self._safe_find(parent_div, "a")
                           data['type'] = self._get_text(type_link)
                      elif "status:" in label and value_text:
                           data['status'] = value_text
                      elif "genres:" in label:
                           genre_items = self._parse_link_list(dark_text_span, pattern=r"/genre/(\d+)/")
                           data['genres'].extend(genre_items)
                      elif "genre:" in label and not data['genres']:
                           genre_items = self._parse_link_list(dark_text_span, pattern=r"/genre/(\d+)/")
                           data['genres'].extend(genre_items)
                      elif "themes:" in label:
                           data['themes'] = self._parse_link_list(dark_text_span, pattern=r"/genre/(\d+)/")
                      elif "theme:" in label and not data['themes']:
                           data['themes'] = self._parse_link_list(dark_text_span, pattern=r"/genre/(\d+)/")
                      elif "demographic:" in label:
                           data['demographics'] = self._parse_link_list(dark_text_span, pattern=r"/genre/(\d+)/")
                      elif "demographics:" in label:
                          data['demographics'] = self._parse_link_list(dark_text_span, pattern=r"/genre/(\d+)/")


                      # --- Manga-specific fields ---
                      if item_type == "manga":
                           if "volumes:" in label and value_text:
                                data['volumes'] = self._parse_int(value_text)
                           elif "chapters:" in label and value_text:
                                data['chapters'] = self._parse_int(value_text)
                           elif "published:" in label and value_text:
                                pub_from, pub_to = self._parse_mal_date_range(value_text)
                                data['published_from'] = pub_from
                                data['published_to'] = pub_to
                           elif "serialization:" in label:
                                # The links come right after span.dark_text
                                serial_links = self._parse_link_list(dark_text_span, stop_at_tag='span', pattern=r"/manga/magazine/(\d+)/")
                                if serial_links:
                                     data['serialization'] = serial_links[0] # Usually one
                           elif "authors:" in label:
                                data['authors'] = self._parse_link_list(dark_text_span, stop_at_tag='span', pattern=r"/people/(\d+)/")

                      # --- Anime-specific fields ---
                      elif item_type == "anime":
                            if "episodes:" in label and value_text:
                                 data['episodes'] = self._parse_int(value_text)
                            elif "aired:" in label and value_text:
                                 aired_from, aired_to = self._parse_mal_date_range(value_text)
                                 data['aired_from'] = aired_from
                                 data['aired_to'] = aired_to
                            elif "premiered:" in label:
                                 premiered_link = self._safe_find(parent_div, "a")
                                 name = self._get_text(premiered_link)
                                 url = self._get_attr(premiered_link, 'href')
                                 # ID for the season is not needed, just a link, maybe?
                                 if name and url:
                                     # Use LinkItem without ID
                                     try:
                                          data['premiered'] = LinkItem(mal_id=0, name=name, url=url) # ID 0 as a stub
                                     except ValidationError:
                                         logger.warning(f"Skipping invalid premiered link: {name}, {url}")
                            elif "broadcast:" in label and value_text:
                                 # "Thursdays at 22:30 (JST)"
                                 broadcast_str = value_text
                                 day = time_str = tz = None
                                 match_day = re.match(r"(\w+)", broadcast_str)
                                 if match_day: day = match_day.group(1)
                                 match_time = re.search(r"(\d{2}:\d{2})", broadcast_str)
                                 if match_time: time_str = match_time.group(1)
                                 match_tz = re.search(r"\(([^)]+)\)", broadcast_str)
                                 if match_tz: tz = match_tz.group(1)
                                 try:
                                      data['broadcast'] = AnimeBroadcast(day=day, time=time_str, timezone=tz, string=broadcast_str)
                                 except ValidationError:
                                      logger.warning(f"Could not parse broadcast string: {broadcast_str}")
                                      data['broadcast'] = AnimeBroadcast(string=broadcast_str) # Save at least a line

                            elif "producers:" in label:
                                 # ID retrieved from /anime/producer/id/Name
                                 data['producers'] = self._parse_link_list(dark_text_span, stop_at_tag='span', pattern=r"/producer/(\d+)/")
                            elif "licensors:" in label:
                                 data['licensors'] = self._parse_link_list(dark_text_span, stop_at_tag='span', pattern=r"/producer/(\d+)/")
                            elif "studios:" in label:
                                 data['studios'] = self._parse_link_list(dark_text_span, stop_at_tag='span', pattern=r"/producer/(\d+)/")
                            elif "source:" in label and value_text:
                                 data['source'] = value_text
                            elif "duration:" in label and value_text:
                                 data['duration'] = value_text
                            elif "rating:" in label and value_text:
                                 data['rating'] = value_text.strip() 


            current_node = current_node.next_sibling
        return data

    def _parse_statistics_block(self, sidebar: Tag) -> Dict[str, Any]:
        """Parses the Statistics block."""
        data = {"score": None, "scored_by": None, "rank": None, "popularity": None, "members": None, "favorites": None}
        stats_h2 = self._safe_find(sidebar, "h2", string="Statistics")
        current_node = stats_h2.find_next_sibling() if stats_h2 else None

        while current_node and current_node.name != 'h2': # Stop at next block (Available At/Resources)
            if isinstance(current_node, Tag) and ('spaceit_pad' in current_node.get('class', []) or current_node.has_attr('itemprop')): # Score иногда не в spaceit_pad
                 dark_text_span = self._safe_find(current_node, "span", class_="dark_text")
                 if dark_text_span:
                      label = self._get_text(dark_text_span).lower()
                      value_text = self._get_clean_sibling_text(dark_text_span)

                      if "score:" in label:
                           # Score/Scored_by are in the same div, often without spaceit_pad but with itemprop
                           score_container = dark_text_span.parent
                           score_val_span = self._safe_find(score_container, "span", attrs={"itemprop": "ratingValue"})
                           score_count_span = self._safe_find(score_container, "span", attrs={"itemprop": "ratingCount"})
                           # Or we can look up the score-label class
                           if not score_val_span:
                               score_val_span = self._safe_find(score_container, "span", class_=lambda x: x and x.startswith('score-')) # score-?, score-na
                           # Scored_by can be text after score_val_span
                           if score_val_span and not score_count_span:
                                score_text = self._get_text(score_val_span)
                                data['score'] = self._parse_float(score_text, default=None) # Could be 'N/A'
                                # Шукаємо 'scored by ... users'
                                score_by_match = re.search(r"scored by ([\d,]+)", score_container.text)
                                if score_by_match:
                                     data['scored_by'] = self._parse_int(score_by_match.group(1))
                           elif score_val_span and score_count_span:
                                data['score'] = self._parse_float(self._get_text(score_val_span), default=None)
                                data['scored_by'] = self._parse_int(self._get_text(score_count_span))

                      elif "ranked:" in label:
                           # Rank can be text (#123) or a link (#N/A)
                           rank_text = value_text
                           if not rank_text: # If N/A is a reference
                                rank_link = self._safe_find(dark_text_span.parent, "a")
                                rank_text = self._get_text(rank_link)

                           if rank_text and rank_text.startswith('#'):
                               # Remove # and potential <sup>...</sup>
                               rank_num_str = rank_text[1:].split('<')[0].strip()
                               data['rank'] = self._parse_int(rank_num_str)
                      elif "popularity:" in label and value_text and value_text.startswith('#'):
                           data['popularity'] = self._parse_int(value_text[1:])
                      elif "members:" in label and value_text:
                           data['members'] = self._parse_int(value_text)
                      elif "favorites:" in label and value_text:
                           data['favorites'] = self._parse_int(value_text)

            current_node = current_node.next_sibling
        return data

    def _parse_external_links(self, sidebar: Tag) -> Tuple[List[ExternalLink], Optional[HttpUrl]]:
        """Parses Available At and Resources blocks."""
        external_links = []
        official_site = None

        for header_text in ["Available At", "Resources", "Streaming Platforms"]: 
             header_h2 = self._safe_find(sidebar, "h2", string=header_text)
             if header_h2:
                  # Container can be div.external_links or div.broadcasts
                  links_container = header_h2.find_next_sibling("div", class_=["external_links", "broadcasts"])
                  if links_container:
                       for link_tag in self._safe_find_all(links_container, "a", class_=["link", "broadcast-item"]):
                            url = self._get_attr(link_tag, 'href')
                            name_div = self._safe_find(link_tag, "div", class_="caption")
                            name = self._get_text(name_div) or link_tag.get('title') or self._get_text(link_tag) # Fallback to link text

                            if name and url:
                                try:
                                     link_item = ExternalLink(name=name.strip(), url=url)
                                     external_links.append(link_item)
                                     if "official site" in name.lower() and not official_site:
                                         try:
                                             official_site = HttpUrl(url)
                                         except ValidationError:
                                              logger.warning(f"Invalid URL format for potential official site: {url}")
                                except ValidationError as e:
                                     logger.warning(f"Skipping invalid external link: Name='{name}', URL='{url}'. Error: {e}")

        return external_links, official_site


    def _parse_synopsis(self, content_area: Tag) -> Optional[str]:
        """Parses the synopsis block using the itemprop attribute."""
        synopsis_p = self._safe_find(content_area, "p", attrs={"itemprop": "description"})

        if not synopsis_p:
            logger.warning("Synopsis paragraph with itemprop='description' not found.")
            synopsis_h2 = self._safe_find(content_area, "h2", id="synopsis")
            if synopsis_h2:

                 synopsis_p_sibling = synopsis_h2.find_next_sibling("p")
                 if synopsis_p_sibling:
                      logger.info("Using fallback: Found synopsis paragraph as sibling to H2.")
                      synopsis_p = synopsis_p_sibling
                 else:
                      logger.warning("Found H2 synopsis header, but no <p> sibling found.")
                      return None 
            else:
                 logger.warning("Synopsis H2 header also not found for fallback.")
                 return None 
        else:
             logger.debug("Found synopsis paragraph using itemprop='description'.")


        synopsis_text = ""
        for element in synopsis_p.contents:
            if isinstance(element, NavigableString):
                 synopsis_text += str(element)
            elif isinstance(element, Tag):
                 if element.name == 'br':
                      synopsis_text += '\n'

                 elif element.name == 'i' and "Written by MAL Rewrite" in element.get_text():
                      continue
                 else:
                      synopsis_text += element.get_text()

        clean_synopsis = re.sub(r'\s*\[Written by MAL Rewrite\]\s*$', '', synopsis_text, flags=re.IGNORECASE).strip()
        clean_synopsis = re.sub(r'\s*Included one-shot:.*$', '', clean_synopsis, flags=re.IGNORECASE).strip()

        return clean_synopsis if clean_synopsis else None


    def _parse_background(self, content_area: Tag) -> Optional[str]:
        """Parses the background block."""
        background_h2 = content_area.find("h2", string="Background")
        if not background_h2: return None

        background_text = ""
        current_node = background_h2.next_sibling
        while current_node:
            if isinstance(current_node, Tag) and current_node.name == 'h2': break # Stop at next h2

            if isinstance(current_node, NavigableString):
                 background_text += str(current_node).strip() + " "
            elif isinstance(current_node, Tag) and current_node.name == 'br':
                 background_text += "\n"
            elif isinstance(current_node, Tag): # Text from other tags (i, b, etc.)
                 background_text += current_node.get_text(strip=True) + " "

            current_node = current_node.next_sibling

        return background_text.strip() if background_text else None

    def _parse_related(self, content_area: Tag) -> Dict[str, List[RelatedItem]]:
        """Parses the Related Entries block."""
        related_data: Dict[str, List[RelatedItem]] = {}
        related_div = self._safe_find(content_area, "div", class_="related-entries")
        if not related_div: return related_data

        # --- 1. Entries in tiles (div.entry) ---
        for entry_div in self._safe_find_all(related_div, "div", class_="entry"):
             relation_type_div = self._safe_find(entry_div, "div", class_="relation")
             title_div = self._safe_find(entry_div, "div", class_="title")
             title_link = self._safe_find(title_div, "a")

             if relation_type_div and title_link:
                  relation_type_text = self._get_text(relation_type_div).strip('(): ')
                  name = self._get_text(title_link)
                  url = self._get_attr(title_link, 'href')
                  item_id = self._extract_id_from_url(url, r"/(?:anime|manga)/(\d+)/")
                  # Определяем тип по URL
                  item_type_guess = "anime" if "/anime/" in url else "manga" if "/manga/" in url else None

                  if relation_type_text and name and url and item_id is not None and item_type_guess:
                       try:
                            item = RelatedItem(mal_id=item_id, type=item_type_guess.capitalize(), name=name, url=url)
                            if relation_type_text not in related_data:
                                 related_data[relation_type_text] = []
                            related_data[relation_type_text].append(item)
                       except ValidationError as e:
                            logger.warning(f"Skipping invalid related item (tile): Name='{name}', URL='{url}'. Error: {e}")

        # --- 2. Entries in table (table.entries-table) ---
        rel_table = self._safe_find(related_div, "table", class_="entries-table")
        for row in self._safe_find_all(rel_table, "tr"):
             cells = self._safe_find_all(row, "td")
             if len(cells) == 2:
                  relation_type_text = self._get_text(cells[0]).strip(': ')
                  for link_tag in cells[1].find_all("a"):
                       name_with_type = self._get_text(link_tag)
                       url = self._get_attr(link_tag, 'href')
                       item_id = self._extract_id_from_url(url, r"/(?:anime|manga|lightnovel|novel|./?id=)/(\d+)/") # Расширенный паттерн

                       # Extract the type from the brackets (Anime), (Light Novel), etc.
                       type_match = re.search(r'\(([^)]+)\)$', name_with_type)
                       entry_type = type_match.group(1).strip() if type_match else None
                       clean_name = re.sub(r'\s*\([^)]+\)$', '', name_with_type).strip()

                       # If the type is not in brackets, we try to guess from the URL
                       if not entry_type:
                              if "/anime/" in url: entry_type = "Anime"
                              elif "/manga/" in url: entry_type = "Manga"
                              #  TODO: Add more types here  

                       if relation_type_text and clean_name and url and item_id is not None and entry_type:
                            try:
                                item = RelatedItem(mal_id=item_id, type=entry_type, name=clean_name, url=url)
                                if relation_type_text not in related_data:
                                     related_data[relation_type_text] = []
                                related_data[relation_type_text].append(item)
                            except ValidationError as e:
                                logger.warning(f"Skipping invalid related item (table): Name='{name_with_type}', URL='{url}'. Error: {e}")
        return related_data

    def _parse_characters(self, content_area: Tag) -> List[CharacterItem]:
        """Parses the Characters & Voice Actors block."""
        characters_data = []
        char_h2 = content_area.find("h2", string=lambda t: t and "Characters & Voice Actors" in t)
        if not char_h2:
            logger.warning("Characters & Voice Actors section header not found.")
            return characters_data

        char_list_div = char_h2.find_next_sibling("div", class_="detail-characters-list")
        if not char_list_div:
            logger.warning("Character list div ('detail-characters-list') not found after header.")
            return characters_data

        for table_tag in self._safe_find_all(char_list_div, "table"):
             char_row = self._safe_find(table_tag, "tr")
             if not char_row: continue
             cells = self._safe_find_all(char_row, "td", recursive=False) 

             if len(cells) >= 2: # Expect a minimum of 2: picture+info, VA+picture VA
                  # Character info cell (usually second in line, but check)
                  info_cell = None
                  img_cell = None
                  for cell in cells:
                      if self._safe_find(cell, "h3", class_="h3_characters_voice_actors"):
                          info_cell = cell
                      elif self._safe_find(cell, "img", alt=lambda t: t and "character picture" in t.lower()):
                          img_cell = cell
                      elif self._safe_find(cell, "img"): # Backup to find a picture
                          img_cell = cell if not img_cell else img_cell 

                  if not info_cell:
     
                      if len(cells) == 2 and not self._safe_find(cells[1], "img"): 
                           info_cell = cells[0]
                           img_cell = None # A picture of a persona may not exist
                      else:
                           logger.debug(f"Skipping character table row, couldn't reliably identify info cell: {table_tag.text[:100]}...")
                           continue


                  # Retrieve data from info_cell
                  name_link = self._safe_find(info_cell, "a", href=lambda h: h and "/character/" in h)
                  char_name = self._get_text(name_link)
                  char_url = self._get_attr(name_link, 'href')
                  char_id = self._extract_id_from_url(char_url, r"/character/(\d+)/")
                  # Role is in <small> inside info_cell
                  char_role = self._get_text(self._safe_find(info_cell, "small"))

                  # Look for a character picture in img_cell or info_cell (if there is no separate img_cell)
                  char_img_url = None
                  target_img_cell = img_cell if img_cell else info_cell
                  img_link_tag = self._safe_find(target_img_cell, "a", href=lambda h: h and "/character/" in h) 
                  if img_link_tag:
                      img_tag_char = self._safe_find(img_link_tag, "img")
                      char_img_url = self._get_attr(img_tag_char, 'data-src') or self._get_attr(img_tag_char, 'src')

                  if char_id is not None and char_name and char_url and char_role:
                       try:
                            char_item = CharacterItem(
                                mal_id=char_id,
                                name=char_name,
                                url=char_url,
                                role=char_role.capitalize(), 
                                image_url=char_img_url,
                                type="character"
                            )
                            characters_data.append(char_item)
                       except ValidationError as e:
                           logger.warning(f"Skipping invalid character item: Name='{char_name}', URL='{char_url}'. Error: {e}")
                  else:
                       logger.debug(f"Skipping character entry due to missing data: ID={char_id}, Name='{char_name}', Role='{char_role}'")

        return characters_data

    def _parse_themes(self, content_area: Tag, theme_type: str) -> List[str]:
        """Parses Opening or Ending themes."""
        themes_list = []
        header_text = "Opening Theme" if theme_type == "opening" else "Ending Theme"
        theme_h2 = content_area.find("h2", string=header_text)
        if not theme_h2: return themes_list

        # Themes are in div.theme-songs after h2
        theme_div = theme_h2.find_next_sibling("div", class_="theme-songs")
        if not theme_div: return themes_list

        # Each topic is usually in a table or just text
        theme_items = theme_div.find_all(["span", "td"], class_=lambda x: x and x.startswith('theme-song-'))
        if not theme_items: # Если просто текст без классов
             # Look for text after span.theme-song-title or span.theme-song-artist
             # It's more complicated, let's try to extract all the text in the theme block
             all_text = self._get_text(theme_div)
             # Trying to divide by numbers like "1:", "2:"
             potential_themes = re.split(r'\s*\d+:\s*', all_text)
             themes_list = [theme.strip() for theme in potential_themes if theme.strip()]

        else:
            current_theme = ""
            for item in theme_items:
                text = item.get_text(strip=True)
                if "theme-song-title" in item.get('class', []):
                    if current_theme: themes_list.append(current_theme.strip())
                    current_theme = text
                elif "theme-song-artist" in item.get('class', []):
                    current_theme += f" {text}"
                elif "theme-song-episode" in item.get('class', []):
                    current_theme += f" {text}"

            if current_theme: 
                 themes_list.append(current_theme.strip())

        final_themes = []
        theme_rows = theme_div.select('tr')
        if theme_rows:
            for row in theme_rows:
                theme_text_parts = [self._get_text(span) for span in row.find_all('span') if 'theme-song' in "".join(span.get('class',[])) ]
                if theme_text_parts:
                    final_themes.append(" ".join(theme_text_parts).strip())
        elif not final_themes and themes_list: # If no tables are found, use the previous result
             final_themes = themes_list
        elif not final_themes: # If we can't find anything at all, we take the whole text
             full_text = theme_div.get_text(separator=' ', strip=True)
             cleaned_text = re.sub(r'\s+', ' ', full_text).strip()
             if cleaned_text:
                 final_themes.append(cleaned_text)

        return final_themes

    async def _parse_details_page(
        self,
        soup: BeautifulSoup,
        item_id: int,
        item_url: str,
        item_type: str, # "anime" or "manga"
        details_model: Type[T_Details]
    ) -> Optional[T_Details]:
        """
        Parses the common structure of a MAL details page (anime or manga).

        Args:
            soup: The BeautifulSoup object of the details page.
            item_id: The MAL ID of the item.
            item_url: The URL of the item's details page.
            item_type: The type of item ("anime" or "manga").
            details_model: The Pydantic model class to instantiate.

        Returns:
            An instance of details_model if successful, None otherwise.
        """
        if item_type not in ["anime", "manga"]:
            logger.error(f"Invalid item_type '{item_type}' provided to _parse_details_page.")
            return None

        try:
            data: Dict[str, Any] = {"mal_id": item_id, "url": item_url}

            # --- Main Title ---
            # h1.title-name strong OR h1 span[itemprop=name]
            title_h1 = self._safe_find(soup, "h1", class_="title-name")
            title_tag = self._safe_find(title_h1, "strong") # First priority
            if not title_tag: # Second priority
                 title_tag = self._find_nested(soup, ("h1", {"class": "title-name"}), ("span", {"itemprop": "name"}))
            if not title_tag: # Third priority (if no strong and itemprop)
                 title_tag = title_h1

            data['title'] = self._get_text(title_tag, f"Title not found for ID {item_id}")
            if not title_tag: logger.warning(f"Could not find main title tag for ID {item_id}.")

            # --- Split into left and right columns ---
            left_sidebar = self._safe_find(soup, "td", attrs={"class": "borderClass", "width": "225"})
            right_content = self._safe_find(soup, "td", attrs={"style": lambda s: s and "padding-left: 5px" in s}) 

            # === Left Sidebar ===
            if not left_sidebar:
                logger.warning(f"Could not find left sidebar for ID {item_id}. Some data might be missing.")
            else:
                 # --- Image ---
                 img_tag = self._safe_find(left_sidebar, "img", attrs={"itemprop": "image"})
                 data['image_url'] = self._get_attr(img_tag, 'data-src') or self._get_attr(img_tag, 'src') # Проверяем оба атрибута

                 # --- Alternative Titles ---
                 data.update(self._parse_alternative_titles(left_sidebar))

                 # --- Information ---
                 data.update(self._parse_information_block(left_sidebar, item_type))

                 # --- Statistics ---
                 data.update(self._parse_statistics_block(left_sidebar))

                 # --- External Links (Available At, Resources, Streaming) ---
                 external, official = self._parse_external_links(left_sidebar)
                 data['external_links'] = external
                 data['official_site'] = official
 
                 if item_type == "anime":
                      data['streaming_platforms'] = [
                          link for link in external
                          if link.url and (
                              'crunchyroll' in str(link.url) or
                              'funimation' in str(link.url) or
                              'netflix' in str(link.url) or
                              'hulu' in str(link.url) or
                              'amazon' in str(link.url) or #  can take over amazon.jp/amazon.com
                              'hidive' in str(link.url) or
                              'iq.com' in str(link.url)
                              # TODO: more?
                          )
                      ]


            # === (Content Area) ===
            if not right_content:
                 logger.warning(f"Could not find right content area for ID {item_id}. Synopsis, Background, etc. might be missing.")
            else:
                 # --- Synopsis ---
                 data['synopsis'] = self._parse_synopsis(right_content)

                 # --- Background ---
                 data['background'] = self._parse_background(right_content)

                 # --- Related Entries ---
                 data['related'] = self._parse_related(right_content)

                 # --- Characters ---
                 data['characters'] = self._parse_characters(right_content)

                 # --- Opening/Ending Themes (Anime only) ---
                 if item_type == "anime":
                      data['opening_themes'] = self._parse_themes(right_content, "opening")
                      data['ending_themes'] = self._parse_themes(right_content, "ending")


            try:
                details_object = details_model(**data)
                logger.info(f"Successfully parsed and validated details for {item_type} ID {item_id}")
                return details_object
            except ValidationError as e:
                logger.error(f"Pydantic validation failed for {item_type} ID {item_id}: {e}\nProblematic data: {data}")
                return None

        except Exception as e:
            logger.exception(f"An unexpected error occurred within _parse_details_page for {item_type} ID {item_id}: {e}")
            return None