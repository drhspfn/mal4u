from typing import Optional
from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional
from mal4u.constants import MAL_DOMAIN


class malIdMixin(BaseModel):
    mal_id: int 
    
class optionalMalIdMixin(BaseModel):
    mal_id: Optional[int] = None 
    
    
class imageUrlMixin(BaseModel):
    image_url: Optional[HttpUrl] = None
    
    @field_validator("image_url", mode="before")
    def validate_image_url(cls, v) -> HttpUrl:
        if isinstance(v, HttpUrl): return v
        elif isinstance(v, str):
            if v == "": return None
            if v.startswith('/'):
                v = MAL_DOMAIN + v
            
            return HttpUrl(v)
        else:
            raise ValueError()

class urlMixin(BaseModel):
    url: HttpUrl
    
    @field_validator("url", mode="before")
    def validate_url(cls, v) -> HttpUrl:
        if isinstance(v, HttpUrl): return v
        elif isinstance(v, str):
            if v.startswith('/'):
                v = MAL_DOMAIN + v
            
            return HttpUrl(v)
        else:
            raise ValueError()
