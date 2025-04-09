import re
import aiohttp
from bs4 import BeautifulSoup, Tag
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
                logger.debug(f"Request to {url} succeeded (Status: {response.status})")
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
            logger.error(f"Error in _safe_find (tag={name}, kwargs={kwargs}): {e}")
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
            logger.error(f"Error in _safe_find_all (tag={name}, kwargs={kwargs}): {e}")
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

    def _parse_int(self, text: str, default: Optional[int] = None) -> Optional[int]:
        """Tries to convert a string to an int."""
        try:
            return int(text.replace(',', '').strip())
        except (ValueError, TypeError, AttributeError):
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
                    logger.warning(f"Could not convert extracted ID '{id_str}' to int for URL: {url} using pattern: {pattern}")
                    return None
                except IndexError:
                    logger.error(f"Regex pattern '{pattern}' matched URL '{url}' but has no capturing group 1.")
                    return None
            else:
                logger.debug(f"Regex pattern '{pattern}' did not match URL: {url}")
                return None
        except re.error as e:
            logger.error(f"Regex error while searching URL '{url}' with pattern '{pattern}': {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error in _extract_id_from_url for URL '{url}': {e}")
            return None
    
    def _find_nested(self, parent: Optional[Union[BeautifulSoup, Tag]],
                     *search_path: Union[Tuple[str, Dict[str, Any]], str, Tuple[str]]) -> Optional[Tag]:

        current_element = parent
        for i, step in enumerate(search_path):
            if current_element is None: return None
            tag_name: Optional[str] = None
            attributes: Dict[str, Any] = {}
            try:
                if isinstance(step, str): tag_name = step
                elif isinstance(step, tuple):
                    if len(step) >= 1 and isinstance(step[0], str):
                        tag_name = step[0]
                        if len(step) == 2 and isinstance(step[1], dict): attributes = step[1]
                        elif len(step) > 1 and not (len(step) == 2 and isinstance(step[1], dict)):
                             logger.warning(f"_find_nested: Invalid tuple format at step {i}: {step}. Use (tag,) or (tag, {{attrs}})."); return None
                    else: logger.warning(f"_find_nested: Invalid tuple format at step {i}: {step}. First element must be a string (tag name)."); return None
                else: logger.warning(f"_find_nested: Invalid step type at {i}: {type(step)}. Expected str or tuple."); return None
                if tag_name is None: logger.warning(f"_find_nested: Tag name not defined at step {i}: {step}."); return None
                found = current_element.find(tag_name, **attributes)
                current_element = found if isinstance(found, Tag) else None
            except Exception as e:
                logger.error(f"_find_nested: Error at step {i} finding '{tag_name}' with {attributes}: {e}")
                return None
        return current_element
    
    def _parse_link_list(
        self,
        start_node: Optional[Tag],
        stop_at_tag: str = 'div',
        parent_limit: Optional[Tag] = None,
        pattern: Union[str, re.Pattern] = r"/(?:genre|magazine|people)/(\d+)/"
    ) -> List[LinkItem]:
        """
        Parses a list of <a> tags following a start_node until a stop_at_tag is encountered.
        Extracts MAL ID from the href using the provided regex pattern.

        Args:
            start_node: The Tag element after which to start searching for <a> tags.
            stop_at_tag: The name of the tag that signifies the end of the list (e.g., 'div', 'span', 'h2').
            pattern: The regex pattern (string or compiled) used to extract the MAL ID
                     from the href attribute. It MUST contain at least one capturing group
                     for the ID. Defaults to a common pattern for genre/magazine/people.

        Returns:
            A list of LinkItem objects.
        """
        links = []
        if not start_node:
            return links

        current_node = start_node.next_sibling
        while current_node:
            if isinstance(current_node, Tag):
                if current_node.name == stop_at_tag or current_node.name == 'h2':
                    break
                if current_node.name == 'a':
                    href = self._get_attr(current_node, 'href')
                    name = self._get_text(current_node)
                    mal_id = None

                    if href:
                        mal_id = self._extract_id_from_url(href, pattern=pattern)

                    if name and href and mal_id is not None:
                        try:
                            link_type = None
                            if "/anime/producer/" in href: link_type = "producer"
                            elif "/people/" in href: link_type = "person"
                            elif "/character/" in href: link_type = "character"
                            elif "/manga/magazine/" in href: link_type = "magazine"
                            elif "/genre/" in href: link_type = "genre" 

                            links.append(LinkItem(mal_id=mal_id, name=name, url=href, type=link_type))
                        except ValidationError as e:
                            logger.warning(f"Skipping invalid link item: Name='{name}', URL='{href}', ID='{mal_id}'. Error: {e}")
                    else:
                         logger.debug(f"Skipping link node: Name='{name}', Href='{href}', Extracted ID='{mal_id}' using pattern '{pattern}'")

            current_node = current_node.next_sibling
        return links


    def _parse_mal_date_range(self, date_str: Optional[str]) -> Tuple[Optional[date], Optional[date]]:
        """
        Parses MAL date strings like "Aug 25, 1989 to ?", "Aug 25, 1989", "?", etc.
        Returns a tuple (start_date, end_date).
        """
        if not date_str or date_str.strip() == '?':
            return None, None

        start_date: Optional[date] = None
        end_date: Optional[date] = None

        parts = [p.strip() for p in date_str.split(" to ")]

        def parse_single_date(text: str) -> Optional[date]:
            if not text or text == '?':
                return None
            # Handle formats like "Aug 25, 1989", "Aug 1989", "1989"
            fmts = ["%b %d, %Y", "%b, %Y", "%Y"] # Order matters
            for fmt in fmts:
                try:
                    # Handle cases like 'Aug 25 , 1989' with extra spaces
                    cleaned_text = re.sub(r'\s+', ' ', text).strip()
                    return datetime.strptime(cleaned_text, fmt).date()
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
        """Gets the stripped text of the immediate next sibling, if it's just text."""
        if node and node.next_sibling and isinstance(node.next_sibling, str):
             text = node.next_sibling.strip()
             return text if text else None
        return None