from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Generic, TypeVar

T = TypeVar("T")

class ApiError(BaseModel):

    message: str = Field(default="", description="错误信息")

class ApiResponse(BaseModel, Generic[T]):

    result: T | None = Field(default=None, description="业务数据")
    error: ApiError | None = Field(default=None, description="错误信息，成功时为 None")

    @classmethod
    def ok(cls, result: Any = None) -> "ApiResponse[Any]":
        return cls(result=result)

    @classmethod
    def fail(cls, message: str) -> "ApiResponse[Any]":
        return cls(error=ApiError(message=message))

class ApiListResponse(BaseModel, Generic[T]):

    data: list[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="数据总数")
    error: ApiError | None = Field(default=None, description="错误信息，成功时为 None")

    @classmethod
    def ok(cls, data: list[Any] | None = None, total: int | None = None) -> "ApiListResponse[Any]":
        items = data or []
        return cls(data=items, total=total if total is not None else len(items))

    @classmethod
    def fail(cls, message: str) -> "ApiListResponse[Any]":
        return cls(error=ApiError(message=message))
