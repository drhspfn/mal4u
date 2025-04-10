from enum import IntEnum


class MangaType(IntEnum):
    UNKNOWN = 0 
    MANGA = 1
    ONE_SHOT = 2
    DOUJINSHI = 3
    LIGHT_NOVEL = 4
    NOVEL = 5
    MANHWA = 6
    MANHUA = 7
    
    @staticmethod
    def from_str(v: str) -> 'MangaType':
        return {
            "manga": MangaType.MANGA,
            "one shot": MangaType.ONE_SHOT,
            "one-shot": MangaType.ONE_SHOT,
            "doujinshi": MangaType.DOUJINSHI,
            "light novel": MangaType.LIGHT_NOVEL,
            "novel": MangaType.NOVEL,
            "manhwa": MangaType.MANHWA,
            "manhua": MangaType.MANHUA,
        }.get(v.lower().strip(), MangaType.UNKNOWN)

class MangaStatus(IntEnum):
    UNKNOWN = 0 
    FINISHED = 1
    PUBLISHING = 2
    ON_HIATUS = 3
    DISCONTINUED = 4
    NOT_YES_PUBLISHED = 5
    
    @staticmethod
    def from_str(v: str) -> 'MangaStatus':
        return {
            "finished": MangaStatus.FINISHED,
            "publishing": MangaStatus.PUBLISHING,
            "on hiatus": MangaStatus.ON_HIATUS,
            "discontinued": MangaStatus.DISCONTINUED,
            "not yet published": MangaStatus.NOT_YES_PUBLISHED,
        }.get(v.lower().strip(), MangaStatus.UNKNOWN)