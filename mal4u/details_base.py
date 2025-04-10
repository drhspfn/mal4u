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

    def _parse_alternative_titles(self, sidebar: Tag) -> Dict[str, Any]:
        """Parses the Alternative Titles block."""
        data = {"title_english": None,
                "title_synonyms": [], "title_japanese": None}
        # Use lambda to find header containing the text, robustness against nested divs
        alt_title_h2 = self._safe_find(
            sidebar, "h2", string=lambda t: t and "Alternative Titles" in t)
        current_node = alt_title_h2.find_next_sibling() if alt_title_h2 else None
        logger.debug("Parsing Alternative Titles...")

        while current_node and current_node.name != 'h2':
            node_classes = current_node.get(
                'class', []) if isinstance(current_node, Tag) else []

            if isinstance(current_node, Tag) and 'spaceit_pad' in node_classes:
                dark_text_span = self._safe_find(
                    current_node, "span", class_="dark_text")
                if dark_text_span:
                    label = self._get_text(dark_text_span).lower()
                    value = self._get_clean_sibling_text(dark_text_span)
                    link_value = self._get_text(self._safe_find(
                        current_node, 'a')) if not value else None
                    final_value = value or link_value

                    if final_value:
                        if "synonyms:" in label:
                            data["title_synonyms"].extend(
                                [s.strip() for s in final_value.split(',') if s.strip()])
                            logger.debug(
                                f"Found Synonyms: {data['title_synonyms']}")
                        elif "japanese:" in label:
                            data["title_japanese"] = final_value
                            logger.debug(
                                f"Found Japanese Title: {final_value}")
                        elif "english:" in label and not data["title_english"]:
                            data["title_english"] = final_value
                            logger.debug(
                                f"Found English Title (primary): {final_value}")

            elif isinstance(current_node, Tag) and 'js-alternative-titles' in node_classes:
                logger.debug("Checking hidden alternative titles block...")
                for div_spaceit in self._safe_find_all(current_node, "div", class_="spaceit_pad"):
                    dark_text_span = self._safe_find(
                        div_spaceit, "span", class_="dark_text")
                    if dark_text_span:
                        label = self._get_text(dark_text_span).lower()
                        value = self._get_clean_sibling_text(dark_text_span)
                        link_value = self._get_text(self._safe_find(
                            div_spaceit, 'a')) if not value else None
                        final_value = value or link_value
                        if "english:" in label and final_value and not data["title_english"]:
                            data["title_english"] = final_value
                            logger.debug(
                                f"Found English Title (hidden): {final_value}")

            current_node = current_node.next_sibling
        return data

    def _parse_information_block(self, sidebar: Tag, item_type: str) -> Dict[str, Any]:
        """Parses the Information block (handles differences between anime/manga)."""
        # (Keep your implementation from previous response - it looked generally okay,
        # just ensure _parse_link_list uses correct patterns and parent_limit)
        # --- Re-paste the implementation from the previous good response here ---
        data: Dict[str, Any] = {
            "volumes": None, "chapters": None, "published_from": None,
            "published_to": None, "serialization": None, "authors": [],
            "episodes": None, "aired_from": None, "aired_to": None,
            "premiered": None, "broadcast": None, "producers": [],
            "licensors": [], "studios": [], "source": None, "duration": None,
            "rating": None, "type": None, "status": None, "genres": [],
            "themes": [], "demographics": []
        }
        info_h2 = self._safe_find(sidebar, "h2", string="Information")
        current_node = info_h2.find_next_sibling() if info_h2 else None
        logger.debug(f"Parsing Information block for {item_type}...")

        while current_node and current_node.name != 'h2':
            if isinstance(current_node, Tag) and 'spaceit_pad' in current_node.get('class', []):
                dark_text_span = self._safe_find(
                    current_node, "span", class_="dark_text")
                if dark_text_span:
                    label = self._get_text(dark_text_span).lower()
                    value_text = self._get_clean_sibling_text(dark_text_span)
                    parent_div = current_node  # The div.spaceit_pad itself

                    # --- Common fields ---
                    if "type:" in label:
                        type_link = self._safe_find(parent_div, "a")
                        data['type'] = self._get_text(type_link)
                        logger.debug(f"Found Type: {data['type']}")
                    elif "status:" in label and value_text:
                        data['status'] = value_text
                        logger.debug(f"Found Status: {data['status']}")
                    elif "genres:" in label or ("genre:" in label and not data['genres']):
                        # Use specific pattern for genres/themes/demographics
                        items = self._parse_link_list(
                            dark_text_span, parent_limit=parent_div, pattern=r"/(?:anime|manga)/genre/(\d+)/")
                        data['genres'].extend(items)
                        logger.debug(
                            f"Found Genres: {[g.name for g in items]}")
                    elif "themes:" in label or ("theme:" in label and not data['themes']):
                        items = self._parse_link_list(
                            dark_text_span, parent_limit=parent_div, pattern=r"/(?:anime|manga)/genre/(\d+)/")
                        data['themes'].extend(items)
                        logger.debug(
                            f"Found Themes: {[t.name for t in items]}")
                    elif "demographics:" in label or ("demographic:" in label and not data['demographics']):
                        items = self._parse_link_list(
                            dark_text_span, parent_limit=parent_div, pattern=r"/(?:anime|manga)/genre/(\d+)/")
                        data['demographics'].extend(items)
                        logger.debug(
                            f"Found Demographics: {[d.name for d in items]}")

                    # --- Manga-specific fields ---
                    if item_type == "manga":
                        if "volumes:" in label and value_text:
                            data['volumes'] = self._parse_int(value_text)
                            logger.debug(f"Found Volumes: {data['volumes']}")
                        elif "chapters:" in label and value_text:
                            data['chapters'] = self._parse_int(value_text)
                            logger.debug(f"Found Chapters: {data['chapters']}")
                        elif "published:" in label and value_text:
                            pub_from, pub_to = self._parse_mal_date_range(
                                value_text)
                            data['published_from'] = pub_from
                            data['published_to'] = pub_to
                            logger.debug(
                                f"Found Published: {pub_from} to {pub_to}")
                        elif "serialization:" in label:
                            # Use specific pattern for magazines
                            items = self._parse_link_list(
                                dark_text_span, parent_limit=parent_div, pattern=r"/manga/magazine/(\d+)/")
                            if items:
                                data['serialization'] = items[0]
                            logger.debug(
                                f"Found Serialization: {data['serialization'].name if data['serialization'] else None}")
                        elif "authors:" in label:
                            # Use specific pattern for people
                            data['authors'] = self._parse_link_list(
                                dark_text_span, parent_limit=parent_div, pattern=r"/people/(\d+)/")
                            logger.debug(
                                f"Found Authors: {[a.name for a in data['authors']]}")

                    # --- Anime-specific fields ---
                    elif item_type == "anime":
                        if "episodes:" in label and value_text:
                            data['episodes'] = self._parse_int(value_text)
                            logger.debug(f"Found Episodes: {data['episodes']}")
                        elif "aired:" in label and value_text:
                            aired_from, aired_to = self._parse_mal_date_range(
                                value_text)
                            data['aired_from'] = aired_from
                            data['aired_to'] = aired_to
                            logger.debug(
                                f"Found Aired: {aired_from} to {aired_to}")
                        elif "premiered:" in label:
                            premiered_link = self._safe_find(parent_div, "a")
                            name = self._get_text(premiered_link)
                            url = self._get_attr(premiered_link, 'href')
                            if name and url:
                                try:
                                    # Use simpler ID extraction just for the LinkItem
                                    sid = self._extract_id_from_url(
                                        url, r'/season/(\d+)/') or 0
                                    data['premiered'] = LinkItem(
                                        mal_id=sid, name=name, url=url, type="season")
                                    logger.debug(f"Found Premiered: {name}")
                                except ValidationError:
                                    logger.warning(
                                        f"Skipping invalid premiered link: {name}, {url}")
                        elif "broadcast:" in label and value_text:
                            broadcast_str = value_text.strip()
                            day = time_str = tz = None
                            try:
                                parts = broadcast_str.split(' at ')
                                if len(parts) > 0:
                                    day_match = re.match(r"(\w+)", parts[0])
                                    if day_match:
                                        day = day_match.group(1)
                                if len(parts) > 1:
                                    time_match = re.match(
                                        r"(\d{2}:\d{2})", parts[1])
                                    if time_match:
                                        time_str = time_match.group(1)
                                    tz_match = re.search(
                                        r"\(([^)]+)\)", parts[1])
                                    if tz_match:
                                        tz = tz_match.group(1)
                                data['broadcast'] = AnimeBroadcast(
                                    day=day, time=time_str, timezone=tz, string=broadcast_str)
                                logger.debug(
                                    f"Found Broadcast: {broadcast_str}")
                            except ValidationError:
                                logger.warning(
                                    f"Could not fully parse broadcast string: {broadcast_str}, storing raw string.")
                                data['broadcast'] = AnimeBroadcast(
                                    string=broadcast_str)
                        # Use specific pattern for producers/companies
                        elif "producers:" in label:
                            data['producers'] = self._parse_link_list(
                                dark_text_span, parent_limit=parent_div, pattern=r"/anime/producer/(\d+)/")
                            logger.debug(
                                f"Found Producers: {[p.name for p in data['producers']]}")
                        elif "licensors:" in label:
                            data['licensors'] = self._parse_link_list(
                                dark_text_span, parent_limit=parent_div, pattern=r"/anime/producer/(\d+)/")
                            logger.debug(
                                f"Found Licensors: {[l.name for l in data['licensors']]}")
                        elif "studios:" in label:
                            data['studios'] = self._parse_link_list(
                                dark_text_span, parent_limit=parent_div, pattern=r"/anime/producer/(\d+)/")
                            logger.debug(
                                f"Found Studios: {[s.name for s in data['studios']]}")
                        elif "source:" in label and value_text:
                            data['source'] = value_text
                            logger.debug(f"Found Source: {data['source']}")
                        elif "duration:" in label and value_text:
                            data['duration'] = value_text
                            logger.debug(f"Found Duration: {data['duration']}")
                        elif "rating:" in label and value_text:
                            data['rating'] = value_text.strip()
                            logger.debug(f"Found Rating: {data['rating']}")

            current_node = current_node.next_sibling
        return data

    def _parse_statistics_block(self, sidebar: Tag) -> Dict[str, Any]:
        """Parses the Statistics block."""
        # (Keep your implementation from previous response - it looked generally okay)
        # --- Re-paste the implementation from the previous good response here ---
        data = {"score": None, "scored_by": None, "rank": None,
                "popularity": None, "members": None, "favorites": None}
        stats_h2 = self._safe_find(sidebar, "h2", string="Statistics")
        current_node = stats_h2.find_next_sibling() if stats_h2 else None
        logger.debug("Parsing Statistics block...")

        while current_node and current_node.name != 'h2':
            if isinstance(current_node, Tag) and ('spaceit_pad' in current_node.get('class', []) or current_node.has_attr('itemprop')):
                dark_text_span = self._safe_find(
                    current_node, "span", class_="dark_text")
                if dark_text_span:
                    label = self._get_text(dark_text_span).lower()
                    value_text = self._get_clean_sibling_text(dark_text_span)
                    value_container = dark_text_span.parent

                    if "score:" in label:
                        score_val_span = self._safe_find(value_container, "span", attrs={
                                                         "itemprop": "ratingValue"})
                        if not score_val_span:
                            score_val_span = self._safe_find(
                                value_container, "span", class_=lambda x: x and x.startswith('score-'))
                        score_count_span = self._safe_find(value_container, "span", attrs={
                                                           "itemprop": "ratingCount"})

                        if score_val_span:
                            data['score'] = self._parse_float(
                                self._get_text(score_val_span), default=None)
                            logger.debug(f"Found Score: {data['score']}")

                        if score_count_span:
                            data['scored_by'] = self._parse_int(
                                self._get_text(score_count_span))
                            logger.debug(
                                f"Found Scored By: {data['scored_by']}")
                        elif data['score'] is not None:
                            score_by_match = re.search(
                                r"scored by ([\d,]+)", value_container.get_text())
                            if score_by_match:
                                data['scored_by'] = self._parse_int(
                                    score_by_match.group(1))
                                logger.debug(
                                    f"Found Scored By (regex fallback): {data['scored_by']}")

                    elif "ranked:" in label:
                        rank_text_node = dark_text_span.next_sibling
                        rank_text = ""
                        while rank_text_node:
                            if isinstance(rank_text_node, Tag) and rank_text_node.name == 'sup':
                                rank_text_node = rank_text_node.next_sibling
                                continue
                            elif isinstance(rank_text_node, NavigableString):
                                rank_text += str(rank_text_node)
                            elif isinstance(rank_text_node, Tag) and rank_text_node.name == 'a':
                                rank_text += self._get_text(rank_text_node)
                                break
                            elif isinstance(rank_text_node, Tag):
                                break
                            rank_text_node = rank_text_node.next_sibling
                        rank_text = rank_text.strip()
                        if rank_text and rank_text.startswith('#'):
                            rank_num_str = rank_text[1:].strip()
                            data['rank'] = self._parse_int(rank_num_str)
                            logger.debug(f"Found Rank: {data['rank']}")
                        elif "N/A" in rank_text:
                            data['rank'] = None
                            logger.debug("Found Rank: N/A")

                    elif "popularity:" in label and value_text and value_text.startswith('#'):
                        data['popularity'] = self._parse_int(value_text[1:])
                        logger.debug(f"Found Popularity: {data['popularity']}")
                    elif "members:" in label and value_text:
                        data['members'] = self._parse_int(value_text)
                        logger.debug(f"Found Members: {data['members']}")
                    elif "favorites:" in label and value_text:
                        data['favorites'] = self._parse_int(value_text)
                        logger.debug(f"Found Favorites: {data['favorites']}")

            current_node = current_node.next_sibling
        return data

    def _parse_external_links(self, sidebar: Tag) -> Tuple[List[ExternalLink], Optional[HttpUrl]]:
        """Parses Available At, Resources, and Streaming Platforms blocks."""
        # (Keep implementation from previous response)
        external_links = []
        official_site = None
        logger.debug("Parsing External Links/Resources/Streaming...")

        for header_text in ["Available At", "Resources", "Streaming Platforms"]:
            header_h2 = self._safe_find(sidebar, "h2", string=header_text)
            if header_h2:
                links_container = header_h2.find_next_sibling(
                    "div", class_=["external_links", "broadcasts"])
                if links_container:
                    logger.debug(f"Found container for '{header_text}'")
                    for link_tag in self._safe_find_all(links_container, "a", class_=["link", "broadcast-item"]):
                        url = self._get_attr(link_tag, 'href')
                        name_div = self._safe_find(
                            link_tag, "div", class_="caption")
                        name = self._get_text(name_div) or link_tag.get(
                            'title') or self._get_text(link_tag)

                        if name and url:
                            try:
                                clean_name = re.sub(r'\s+', ' ', name).strip()
                                # Ensure URL is absolute
                                if url.startswith('/'):
                                    url = f"https://myanimelist.net{url}"

                                link_item = ExternalLink(
                                    name=clean_name, url=url)
                                external_links.append(link_item)
                                logger.debug(
                                    f"Found external link: {clean_name} - {url}")
                                if "official site" in clean_name.lower() and not official_site:
                                    try:
                                        official_site = HttpUrl(url)
                                        logger.debug(
                                            f"Identified official site: {url}")
                                    except ValidationError:
                                        logger.warning(
                                            f"Invalid URL format for potential official site: {url}")
                            except ValidationError as e:
                                logger.warning(
                                    f"Skipping invalid external link: Name='{name}', URL='{url}'. Error: {e}")
                        else:
                            logger.debug(
                                f"Skipping link tag in '{header_text}' block with missing name or URL.")
                else:
                    logger.debug(f"No container found for '{header_text}'")
        return external_links, official_site

    def _parse_synopsis(self, content_area: Tag) -> Optional[str]:
        """Parses the synopsis block using itemprop (span or p) or fallback H2."""
        logger.debug("Parsing Synopsis...")
        # Primary method: itemprop="description" (can be span or p)
        synopsis_tag = self._safe_find(content_area, ["p", "span"], attrs={
                                       "itemprop": "description"})

        if not synopsis_tag:
            logger.warning(
                "Synopsis tag with itemprop='description' not found. Trying fallback H2...")
            # Fallback: Find <h2> containing "Synopsis" and get the next sibling <p>
            # Use lambda to be robust against nested divs in h2
            synopsis_h2 = content_area.find(
                "h2", string=lambda t: t and "Synopsis" in t)
            if synopsis_h2:
                logger.debug("Found Synopsis H2 header for fallback.")
                current_node = synopsis_h2.next_sibling
                while current_node and not (isinstance(current_node, Tag) and current_node.name == 'p'):
                    # Check if we hit the next h2 or the background h2
                    if isinstance(current_node, Tag) and current_node.name == 'h2':
                        logger.warning(
                            "Found next H2 before finding a <p> sibling for synopsis.")
                        return None
                    current_node = current_node.next_sibling
                if isinstance(current_node, Tag) and current_node.name == 'p':
                    synopsis_tag = current_node
                    logger.info(
                        "Using fallback: Found synopsis paragraph as sibling to H2.")
                else:
                    logger.warning(
                        "Found H2 synopsis header, but no suitable <p> sibling found for fallback.")
                    return None
            else:
                logger.warning(
                    "Synopsis H2 header also not found for fallback.")
                return None
        else:
            logger.debug(
                f"Found synopsis tag using itemprop='description' (tag type: {synopsis_tag.name}).")

        # Extract text carefully
        synopsis_text_parts = []
        for element in synopsis_tag.contents:
            if isinstance(element, NavigableString):
                synopsis_text_parts.append(str(element))
            elif isinstance(element, Tag):
                if element.name == 'br':
                    synopsis_text_parts.append('\n')
                elif "Written by MAL Rewrite" in element.get_text():
                    continue
                else:
                    synopsis_text_parts.append(element.get_text())

        full_synopsis = "".join(synopsis_text_parts)
        clean_synopsis = re.sub(
            r'\s*\[Written by MAL Rewrite\]\s*$', '', full_synopsis, flags=re.IGNORECASE).strip()
        clean_synopsis = re.sub(
            r'\s*Included one-shot:.*$', '', clean_synopsis, flags=re.IGNORECASE).strip()
        clean_synopsis = re.sub(r'\s*\n\s*', '\n', clean_synopsis)
        clean_synopsis = re.sub(r' +', ' ', clean_synopsis)

        logger.info(f"Parsed Synopsis (length: {len(clean_synopsis)} chars)")
        return clean_synopsis if clean_synopsis else None

    def _parse_background(self, content_area: Tag) -> Optional[str]:
        """Parses the background block."""
        logger.debug("Parsing Background...")
        # Use lambda for robustness against nested divs in h2
        background_h2 = content_area.find(
            "h2", string=lambda t: t and "Background" in t)
        if not background_h2:
            logger.debug("Background H2 header not found.")
            return None

        background_parts = []
        current_node = background_h2.next_sibling
        while current_node:
            if isinstance(current_node, Tag) and (current_node.name == 'h2' or current_node.find("h2")):
                break
            if isinstance(current_node, Tag) and 'border_top' in current_node.get('class', []):
                break

            if isinstance(current_node, NavigableString):
                background_parts.append(str(current_node))
            elif isinstance(current_node, Tag):
                if current_node.name == 'br':
                    background_parts.append('\n')
                else:
                    background_parts.append(current_node.get_text())

            current_node = current_node.next_sibling

        full_background = "".join(background_parts)
        clean_background = re.sub(r'\s*\n\s*', '\n', full_background).strip()
        clean_background = re.sub(r' +', ' ', clean_background)

        logger.info(
            f"Parsed Background (length: {len(clean_background)} chars)")
        return clean_background if clean_background else None

    def _parse_related(self, content_area: Tag) -> Dict[str, List[RelatedItem]]:
        """Parses the Related Entries block (tiles and table)."""
        related_data: Dict[str, List[RelatedItem]] = {}
        logger.debug("Parsing Related Entries...")
        related_div = content_area.find("div", class_="related-entries")
        if not related_div:
            logger.debug("Related entries div not found.")
            return related_data

        id_pattern = r"/(?:anime|manga|lightnovel)/(\d+)/"

        # --- 1. Entries in tiles (div.entry) ---
        logger.debug("Checking for related entries in tiles...")
        for entry_div in self._safe_find_all(related_div, "div", class_="entry"):
            relation_type_div = self._safe_find(
                entry_div, "div", class_="relation")
            title_div = self._safe_find(entry_div, "div", class_="title")
            title_link = self._safe_find(title_div, "a")

            if relation_type_div and title_link:
                # --- FIX v2 START ---
                relation_raw_text = self._get_text(
                    relation_type_div)  # Get text with strip=True
                # Normalize whitespace AND strip ends
                relation_no_extra_whitespace = re.sub(
                    r'\s+', ' ', relation_raw_text).strip()
                # Remove () and : from edges *after* stripping whitespace
                
                relation_type_text = relation_no_extra_whitespace.strip('():')
                if '(' in relation_type_text and not ")" in relation_type_text:
                        relation_type_text += ")" # FIXME: weird bug - country fix
                # --- FIX v2 END ---

                name = self._get_text(title_link)
                
                url = self._get_attr(title_link, 'href')
                item_id = self._extract_id_from_url(url, pattern=id_pattern)
                item_type_match = re.search(r"/(anime|manga|lightnovel)/", url)
                item_type_guess = item_type_match.group(
                    1).capitalize() if item_type_match else None

                if relation_type_text and name and url and item_id is not None and item_type_guess:
                    try:
                        abs_url = f"https://myanimelist.net{url}" if url.startswith(
                            '/') else url
                        item = RelatedItem(
                            mal_id=item_id, type=item_type_guess, name=name, url=abs_url)
                        if relation_type_text not in related_data:
                            related_data[relation_type_text] = []
                        related_data[relation_type_text].append(item)
                        logger.debug(
                            f"Found related (tile): {relation_type_text} - {name} ({item_type_guess} ID:{item_id})")
                    except ValidationError as e:
                        logger.warning(
                            f"Skipping invalid related item (tile): Name='{name}', URL='{url}'. Error: {e}")
                else:
                    logger.debug(
                        f"Skipping related tile: Rel='{relation_type_text}', Name='{name}', URL='{url}', ID='{item_id}', Type='{item_type_guess}'")

        # --- 2. Entries in table (table.entries-table) ---
        rel_table = self._safe_find(
            related_div, "table", class_="entries-table")
        if rel_table:
            logger.debug("Checking for related entries in table...")
            for row in self._safe_find_all(rel_table, "tr"):
                cells = self._safe_find_all(row, "td")
                if len(cells) == 2:
                    # --- FIX v2 START ---
                    relation_raw_text = self._get_text(
                        cells[0])  # Get text with strip=True
                    # Normalize whitespace AND strip ends
                    relation_no_extra_whitespace = re.sub(
                        r'\s+', ' ', relation_raw_text).strip()
                    relation_type_text = relation_no_extra_whitespace.strip(':')  # Remove : from edges *after* stripping whitespace
                    if '(' in relation_type_text and not ")" in relation_type_text:
                        relation_type_text += ")"
                    # --- FIX v2 END ---

                    for link_tag in self._safe_find_all(cells[1], "a"):
                        name_with_type = self._get_text(link_tag)
                        url = self._get_attr(link_tag, 'href')
                        item_id = self._extract_id_from_url(
                            url, pattern=id_pattern)

                        type_match_brackets = re.search(
                            r'\(([^)]+)\)$', name_with_type)
                        entry_type = type_match_brackets.group(1).strip() if type_match_brackets else None
                        clean_name = re.sub(r'\s*\([^)]+\)$', '', name_with_type).strip()


                        if not entry_type:
                            item_type_match_url = re.search(
                                r"/(anime|manga|lightnovel)/", url)
                            entry_type = item_type_match_url.group(
                                1).capitalize() if item_type_match_url else None

                        if relation_type_text and clean_name and url and item_id is not None and entry_type:
                            try:
                                abs_url = f"https://myanimelist.net{url}" if url.startswith(
                                    '/') else url
                                item = RelatedItem(
                                    mal_id=item_id, type=entry_type, name=clean_name, url=abs_url)
                                if relation_type_text not in related_data:
                                    related_data[relation_type_text] = []
                                related_data[relation_type_text].append(item)
                                logger.debug(
                                    f"Found related (table): {relation_type_text} - {clean_name} ({entry_type} ID:{item_id})")
                            except ValidationError as e:
                                logger.warning(
                                    f"Skipping invalid related item (table): Name='{name_with_type}', URL='{url}'. Error: {e}")
                        else:
                            logger.debug(
                                f"Skipping related table link: Rel='{relation_type_text}', Name='{name_with_type}', URL='{url}', ID='{item_id}', Type='{entry_type}'")
        return related_data

    def _parse_characters(self, content_area: Tag) -> List[CharacterItem]:
        """Parses the Characters & Voice Actors block."""
        characters_data = []
        logger.debug("Parsing Characters...")
        # Use lambda for robustness
        char_h2 = content_area.find(
            "h2", string=lambda t: t and "Characters" in t)
        if not char_h2:
            logger.warning("Characters section header not found.")
            return characters_data

        char_list_div = char_h2.find_next_sibling(
            "div", class_="detail-characters-list")
        if not char_list_div:
            logger.warning(
                "Character list div ('detail-characters-list') not found after header.")
            return characters_data

        # Use specific pattern for character IDs
        char_id_pattern = r"/character/(\d+)/"

        for table_tag in self._safe_find_all(char_list_div, "table"):
            char_row = self._safe_find(table_tag, "tr")
            if not char_row:
                continue
            cells = self._safe_find_all(char_row, "td", recursive=False)

            if len(cells) < 2:  # Need at least image and info cell
                logger.debug(
                    f"Skipping character table row, less than 2 cells found: {table_tag.text[:50]}...")
                continue

            # Assume image is first, info is second (common structure)
            char_img_cell = cells[0]
            info_cell = cells[1]

            # Extract Character Info from info_cell
            char_link = self._safe_find(
                info_cell, "a", href=lambda h: h and "/character/" in h)
            if not char_link:
                logger.debug(
                    f"Could not find character link in info cell: {info_cell.text[:50]}...")
                continue  # Skip if no character link found in the expected cell

            char_name = self._get_text(char_link)
            char_url = self._get_attr(char_link, 'href')
            char_id = self._extract_id_from_url(
                char_url, pattern=char_id_pattern)
            char_role_tag = self._safe_find(info_cell, "small")
            char_role = self._get_text(
                char_role_tag).capitalize() if char_role_tag else "Unknown"

            # Extract Character Image from char_img_cell
            char_img_url = None
            img_tag = self._safe_find(char_img_cell, "img")
            if img_tag:
                char_img_url = self._get_attr(
                    img_tag, 'data-src') or self._get_attr(img_tag, 'src')

            if char_id is not None and char_name and char_url:
                try:
                    abs_url = f"https://myanimelist.net{char_url}" if char_url.startswith(
                        '/') else char_url
                    char_item = CharacterItem(
                        mal_id=char_id, name=char_name, url=abs_url,
                        role=char_role, image_url=char_img_url, type="character"
                    )
                    characters_data.append(char_item)
                    logger.debug(
                        f"Found character: {char_name} (ID: {char_id}, Role: {char_role})")
                except ValidationError as e:
                    logger.warning(
                        f"Skipping invalid character item: Name='{char_name}', URL='{char_url}'. Error: {e}")
            else:
                logger.debug(
                    f"Skipping character entry due to missing data: ID={char_id}, Name='{char_name}', Role='{char_role}'")

        return characters_data

    def _parse_themes(self, content_area: Tag, theme_type: str) -> List[str]:
        """Parses Opening or Ending themes (Anime only)."""
        # (Keep your implementation from previous response - it looked okay)
        # --- Re-paste the implementation from the previous good response here ---
        themes_list = []
        header_text = "Opening Theme" if theme_type == "opening" else "Ending Theme"
        theme_h2 = content_area.find("h2", string=header_text)
        if not theme_h2:
            logger.debug(f"{header_text} section header not found.")
            return themes_list
        logger.debug(f"Parsing {header_text}s...")
        theme_div = theme_h2.find_next_sibling("div", class_="theme-songs")
        if not theme_div:
            logger.debug(
                f"Theme songs div not found after {header_text} header.")
            return themes_list

        theme_rows = theme_div.select('tr')
        if theme_rows:
            logger.debug(f"Found {len(theme_rows)} theme rows in table.")
            for row in theme_rows:
                tds = row.find_all('td', recursive=False)
                text_cell = tds[1] if len(
                    tds) > 1 else tds[0] if len(tds) == 1 else None
                if text_cell:
                    theme_parts = [self._get_text(span) for span in text_cell.find_all(
                        'span', class_=lambda x: x and x.startswith('theme-song-'))]
                    full_theme_string = " ".join(
                        part for part in theme_parts if part).strip()
                    if full_theme_string:
                        # Clean up potential extra spaces from joining parts
                        full_theme_string = re.sub(
                            r'\s{2,}', ' ', full_theme_string)
                        themes_list.append(full_theme_string)
                        logger.debug(
                            f"Parsed theme from table: {full_theme_string}")

        if not themes_list:
            logger.debug(
                "No themes found in table, trying fallback text extraction.")
            all_text = theme_div.get_text(separator='\n', strip=True)
            potential_themes = re.split(r'\n\s*\d+:\s*|\n', all_text)
            themes_list = [re.sub(r'\s{2,}', ' ', theme).strip()
                           for theme in potential_themes if theme.strip()]
            if themes_list:
                logger.debug(
                    f"Parsed themes using fallback text split: {themes_list}")
            else:
                logger.warning(
                    f"Could not parse any themes from {header_text} block.")

        return themes_list

    async def _parse_details_page(
        self,
        soup: BeautifulSoup,
        item_id: int,
        item_url: str,
        item_type: str,  # "anime" or "manga"
        details_model: Type[T_Details]
    ) -> Optional[T_Details]:
        """
        Parses the common structure of a MAL details page (anime or manga).
        """
        if item_type not in ["anime", "manga"]:
            logger.error(f"Invalid item_type '{item_type}' provided.")
            return None

        logger.info(
            f"Starting parsing for {item_type} ID {item_id} at {item_url}")
        data: Dict[str, Any] = {"mal_id": item_id, "url": item_url}

        try:
            # --- Main Title ---
            # Find h1, then look for spans within it, prioritize itemprop, then use h1 text directly if needed
            title_h1 = self._safe_find(
                soup, "h1", class_=lambda c: c and 'title-name' in c or 'h1' in c)  # Find h1 flexibly
            title_tag = None
            if title_h1:
                # Case 1: h1 > span.h1-title > span[itemprop=name] (like manga page)
                title_tag = self._find_nested(
                    title_h1, ("span", {"class": "h1-title"}), ("span", {"itemprop": "name"}))
                # Case 2: h1 > strong (older style?)
                if not title_tag:
                    title_tag = self._safe_find(title_h1, "strong")
                # Case 3: Direct text in h1 or first relevant span if no itemprop/strong
                if not title_tag:
                    title_tag = title_h1

            data['title'] = self._get_text(
                title_tag, f"Unknown Title (ID: {item_id})").strip()  # Ensure stripping
            if not title_tag or data['title'] == f"Unknown Title (ID: {item_id})":
                logger.error(
                    f"Could not find main title tag/text for ID {item_id}.")
            logger.info(f"Found Title: {data['title']}")

            # --- Split into left and right columns ---
            left_sidebar = self._safe_find(
                soup, "td", class_="borderClass", width="225")
            right_content = soup.find(
                "td", style=lambda s: s and "padding-left: 5px" in s)

            # === Left Sidebar Parsing ===
            if not left_sidebar:
                logger.warning(
                    f"Could not find left sidebar for ID {item_id}. Some data will be missing.")
            else:
                logger.debug("Processing left sidebar...")
                img_tag_link = self._safe_find(
                    left_sidebar, "a", href=lambda h: h and "/pics" in h)
                img_tag = self._safe_find(
                    img_tag_link, "img", attrs={"itemprop": "image"})
                if not img_tag:
                    img_tag = self._safe_find(
                        left_sidebar, "img", attrs={"itemprop": "image"})

                if img_tag:
                    data['image_url'] = self._get_attr(
                        img_tag, 'data-src') or self._get_attr(img_tag, 'src')
                    logger.debug(f"Found Image URL: {data['image_url']}")
                else:
                    logger.warning("Could not find main image tag.")

                data.update(self._parse_alternative_titles(left_sidebar))
                data.update(self._parse_information_block(
                    left_sidebar, item_type))
                data.update(self._parse_statistics_block(left_sidebar))
                external, official = self._parse_external_links(left_sidebar)
                data['external_links'] = external
                data['official_site'] = official

                if item_type == "anime":
                    data['streaming_platforms'] = [
                        link for link in external if any(
                            platform in str(link.url).lower()
                            for platform in ['crunchyroll', 'funimation', 'netflix', 'hulu', 'amazon', 'hidive', 'iq.com', 'animax', 'bahamut']
                        )
                    ]
                    logger.debug(
                        f"Found {len(data['streaming_platforms'])} potential streaming platforms.")

            # === Right Content Area Parsing ===
            if not right_content:
                logger.warning(
                    f"Could not find right content area for ID {item_id}. Main content will be missing.")
            else:
                logger.debug("Processing right content area...")
                data['synopsis'] = self._parse_synopsis(right_content)
                data['background'] = self._parse_background(right_content)
                data['related'] = self._parse_related(right_content)
                data['characters'] = self._parse_characters(right_content)

                if item_type == "anime":
                    data['opening_themes'] = self._parse_themes(
                        right_content, "opening")
                    data['ending_themes'] = self._parse_themes(
                        right_content, "ending")

            # --- Final Validation and Object Creation ---
            try:
                # Clean up potential None values Pydantic might not like if not Optional
                # (Though defaults should handle this, belt-and-suspenders)
                cleaned_data = {k: v for k, v in data.items(
                ) if v is not None or k in details_model.model_fields and details_model.model_fields[k].is_required() is False}

                details_object = details_model(**cleaned_data)
                logger.info(
                    f"Successfully parsed and validated details for {item_type} ID {item_id}: {details_object.title}")
                return details_object
            except ValidationError as e:
                error_details = e.errors()
                problematic_fields = {err['loc'][0]: data.get(
                    err['loc'][0], '<Field Missing>') for err in error_details if err['loc']}
                logger.error(f"Pydantic validation failed for {item_type} ID {item_id}: {e}\n"
                             f"Problematic fields data: {problematic_fields}")
                return None

        except Exception as e:
            logger.exception(
                f"A critical unexpected error occurred during parsing for {item_type} ID {item_id}: {e}")
            return None


    