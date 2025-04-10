from typing import Optional
from pydantic import BaseModel, field_validator
from .constants import AnimeType, AnimeRated, AnimeStatus
 
        
# --- ANIME
        
class animeTypeMixin(BaseModel):
    type: Optional[AnimeType] = None 
    
    @field_validator('type', mode='before')
    def validate_type(cls, v:str) -> AnimeType:
        if isinstance(v, AnimeType): return v
        elif isinstance(v, str): return AnimeType.from_str(v)
        elif isinstance(v, int): return AnimeType(v)
        else: return None
        
class animeRatedMixin(BaseModel):
    rating: Optional[AnimeRated] = None 
    
    @field_validator('rating', mode='before')
    def validate_rating(cls, v:str) -> AnimeRated:
        if isinstance(v, AnimeRated): return v
        elif isinstance(v, str): return AnimeRated.from_str(v)
        elif isinstance(v, int): return AnimeRated(v)
        else: return None
        
class animeStatusMixin(BaseModel):
    status: Optional[AnimeStatus] = None 
    
    @field_validator('status', mode='before')
    def validate_status(cls, v:str) -> AnimeStatus:
        if isinstance(v, AnimeStatus): return v
        elif isinstance(v, str): return AnimeStatus.from_str(v)
        elif isinstance(v, int): return AnimeStatus(v)
        else: return None
        