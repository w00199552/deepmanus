from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

class Topic(BaseModel):

    id: str = Field(description="Topic ID")
    title: Optional[str] = Field(default=None, description="标题")
    workdir: Optional[str] = Field(default=None, description="工作目录")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")

class TopicSummary(BaseModel):

    id: str = Field(description="Topic ID")
    title: Optional[str] = Field(default=None, description="标题")
    workdir: Optional[str] = Field(default=None, description="工作目录")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")
    session_id: Optional[str] = Field(default=None, description="最新 session 的 ID")
    kind: str = Field(default="root", description="最新 session 的类型")
    status: str = Field(default="active", description="最新 session 的状态")
    preview: Optional[str] = Field(default=None, description="最新消息预览")
    agents: list[str] = Field(default_factory=list, description="成员 agent 名称列表")

class Session(BaseModel):

    id: str = Field(description="Session ID")
    topic_id: str = Field(description="所属 topic ID")
    kind: str = Field(default="root", description="类型：root | team | subagent")
    name: Optional[str] = Field(default=None, description="agent 名称")
    status: str = Field(default="active", description="状态：active | running | error")
    title: Optional[str] = Field(default=None, description="标题")
    model: Optional[str] = Field(default=None, description="使用的模型")
    workdir: Optional[str] = Field(default=None, description="工作目录")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")

class MailboxMessage(BaseModel):

    id: int = Field(description="消息 ID")
    topic_id: str = Field(description="所属 topic ID")
    from_agent: str = Field(description="发送方 agent 名称")
    to_agent: str = Field(description="接收方 agent 名称")
    kind: str = Field(description="消息类型：dispatch | result | chat")
    content: Optional[str] = Field(default=None, description="消息内容")
    whiteboard_ref: Optional[str] = Field(default=None, description="关联的白板便签 ID")
    read: bool = Field(default=False, description="是否已读")
    created_at: Optional[str] = Field(default=None, description="创建时间")

class WhiteboardNote(BaseModel):

    id: str = Field(description="便签 ID")
    topic_id: str = Field(description="所属 topic ID")
    author: str = Field(description="写入的 agent 名称")
    kind: Optional[str] = Field(default="task", description="自由标签：task | plan | research | result ...")
    status: str = Field(default="pending", description="工作流状态：pending | in_progress | finished | error")
    title: Optional[str] = Field(default=None, description="标题")
    content: Optional[str] = Field(default=None, description="正文内容")
    created_at: Optional[str] = Field(default=None, description="创建时间")

class CdBody(BaseModel):

    path: str = Field(default="", description="CD进入的目录路径")

class CreateSessionBody(BaseModel):

    kind: str = Field(default="root", description="session 类型")
    name: Optional[str] = Field(default=None, description="agent 名称")
    title: Optional[str] = Field(default=None, description="标题")
    workdir: Optional[str] = Field(default=None, description="工作目录")
    topic_id: str = Field(default="main", description="所属 topic ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

class UpdateSessionBody(BaseModel):

    title: Optional[str] = Field(default=None, description="标题")
    status: Optional[str] = Field(default=None, description="状态")
    workdir: Optional[str] = Field(default=None, description="工作目录")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="扩展元数据（整体替换）")

class UpdatePreviewBody(BaseModel):

    preview: str = Field(default="", description="预览文本")
    speaker: Optional[str] = Field(default=None, description="发言人")
