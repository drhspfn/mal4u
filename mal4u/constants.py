# --- Base
from enum import StrEnum
from re import compile


MAL_DOMAIN = "https://myanimelist.net"
DEFAULT_TIMEOUT = 10
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
MAL_PAGE_SIZE = 50


# --- Manga
MANGA_URL = "/manga.php"
MANGA_DETAILS_URL = "/manga/{manga_id}"
MANGA_ID_PATTERN = compile(r"/manga/(\d+)(?:/[^/]*)?")

# --- Anime
ANIME_URL = "/anime.php"
ANIME_DETAILS_URL = "/anime/{anime_id}"
ANIME_ID_PATTERN = compile(r"/anime/(\d+)(?:/[^/]*)?")

# --- Character
CHARACTER_URL = "/character.php"
ANIME_DETAILS_URL = "/character/{character_id}"
CHARACTER_ID_PATTERN = compile(r"/character/(\d+)(?:/[^/]*)?")


PERSON_ID_PATTERN = compile(r"/people/(\d+)(?:/[^/]*)?")


class TopType(StrEnum):
    # Common to anime and manga
    MOST_POPULAR = "bypopularity"
    MOST_FAVORITED = "favorite"

    # Anime-specific
    AIRING = "airing"
    UPCOMING = "upcoming"
    TV_SERIES = "tv"
    MOVIES = "movie"
    OVAS = "ova"
    ONAS = "ona"
    SPECIAL = "special"

    # Specific to manga
    ALL_MANGA = "manga"
    ONE_SHOTS = "oneshots"
    DOUJIN = "doujin"
    LIGHT_NOVELS = "lightnovels"
    NOVELS = "novels"
    MANHWA = "manhwa"
    MANHUA = "manhua"

    @staticmethod
    def is_anime_specific(value: "TopType") -> bool:
        return value in {
            TopType.AIRING,
            TopType.UPCOMING,
            TopType.TV_SERIES,
            TopType.MOVIES,
            TopType.OVAS,
            TopType.ONAS,
            TopType.SPECIAL,
        }

    @staticmethod
    def is_manga_specific(value: "TopType") -> bool:
        return value in {
            TopType.ALL_MANGA,
            TopType.ONE_SHOTS,
            TopType.DOUJIN,
            TopType.LIGHT_NOVELS,
            TopType.NOVELS,
            TopType.MANHWA,
            TopType.MANHUA,
        }

    @staticmethod
    def is_common(value: "TopType") -> bool:
        return value in {
            TopType.MOST_POPULAR,
            TopType.MOST_FAVORITED,
        }


class LinkItemType(StrEnum):
    SEASON = "season"
    PERSON = "person"
    GENRE = "genre"
    PRODUCER = "producer"
    MAGAZINE = "magazine"
    ANIME = "anime"
    MANGA = "manga"