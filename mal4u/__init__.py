from .api import MyAnimeListApi

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

__all__ = ['MyAnimeListApi']