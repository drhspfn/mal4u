from typing import Optional
from pydantic import BaseModel, field_validator
from .constants import MangaType, MangaStatus
 
class mangaStatusMixin(BaseModel):
    status: Optional[MangaType] = None 
    
    @field_validator('status', mode='before')
    def validate_status(cls, v:str) -> MangaStatus:
        if isinstance(v, MangaStatus): return v
        elif isinstance(v, str): return MangaStatus.from_str(v)
        elif isinstance(v, int): return MangaStatus(v)
        else: return None
        
class mangaTypeMixin(BaseModel):
    type: Optional[MangaType] = None 
    
    @field_validator('type', mode='before')
    def validate_type(cls, v:str) -> MangaType:
        if isinstance(v, MangaType): return v
        elif isinstance(v, str): return MangaType.from_str(v)
        elif isinstance(v, int): return MangaType(v)
        else: return None
        
        