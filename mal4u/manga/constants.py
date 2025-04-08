from enum import IntEnum, auto

class MangaType(IntEnum):
    MANGA = 1
    ONE_SHOT = 2
    DOUJINSHI = 3
    LIGHT_NOVEL = 4
    NOVEL = 5
    MANHWA = 6
    MANHUA = 7
    
class MangaStatus(IntEnum):
    FINISHED = 1
    PUBLISHING = 2
    ON_HIATUS = 3
    DISCONTINUED = 4
    NOT_YES_PUBLISHED = 5