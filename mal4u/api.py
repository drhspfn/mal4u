from typing import Optional, List
import aiohttp
import logging

from . import constants
from .manga import MangaSearchResult, MALMangaParser


logger = logging.getLogger(__name__)

class MyAnimeListApi:
    """
    Asynchronous client for interacting with MyAnimeList (via HTML parsing).
    Manages aiohttp session and provides access to various parsers (manga, anime, etc).

    Supports two modes of use:
    1. Direct object creation:
       api = MyAnimeListApi()
       await api.create_session() # Must be called before use
       # ... using api.manga.search(...) ...
       await api.close() # Must be called to close the session

    2. asynchronous context manager (recommended):
       async with MyAnimeListApi() as api:
           # ... using api.manga.search(...) ...
       # Session will be created and closed automatically
    """
    def __init__(
        self,
        timeout: int = constants.DEFAULT_TIMEOUT,
        user_agent: str = constants.DEFAULT_USER_AGENT,
        cookies: Optional[dict] = None,
        headers: Optional[dict] = None
    ):
        self._timeout_val = timeout
        self._cookies = cookies or {}
        self._headers = headers or {"User-Agent": user_agent}
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_owner: bool = False

        self._manga_parser: Optional[MALMangaParser] = None
        # self._anime_parser: Optional[MALAnimeParser] = None

        logger.info("A MyAnimeListApi instance has been created.")

    @property
    def manga(self) -> MALMangaParser:
        """Access to the manga parser."""
        if not self._manga_parser:
            raise RuntimeError("The session has not been initialized. Call create_session() or use async with.")
        return self._manga_parser

    # @property
    # def anime(self) -> MALAnimeParser: ... # TODO:

    async def _create_session(self) -> aiohttp.ClientSession:
        """Creates a new aiohttp session."""
        if self._session is None or self._session.closed:
            logger.debug("Creating a new aiohttp session.")
            timeout = aiohttp.ClientTimeout(total=self._timeout_val)
            self._session = aiohttp.ClientSession(
                constants.MAL_DOMAIN,
                cookies=self._cookies,
                headers=self._headers,
                timeout=timeout
            )
            self._session_owner = True
            self._initialize_parsers()
            logger.info("The aiohttp session has been successfully created.")
        return self._session

    def _initialize_parsers(self) -> None:
        """Initializes all sub-parsers with the current session."""
        if not self._session:
             raise RuntimeError("Attempting to initialize parsers without an active session.")
        logger.debug("Initialization of sub-parsers (manga)...")
        self._manga_parser = MALMangaParser(self._session)
        # self._anime_parser = MALAnimeParser(self._session) # TODO:

    async def create_session(self) -> None:
        """
        Explicitly creates an internal aiohttp session.
        Must be called before using the API if the object is created without `async with`.
        """
        if self._session and not self._session.closed:
            logger.warning("The session already exists and is active.")
            return
        await self._create_session()

    async def close(self) -> None:
        """
        Closes the internal aiohttp session if it was created by this instance.
        Must be called after using the API if the object was created without `async with`.
        """
        if self._session and not self._session.closed and self._session_owner:
            logger.debug("Closing session aiohttp.")
            await self._session.close()
            self._session = None
            self._session_owner = False
            logger.info("The aiohttp session is closed.")
        elif self._session and not self._session_owner:
             logger.debug("The session was externally transferred, no closure is required.")

    async def __aenter__(self) -> "MyAnimeListApi":
        """Logging into an asynchronous context, creates a session."""
        logger.debug("Login to async context, check/create session.")
        await self._create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exits the asynchronous context, closing the session."""
        logger.debug("Exiting the async context, closing the session.")
        await self.close()

    # --- Methods-Facades ---

    async def search_manga(self, query: str, limit: int = 5) -> List[MangaSearchResult]:
        """
        Searches for manga using a manga parser.

        An example of using a facade. Make sure the session is active.
        """
        if not self._session or self._session.closed:
            raise RuntimeError("The session is not active. Use 'async with' or call 'await api.create_session()' before using it.")

        return await self.manga.search(query, limit)