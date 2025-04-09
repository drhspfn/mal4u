import re
import aiohttp
from bs4 import BeautifulSoup, Tag, NavigableString
from typing import Dict, List, Optional, Any, Tuple, Union
import logging
from datetime import date, datetime
from pydantic import ValidationError
from .types import LinkItem

logger = logging.getLogger(__name__)


class BaseParser:
    """Base class for MAL parsers."""

    def __init__(self, session: aiohttp.ClientSession):
        if session is None:
            # This should not happen when using MyAnimeListApi correctly
            raise ValueError("ClientSession cannot be None for the parser")
        self._session = session

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

        potential_headers = self._safe_find_all(container, 'div', class_='normal_header')

        for h in potential_headers:
            direct_texts = [str(c).strip() for c in h.contents if isinstance(c, NavigableString) and str(c).strip()]

            if header_text_exact in direct_texts:
                # Additional check: make sure it's not part of the text of another heading
                # For example, "Explicit Genres" contains "Genres". We want an exact match.
                # Often the desired text is the last text node.
                if direct_texts and direct_texts[-1] == header_text_exact:
                    header = h
                    logger.debug(f"Found header for '{header_text_exact}' using direct text node check.")
                    break 

        # If you can't find it via direct text, let's try the old method (in case of headings inside <a>)
        if not header:
            for h in potential_headers:
                header_link = self._safe_find(h, 'a', string=lambda t: t and header_text_exact == t.strip())
                if header_link:
                    header = h
                    logger.debug(f"Found header for '{header_text_exact}' using inner link text check.")
                    break

        if not header:
            logger.warning(f"Header '{header_text_exact}' not found in the container using multiple checks.")
            return results 


        link_container = header.find_next_sibling('div', class_='genre-link')
        if not link_container:
            logger.warning(f"Could not find 'div.genre-link' container after header: '{header_text_exact}'")
            return results 


        links = self._safe_find_all(link_container, 'a', class_='genre-name-link')
        if not links:
            logger.debug(f"No 'a.genre-name-link' found within the container for '{header_text_exact}'.")
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
                    logger.warning(f"Skipping invalid LinkItem data from '{category_name_for_logging}': Name='{name}', URL='{href}', ID='{mal_id}'. Error: {e}")
                except Exception as e:
                    logger.error(f"Error creating LinkItem for '{name}' ({href}) in '{category_name_for_logging}': {e}", exc_info=True)
            else:
                logger.debug(f"Skipping link in '{category_name_for_logging}' due to missing data: Text='{full_text}', Href='{href}', Extracted ID='{mal_id}'")

        return results