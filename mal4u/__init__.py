# Экспортируем основной класс для удобства импорта
from .api import MyAnimeListApi
from .manga.types import MangaSearchResult, MangaDetails

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

__all__ = ['MyAnimeListApi', 'MangaSearchResult', "MangaDetails"]