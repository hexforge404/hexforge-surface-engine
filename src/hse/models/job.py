from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

class TextureRequest(BaseModel):
    prompt: str = Field(min_length=1)
    seed: Optional[int] = None
    size: List[int] = Field(default_factory=lambda: [1024, 1024])

class EnclosureFeatures(BaseModel):
    standoffs: List[Dict[str, Any]] = Field(default_factory=list)
    cutouts: List[Dict[str, Any]] = Field(default_factory=list)

class EnclosureRequest(BaseModel):
    inner_mm: List[float] = Field(min_length=3, max_length=3)
    wall_mm: float = Field(gt=0)
    lid_split: Literal["x", "y", "z"] = "z"
    lid_ratio: float = Field(gt=0, lt=1, default=0.25)
    features: EnclosureFeatures = Field(default_factory=EnclosureFeatures)

class CreateJobRequest(BaseModel):
    subfolder: Optional[str] = None
    enclosure: EnclosureRequest
    texture: TextureRequest

class JobResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
