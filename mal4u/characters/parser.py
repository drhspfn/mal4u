from typing import Any, Dict, List, Optional
import aiohttp
import logging
import re

from bs4 import BeautifulSoup, Tag
from pydantic import ValidationError

from ..base import BaseParser
from .. import constants

logger = logging.getLogger(__name__)

class MALCharactersParser(BaseParser):
    def __init__(self, session: aiohttp.ClientSession):
        super().__init__(session)
        logger.info("Characters parser initialized")