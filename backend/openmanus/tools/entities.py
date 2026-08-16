from __future__ import annotations

from pydantic import BaseModel, Field

from openmanus.sandbox.entities import FileNode

class Tool(BaseModel):

    name: str = Field(description="工具名")
    description: str = Field(default="", description="工具描述")
    source: str = Field(default="builtin", description="来源：builtin | deepagents | user")

class ToolFile(BaseModel):

    path: str = Field(description="相对工具目录的路径")
    name: str = Field(description="文件名")
    content: str = Field(default="", description="文件文本内容")
    file_type: str = Field(default="text", description="前端渲染类型：markdown | code | text")

__all__ = ["FileNode", "Tool", "ToolFile"]
