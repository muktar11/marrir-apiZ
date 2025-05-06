from typing import Generic, TypeVar, Optional

from pydantic import BaseModel, Extra

M = TypeVar("M", bound=BaseModel)


class BaseProps(BaseModel):
    class Config:
        from_attributes = True
        extra = Extra.forbid


class BaseGenericResponse(BaseModel):
    error: Optional[bool]
    message: Optional[str]
    status_code: Optional[int]
    count: Optional[int] = None


class GenericSingleResponse(BaseGenericResponse, Generic[M]):
    data: Optional[M]
    dealer: Optional[list] = None
    selectable: Optional[list] = None


class GenericMultipleResponse(BaseGenericResponse, Generic[M]):
    data: list[M]
