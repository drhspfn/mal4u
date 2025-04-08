from enum import IntEnum

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
    
class AnimeStatus(IntEnum):
    UNKNOWN = 0           
    CURRENTLY_AIRING = 1 
    FINISHED_AIRING = 2    
    NOT_YET_AIRED = 3     

class AnimeRated(IntEnum):
    UNKNOWN = 0                  # Select rating
    G_ALL_AGES = 1               # G - All Ages
    PG_CHILDREN = 2              # PG - Children
    PG_13_TEENS_13_OR_OLDER = 3  # PG-13 - Teens 13 or older
    R_17_PLUS = 4                # R - 17+ (violence & profanity)
    R_PLUS_MILD_NUDITY = 5       # R+ - Mild Nudity
    RX_HENTAI = 6                # Rx - Hentai