from enum import IntEnum

RE_ANIME_ID = r"/anime/(\d+)/" 

class AnimeType(IntEnum):
    UNKNOWN = 0 
    TV = 1      
    OVA = 2       
    MOVIE = 3    
    SPECIAL = 4   
    ONA = 5        
    MUSIC = 6     
    CM = 7        
    PV = 8       
    TV_SPECIAL = 9  
    
    @staticmethod
    def from_str(v: str) -> 'AnimeType':
        return {
            "tv": AnimeType.TV,
            "ova": AnimeType.OVA,
            "movie": AnimeType.MOVIE,
            "special": AnimeType.SPECIAL,
            "ona": AnimeType.ONA,
            "music": AnimeType.MUSIC,
            "cm": AnimeType.CM,
            "pv": AnimeType.PV,
            "tv special": AnimeType.TV_SPECIAL,
        }.get(v.lower().strip(), AnimeType.UNKNOWN)

class AnimeStatus(IntEnum):
    UNKNOWN = 0           
    CURRENTLY_AIRING = 1 
    FINISHED_AIRING = 2    
    NOT_YET_AIRED = 3     

    @staticmethod
    def from_str(v: str) -> 'AnimeStatus':
        return {
            "currently airing": AnimeStatus.CURRENTLY_AIRING,
            "finished airing": AnimeStatus.FINISHED_AIRING,
            "not yet aired": AnimeStatus.NOT_YET_AIRED,
        }.get(v.lower().strip(), AnimeStatus.UNKNOWN)

class AnimeRated(IntEnum):
    UNKNOWN = 0                  # Select rating
    G_ALL_AGES = 1               # G - All Ages
    PG_CHILDREN = 2              # PG - Children
    PG_13_TEENS_13_OR_OLDER = 3  # PG-13 - Teens 13 or older
    R_17_PLUS = 4                # R - 17+ (violence & profanity)
    R_PLUS_MILD_NUDITY = 5       # R+ - Mild Nudity
    RX_HENTAI = 6                # Rx - Hentai

    @staticmethod
    def from_str(v: str) -> 'AnimeRated':
        return {
            "g": AnimeRated.G_ALL_AGES,
            "g - all ages": AnimeRated.G_ALL_AGES,
            "pg": AnimeRated.PG_CHILDREN,
            "pg - children": AnimeRated.PG_CHILDREN,
            "pg-13": AnimeRated.PG_13_TEENS_13_OR_OLDER,
            "pg-13 - teens 13 or older": AnimeRated.PG_13_TEENS_13_OR_OLDER,
            "r": AnimeRated.R_17_PLUS,
            "r - 17+ (violence & profanity)": AnimeRated.R_17_PLUS,
            "r+": AnimeRated.R_PLUS_MILD_NUDITY,
            "r+ - mild nudity": AnimeRated.R_PLUS_MILD_NUDITY,
            "rx": AnimeRated.RX_HENTAI,
            "rx - hentai": AnimeRated.RX_HENTAI,
        }.get(v.lower().strip(), AnimeRated.UNKNOWN)
