from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

class FileNode(BaseModel):

    name: str = Field(description="文件或目录名")
    path: str = Field(description="相对 workdir 的路径")
    type: str = Field(default="file", description="类型：file | dir")
    size: int = Field(default=0, description="文件字节数（目录为 0）")
    children: list["FileNode"] = Field(default_factory=list, description="子节点")
    has_children: bool = Field(default=False, description="目录是否有可加载的子项（懒展开用）")

FileNode.model_rebuild()

class FileContent(BaseModel):

    path: str = Field(description="相对 workdir 的路径")
    name: str = Field(description="文件名")
    content: str = Field(default="", description="文件文本内容")
    file_type: str = Field(default="text", description="前端渲染类型：markdown | code | image | text | binary")

class WriteFileBody(BaseModel):

    path: str = Field(description="相对 workdir 的文件路径")
    content: str = Field(default="", description="写入的文本内容")
    workdir: Optional[str] = Field(default=None, description="指定 workdir（按 topic），缺省用全局")

class PathBody(BaseModel):

    path: str = Field(description="相对 workdir 的路径")
    workdir: Optional[str] = Field(default=None, description="指定 workdir（按 topic），缺省用全局")

class ChildrenResult(BaseModel):

    path: str = Field(description="目录相对路径")
    children: list[FileNode] = Field(default_factory=list, description="子节点列表")

class WriteResult(BaseModel):

    ok: bool = Field(default=True, description="是否成功")
    path: str = Field(description="操作的相对路径")

class WatchEvent(BaseModel):

    type: str = Field(description="事件类型：created | modified | deleted | moved | ping")
    path: Optional[str] = Field(default=None, description="变更文件的相对路径")
