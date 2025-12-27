from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class EnclosureSpec(BaseModel):
    inner_mm: List[float] = Field(default_factory=lambda: [70, 40, 18])
    wall_mm: float = 2.4

class TextureSpec(BaseModel):
    prompt: str = "circuit board, clean lines"
    seed: Optional[int] = None
    size: List[int] = Field(default_factory=lambda: [1024, 1024])

class CreateJobRequest(BaseModel):
    subfolder: Optional[str] = None
    enclosure: EnclosureSpec = Field(default_factory=EnclosureSpec)
    texture: TextureSpec = Field(default_factory=TextureSpec)
    meta: Dict[str, Any] = Field(default_factory=dict)

class CreateJobResponse(BaseModel):
    job_id: str
    subfolder: Optional[str]
    status: str
    public: Dict[str, str]
