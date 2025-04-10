import asyncio
from collections import defaultdict
from datetime import date, time
from math import ceil
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlencode
import aiohttp
import logging
from pydantic import ValidationError
from bs4 import Tag
from mal4u.details_base import BaseDetailsParser
from mal4u.types import LinkItem
from ..search_base import BaseSearchParser
from .. import constants
from .types import AnimeDetails, AnimeSearchResult, ScheduleAnimeItem, SeasonalAnimeItem, TopAnimeItem
from . import constants as animeConstants


logger = logging.getLogger(__name__)


class MALAnimeParser(BaseSearchParser, BaseDetailsParser):
    def __init__(self, session: aiohttp.ClientSession):
        super().__init__(session)
        logger.info("Anime parser initialized")

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

    # -------------------
    async def seasonal(
        self,
        year: int = 2025,
        season: constants.Season = constants.Season.SPRING,
        anime_type: Optional[animeConstants.AnimeType] = None,
        include_genres: Optional[List[int]] = None,
        exclude_genres: Optional[List[int]] = None,
    ) -> Union[List[SeasonalAnimeItem], Dict[animeConstants.AnimeType, List[SeasonalAnimeItem]]]:
        """
        Fetches and parses anime for a specific season.

        Args:
            year: The year of the season.
            season: The season (WINTER, SPRING, SUMMER, FALL).
            anime_type: Optional filter to return only anime of a specific type.
                        If None, returns a dictionary mapping AnimeType to a list of anime.
            include_genres: Optional list of genre MAL IDs to include. Anime must have ALL specified genres.
            exclude_genres: Optional list of genre MAL IDs to exclude. Anime must have NONE of the specified genres.

        Returns:
            If anime_type is specified, a list of SeasonalAnimeItem matching the criteria.
            If anime_type is None, a dictionary where keys are AnimeType enums and values are lists
            of SeasonalAnimeItem matching the genre filters for that type.
            Returns an empty list/dict if the page fails to load or no anime are found/match.
        """
        if anime_type and not anime_type in {
            animeConstants.AnimeType.TV,
            animeConstants.AnimeType.ONA,
            animeConstants.AnimeType.OVA,
            animeConstants.AnimeType.MOVIE,
            animeConstants.AnimeType.TV_SPECIAL
        }:
            raise ValueError(
                f"Invalid anime_type {anime_type}. Must be one of [TV, ONA, OVA, MOVIE, TV_SPECIAL]")

        endpoint = constants.ANIME_SEASONAL_URL.format(
            year=year, season=season.value)
        soup = await self._get_soup(endpoint)

        if not soup:
            logger.error(
                f"Could not fetch seasonal page for {season.value} {year}")
            return [] if anime_type is not None else {}

        all_anime_tags = self._safe_find_all(
            soup, 'div', class_='seasonal-anime')
        logger.info(
            f"Found {len(all_anime_tags)} potential anime entries on the page for {season.value} {year}.")

        parsed_anime: List[SeasonalAnimeItem] = []
        results = [self._parse_seasonal_anime_entry(
            tag, year, season) for tag in all_anime_tags]
        parsed_anime = [item for item in results if item is not None]
        logger.info(f"Successfully parsed {len(parsed_anime)} anime entries.")

        filtered_by_genre = parsed_anime
        # Apply include_genres filter
        if include_genres:
            include_set = set(include_genres)
            filtered_by_genre = [
                item for item in filtered_by_genre
                if include_set.issubset(item.all_genre_ids)
            ]
            logger.debug(
                f"Filtered down to {len(filtered_by_genre)} after including genres: {include_genres}")

        # Apply exclude_genres filter
        if exclude_genres:
            exclude_set = set(exclude_genres)
            filtered_by_genre = [
                item for item in filtered_by_genre
                if exclude_set.isdisjoint(item.all_genre_ids)
            ]
            logger.debug(
                f"Filtered down to {len(filtered_by_genre)} after excluding genres: {exclude_genres}")

        # --- Final Output Formatting ---
        if anime_type is not None:
            # Filter for a specific type *after* genre filtering
            final_list = [
                item for item in filtered_by_genre if item.type == anime_type
            ]
            logger.info(
                f"Returning {len(final_list)} anime of type {anime_type.name} for {season.value} {year} after genre filters.")
            return final_list
        else:
            # Group the genre-filtered list by type
            grouped_anime: Dict[animeConstants.AnimeType,
                                List[SeasonalAnimeItem]] = defaultdict(list)
            for item in filtered_by_genre:
                grouped_anime[item.type].append(item)

            # Sort by enum value for consistent output order
            final_grouped = dict(
                sorted(grouped_anime.items(), key=lambda pair: pair[0].value))
            logger.info(
                f"Returning grouped anime for {season.value} {year} after genre filters. Types found: {[t.name for t in final_grouped.keys()]}")
            return final_grouped

    async def schedule(
        self,
        week_day: Optional[Union[constants.DayOfWeek, List[constants.DayOfWeek]]] = None,
        include_genres: Optional[List[int]] = None,
        exclude_genres: Optional[List[int]] = None,
    ) -> Union[List[ScheduleAnimeItem], Dict[constants.DayOfWeek, List[ScheduleAnimeItem]]]:
        """
        Fetches and parses the MAL anime schedule page.

        Args:
            week_day: Optional day or list of days to filter by.
            include_genres: Optional list of genre MAL IDs to include.
            exclude_genres: Optional list of genre MAL IDs to exclude.

        Returns:
            Filtered list or dictionary of ScheduleAnimeItem based on week_day input.
        """
        soup = await self._get_soup(constants.ANIME_SCHEDULE_URL)
        if not soup:
            logger.error("Could not fetch anime schedule page")
            # Match return type hint
            return [] if isinstance(week_day, constants.DayOfWeek) else {}

        schedule_container = self._safe_find(
            soup, 'div', class_='js-categories-seasonal')
        if not schedule_container:
            logger.warning(
                "Could not find main schedule container 'div.js-categories-seasonal'")
            return [] if isinstance(week_day, constants.DayOfWeek) else {}

        all_anime_by_day: Dict[constants.DayOfWeek,
                               List[ScheduleAnimeItem]] = defaultdict(list)

        day_sections = self._safe_find_all(
            schedule_container, 'div', class_=lambda c: c and 'js-seasonal-anime-list-key-' in c)
        logger.info(
            f"Found {len(day_sections)} day sections on the schedule page.")

        for section in day_sections:
            day_key = None
            classes = section.get('class', [])
            for cls in classes:
                if cls.startswith('js-seasonal-anime-list-key-'):
                    day_key = cls.replace(
                        'js-seasonal-anime-list-key-', '').lower()
                    break

            if not day_key:
                logger.warning(
                    "Could not extract day key from section classes: {classes}")
                continue

            try:
                current_day = constants.DayOfWeek(day_key)
            except ValueError:
                logger.warning(
                    f"Unknown day key found: {day_key}, mapping to UNKNOWN")
                current_day = constants.DayOfWeek.UNKNOWN

            anime_tags_in_section = self._safe_find_all(
                section, 'div', class_='seasonal-anime')
            for tag in anime_tags_in_section:
                parsed_item = self._parse_anime_card_for_schedule(
                    tag)  # Use the schedule-specific parser
                if parsed_item:
                    all_anime_by_day[current_day].append(parsed_item)
            logger.debug(
                f"Parsed {len(anime_tags_in_section)} entries for {current_day.value}")

        # --- Client-side Genre Filtering ---
        filtered_anime_by_day: Dict[constants.DayOfWeek,
                                    List[ScheduleAnimeItem]] = defaultdict(list)
        include_set = set(include_genres) if include_genres else set()
        exclude_set = set(exclude_genres) if exclude_genres else set()

        for day, anime_list in all_anime_by_day.items():
            filtered_list = anime_list
            if include_genres:
                filtered_list = [
                    item for item in filtered_list if include_set.issubset(item.all_genre_ids)]
            if exclude_genres:
                filtered_list = [
                    item for item in filtered_list if exclude_set.isdisjoint(item.all_genre_ids)]
            if filtered_list:  # Only add day if it has matching anime after filtering
                filtered_anime_by_day[day] = filtered_list

        # --- Return based on week_day input ---
        if week_day is None:
            # Return all days (after genre filtering)
            final_dict = dict(sorted(filtered_anime_by_day.items(), key=lambda pair: list(
                constants.DayOfWeek).index(pair[0])))  # Sort by Enum order
            logger.info(
                f"Returning full schedule. Days with matching anime: {[d.name for d in final_dict.keys()]}")
            return final_dict
        elif isinstance(week_day, constants.DayOfWeek):
            # Return only the list for the specified day
            day_list = filtered_anime_by_day.get(week_day, [])
            logger.info(
                f"Returning schedule for {week_day.name}. Found {len(day_list)} matching anime.")
            return day_list
        elif isinstance(week_day, list):
            # Return a dict containing only the requested days
            result_dict: Dict[constants.DayOfWeek,
                              List[ScheduleAnimeItem]] = {}
            requested_days = set(week_day)
            for day_enum in constants.DayOfWeek:  # Iterate in enum order
                if day_enum in requested_days and day_enum in filtered_anime_by_day:
                    result_dict[day_enum] = filtered_anime_by_day[day_enum]
            logger.info(
                f"Returning schedule for days: {[d.name for d in week_day]}. Found anime for: {[d.name for d in result_dict.keys()]}")
            return result_dict
        else:
            logger.warning(
                f"Invalid type for week_day parameter: {type(week_day)}")
            return {}  # Or raise error

    def _parse_properties(self, properties_div: Optional[Tag]) -> Dict[str, Any]:
        """Parses the 'properties' div for studios, source, themes, demographics."""
        data: Dict[str, Any] = {
            "studios": [], "source": None, "themes": [], "demographics": []
        }
        if not properties_div:
            return data
        prop_divs = self._safe_find_all(
            properties_div, 'div', class_='property')
        for prop_div in prop_divs:
            caption_tag = self._safe_find(prop_div, 'span', class_='caption')
            caption = self._get_text(
                caption_tag).lower().strip().replace(':', '')
            item_tags = self._safe_find_all(prop_div, 'span', class_='item')
            # Find all links within the property div
            links = self._safe_find_all(prop_div, 'a')

            if caption == 'studio' or caption == 'studios':
                data['studios'] = self._parse_links_from_list(
                    links, constants.PRODUCER_ID_PATTERN, "producer")
            elif caption == 'source':
                if item_tags:
                    data['source'] = self._get_text(item_tags[0])
            elif caption == 'theme' or caption == 'themes':
                data['themes'] = self._parse_links_from_list(
                    links, constants.GENRE_ID_PATTERN, "genre")
            elif caption == 'demographic' or caption == 'demographics':
                data['demographics'] = self._parse_links_from_list(
                    links, constants.GENRE_ID_PATTERN, "genre")
        return data

    def _parse_episodes_duration(self, info_text: str) -> Tuple[Optional[int], Optional[int]]:
        """Parses 'X eps, Y min' string."""
        episodes = None
        duration = None

        # Regex to find episodes and duration
        # Allows for "? eps" and "Unknown min" or just one part present
        eps_match = re.search(r"(\?|\d+)\s+eps?", info_text, re.IGNORECASE)
        dur_match = re.search(r"(\?|\d+|Unknown)\s+min",
                              info_text, re.IGNORECASE)

        if eps_match:
            eps_str = eps_match.group(1)
            if eps_str != '?':
                episodes = self._parse_int(eps_str)

        if dur_match:
            dur_str = dur_match.group(1)
            if dur_str.lower() != 'unknown' and dur_str != '?':
                duration = self._parse_int(dur_str)

        return episodes, duration

    def _parse_seasonal_anime_entry(self, anime_tag: Tag, year: int, season: constants.Season) -> Optional[SeasonalAnimeItem]:
        """Parses a single anime entry div from the seasonal page."""
        try:
            # --- MAL ID ---
            # Primary source: data-genre attribute's id (e.g., <div class="genres js-genre" id="61224">)
            genre_div = self._safe_find(anime_tag, 'div', class_='js-genre')
            mal_id_str = self._get_attr(genre_div, 'id') if genre_div else None
            mal_id = self._parse_int(mal_id_str)

            # Fallback source: Title link href
            if mal_id is None:
                title_link = self._find_nested(
                    anime_tag, ('div', {'class': 'title'}), 'h2', 'a')
                url_fallback = self._get_attr(title_link, 'href')
                mal_id = self._extract_id_from_url(url_fallback)

            if mal_id is None:
                logger.error("Could not extract MAL ID from entry. Skipping.")
                return None

            # --- Title & URL ---
            title_link = self._find_nested(
                anime_tag, ('div', {'class': 'title'}), 'h2', 'a')
            title = self._get_text(title_link)
            url = self._get_attr(title_link, 'href')
            if not title or not url:
                logger.warning(
                    f"Could not parse title or URL for MAL ID {mal_id}. Skipping.")
                return None

            # --- Genre IDs from data-genre ---
            all_genre_ids: Set[int] = set()
            data_genre_str = self._get_attr(anime_tag, 'data-genre')
            if data_genre_str:
                all_genre_ids = {
                    int(gid) for gid in data_genre_str.split(',') if gid.isdigit()}

            # --- Image URL ---
            img_tag = self._find_nested(
                anime_tag, ('div', {'class': 'image'}), 'a', 'img')
            image_url_srcset = self._get_attr(
                img_tag, 'data-srcset') or self._get_attr(img_tag, 'srcset')
            image_url_src = self._get_attr(
                img_tag, 'data-src') or self._get_attr(img_tag, 'src')
            image_url = None
            if image_url_srcset:
                parts = image_url_srcset.split(',')
                last_part = parts[-1].strip()
                image_url = last_part.split(' ')[0]
            if not image_url and image_url_src:
                image_url = image_url_src
            if not image_url:
                logger.debug(
                    f"Could not find image URL for {title} ({mal_id}).")

            # --- Synopsis ---
            synopsis_p = self._find_nested(
                anime_tag, ('div', {'class': 'synopsis'}), ('p', {'class': 'preline'}))
            synopsis = self._get_text(synopsis_p) if synopsis_p else None

            # --- Type ---
            anime_type = animeConstants.AnimeType.UNKNOWN
            type_class = next((cls for cls in anime_tag.get('class', []) if cls.startswith(
                'js-anime-type-') and cls.split('-')[-1].isdigit()), None)
            if type_class:
                type_id = int(type_class.split('-')[-1])
                anime_type = animeConstants.AnimeType(type_id)
            else:
                logger.warning(
                    f"Could not determine anime type from classes for {title} ({mal_id})")

            # --- Continuing Status ---
            parent_list = anime_tag.find_parent(
                'div', class_='js-seasonal-anime-list')
            continuing = False
            if parent_list:
                header_tag = parent_list.find_previous_sibling(
                    'div', class_='anime-header')
                header_text = self._get_text(header_tag).lower()
                if 'continuing' in header_text:
                    continuing = True

            # --- Episodes & Duration & Start Date ---
            info_divs = self._safe_find_all(self._safe_find(
                anime_tag, 'div', class_='prodsrc'), 'div', class_='info')
            episodes = None
            duration_min_per_ep = None
            start_date = None
            for info_div in info_divs:  # Should only be one, but loop just in case
                info_items = self._safe_find_all(
                    info_div, 'span', class_='item')
                if len(info_items) >= 1:
                    date_text = self._get_text(info_items[0])
                    parsed_date, _ = self._parse_mal_date_range(date_text)
                    if parsed_date:
                        start_date = parsed_date
                if len(info_items) >= 2:
                    eps_dur_text = self._get_text(info_items[1])
                    episodes, duration_min_per_ep = self._parse_episodes_duration(
                        eps_dur_text)
                # Break if we found both date and eps/dur info, assuming standard structure
                if start_date and (episodes is not None or duration_min_per_ep is not None):
                    break

            # --- Score & Members ---
            score_tag = self._find_nested(anime_tag, ('div', {'class': 'information'}), ('div', {
                                          'class': 'scormem'}), ('div', {'class': 'scormem-container'}), ('div', {'class': 'scormem-item score'}))
            score_text = self._get_text(score_tag).replace(
                "N/A", "").strip() if score_tag else ""
            # Handle N/A explicitly for score
            score = self._parse_float(
                score_text) if score_text and score_text != 'N/A' else None

            members_tag = self._find_nested(anime_tag, ('div', {'class': 'information'}), ('div', {
                                            'class': 'scormem'}), ('div', {'class': 'scormem-container'}), ('div', {'class': 'member'}))
            members_text = self._get_text(members_tag)
            members = self._parse_int(members_text)

            # --- Genres (Visible Links) ---
            genres_visible: List[LinkItem] = []
            if genre_div:
                genre_inner_div = self._safe_find(
                    genre_div, 'div', class_='genres-inner')
                if genre_inner_div:
                    genre_links = self._safe_find_all(genre_inner_div, 'a')
                    genres_visible = self._parse_links_from_list(
                        genre_links, constants.GENRE_ID_PATTERN, "genre")

            # --- Properties (Studios, Source, Themes, Demographics - Visible Links) ---
            properties_div = self._safe_find(
                anime_tag, 'div', class_='properties')
            properties_data = self._parse_properties(properties_div)

            anime_data = {
                "mal_id": mal_id,
                "url": url,
                "title": title,
                "image_url": image_url,
                "synopsis": synopsis,
                "type": anime_type,
                "start_date": start_date,
                "episodes": episodes,
                "duration_min_per_ep": duration_min_per_ep,
                "genres": genres_visible,  # Use explicitly listed genres here
                "themes": properties_data.get('themes', []),
                "demographics": properties_data.get('demographics', []),
                "all_genre_ids": all_genre_ids,  # Store all IDs from data-genre
                "studios": properties_data.get('studios', []),
                "source": properties_data.get('source'),
                "score": score,
                "members": members,
                "season_year": year,
                "season_name": season.value,
                "continuing": continuing,
            }
            return SeasonalAnimeItem(**anime_data)

        except ValidationError as e:
            logger.error(
                f"Pydantic validation failed for anime data ({title} - ID:{mal_id}): {e}")
            return None
        except Exception as e:
            logger.exception(
                f"Failed to parse anime entry ({title} - ID:{mal_id}): {e}")
            return None

    def _parse_anime_card_for_schedule(self, anime_tag: Tag) -> Optional[ScheduleAnimeItem]:
        """Parses a single anime entry div specifically for the schedule page."""
        try:
            # --- MAL ID, Title, URL (same as seasonal) ---
            genre_div = self._safe_find(anime_tag, 'div', class_='js-genre')
            mal_id_str = self._get_attr(genre_div, 'id') if genre_div else None
            mal_id = self._parse_int(mal_id_str)
            if mal_id is None:
                title_link_fallback = self._find_nested(
                    anime_tag, ('div', {'class': 'title'}), 'h2', 'a')
                url_fallback = self._get_attr(title_link_fallback, 'href')
                mal_id = self._extract_id_from_url(url_fallback)
            if mal_id is None:
                logger.error(
                    "Could not extract MAL ID from schedule entry. Skipping.")
                return None

            title_link = self._find_nested(
                anime_tag, ('div', {'class': 'title'}), 'h2', 'a')
            title = self._get_text(title_link)
            url = self._get_attr(title_link, 'href')
            if not title or not url:
                logger.warning(
                    f"Could not parse title or URL for schedule MAL ID {mal_id}. Skipping.")
                return None

            # --- Genre IDs from data-genre (same as seasonal) ---
            all_genre_ids: Set[int] = set()
            data_genre_str = self._get_attr(anime_tag, 'data-genre')
            if data_genre_str:
                all_genre_ids = {
                    int(gid) for gid in data_genre_str.split(',') if gid.isdigit()}

            # --- Image URL (same as seasonal) ---
            img_tag = self._find_nested(
                anime_tag, ('div', {'class': 'image'}), 'a', 'img')
            image_url_srcset = self._get_attr(
                img_tag, 'data-srcset') or self._get_attr(img_tag, 'srcset')
            image_url_src = self._get_attr(
                img_tag, 'data-src') or self._get_attr(img_tag, 'src')
            image_url = None
            if image_url_srcset:
                parts = image_url_srcset.split(',')
                last_part = parts[-1].strip()
                image_url = last_part.split(' ')[0]
            if not image_url and image_url_src:
                image_url = image_url_src
            if not image_url:
                logger.debug(
                    f"Could not find image URL for {title} ({mal_id}).")

            # --- Synopsis (same as seasonal) ---
            synopsis_p = self._find_nested(
                anime_tag, ('div', {'class': 'synopsis'}), ('p', {'class': 'preline'}))
            synopsis = self._get_text(synopsis_p) if synopsis_p else None

            # --- Type (same as seasonal) ---
            anime_type = animeConstants.AnimeType.UNKNOWN
            type_class = next((cls for cls in anime_tag.get('class', []) if cls.startswith(
                'js-anime-type-') and cls.split('-')[-1].isdigit()), None)
            if type_class:
                type_id = int(type_class.split('-')[-1])
                anime_type = animeConstants.AnimeType(type_id)
            else:
                logger.warning(
                    f"Could not determine anime type from classes for {title} ({mal_id})")

            # --- Airing Time & Next Episode (Specific to Schedule) ---
            airing_time_jst: Optional[time] = None
            next_episode_num: Optional[int] = None
            prodsrc_div = self._safe_find(anime_tag, 'div', class_='prodsrc')
            if prodsrc_div:
                # Usually the first span in the 'info' div is the time
                info_div = self._safe_find(prodsrc_div, 'div', class_='info')
                if info_div:
                    print('info_div: ', info_div)
                    # Class might differ slightly
                    time_tag = self._safe_find(
                        info_div, 'span', class_='item broadcast-item')
                    if time_tag:
                        print('time_tag: ', time_tag, self._get_text(time_tag))
                        airing_time_jst = self._parse_time_jst(
                            self._get_text(time_tag))
                    # Sometimes the episode number is in the title div
                    episode_span = self._find_nested(
                        anime_tag, ('div', {'class': 'title'}), ('span', {'class': 'js-title'}))
                    ep_num_match = re.search(
                        r'#(\d+)', self._get_text(episode_span))
                    if ep_num_match:
                        next_episode_num = self._parse_int(
                            ep_num_match.group(1))

            # --- Score & Members (same as seasonal) ---
            score_tag = self._find_nested(anime_tag, ('div', {'class': 'information'}), ('div', {
                                          'class': 'scormem'}), ('div', {'class': 'scormem-container'}), ('div', {'class': 'scormem-item score'}))
            score_text = self._get_text(score_tag).replace(
                "N/A", "").strip() if score_tag else ""
            score = self._parse_float(
                score_text) if score_text and score_text != 'N/A' else None

            members_tag = self._find_nested(anime_tag, ('div', {'class': 'information'}), ('div', {
                                            'class': 'scormem'}), ('div', {'class': 'scormem-container'}), ('div', {'class': 'member'}))
            members_text = self._get_text(members_tag)
            members = self._parse_int(members_text)

            # --- Genres (Visible Links - same as seasonal) ---
            genres_visible: List[LinkItem] = []
            if genre_div:
                genre_inner_div = self._safe_find(
                    genre_div, 'div', class_='genres-inner')
                if genre_inner_div:
                    genre_links = self._safe_find_all(genre_inner_div, 'a')
                    genres_visible = self._parse_links_from_list(
                        genre_links, constants.GENRE_ID_PATTERN, "genre")

            # --- Properties (Studios, Source, Themes, Demographics - same as seasonal) ---
            properties_div = self._safe_find(
                anime_tag, 'div', class_='properties')
            properties_data = self._parse_properties(properties_div)

            # --- Start Date (Original start date, same as seasonal) ---
            # Note: This might be less useful for schedule, but it's parsed
            start_date_str = self._get_attr(self._safe_find(
                anime_tag, 'span', class_='js-start_date'), 'text')
            start_date = None
            # The start date isn't directly in a span with class 'js-start_date' in the schedule HTML provided earlier.
            # It's within the 'info' section. Let's reuse the logic from seasonal parsing.
            info_divs_sd = self._safe_find_all(self._safe_find(
                anime_tag, 'div', class_='prodsrc'), 'div', class_='info')
            for info_div_sd in info_divs_sd:
                info_items_sd = self._safe_find_all(
                    info_div_sd, 'span', class_='item')
                if len(info_items_sd) >= 1:
                    date_text_sd = self._get_text(info_items_sd[0])
                    # Check if it's a date, not the time
                    if re.search(r'\w{3}\s+\d{1,2},\s+\d{4}', date_text_sd):
                        parsed_date_sd, _ = self._parse_mal_date_range(
                            date_text_sd)
                        if parsed_date_sd:
                            start_date = parsed_date_sd
                            break  # Found the start date

            anime_data = {
                "mal_id": mal_id, "url": url, "title": title,
                "image_url": image_url, "synopsis": synopsis, "type": anime_type,
                "start_date": start_date,  # Original start date
                "episodes": None,  # Schedule page doesn't list total eps typically
                "duration_min_per_ep": None,  # Schedule page doesn't list duration typically
                "genres": genres_visible,
                "themes": properties_data.get('themes', []),
                "demographics": properties_data.get('demographics', []),
                "all_genre_ids": all_genre_ids,
                "studios": properties_data.get('studios', []),
                "source": properties_data.get('source'),
                "score": score, "members": members,
                "airing_time_jst": airing_time_jst,
                "next_episode_num": next_episode_num,
            }
            return ScheduleAnimeItem(**anime_data)

        except ValidationError as e:
            logger.error(
                f"Pydantic validation failed for schedule data ({title} - ID:{mal_id}): {e}")
            return None
        except Exception as e:
            logger.exception(
                f"Failed to parse schedule entry ({title} - ID:{mal_id}): {e}")
            return None

    # -------------------

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
