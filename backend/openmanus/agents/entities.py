from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


class Agent(BaseModel):
    model_config = {"validate_assignment": True}

    name: str = Field(description="Agent 名称")
    description: str = Field(default="", description="Agent 描述")
    prompt: str = Field(default="", description="系统提示词")
    tools: list[str] = Field(default_factory=list, description="统一工具白名单")
    skills: list[str] = Field(default_factory=list, description="技能白名单")
    sub_agents: list[str] = Field(default_factory=list, description="可派发的子 agent")
    is_builtin: bool = Field(default=False, description="是否内置 agent")
    avatar: str = Field(default="", description="头像预设 ID")


class AvatarPreset(BaseModel):
    id: str = Field(description="预设 ID")
    file: str = Field(description="SVG 文件名")
    seed: str = Field(default="", description="DiceBear 种子")
    url: str = Field(description="静态访问路径")


class CreateAgentBody(BaseModel):
    name: str = Field(description="Agent 名称")
    description: str = Field(default="", description="Agent 描述")
    prompt: str = Field(default="", description="系统提示词")
    tools: list[str] = Field(default_factory=list, description="工具白名单")
    skills: list[str] = Field(default_factory=list, description="技能白名单")


class UpdateAgentBody(BaseModel):
    prompt: Optional[str] = Field(default=None, description="新系统提示词")
    tools: Optional[list[str]] = Field(default=None, description="新工具白名单")
    skills: Optional[list[str]] = Field(default=None, description="新技能白名单")
    description: Optional[str] = Field(default=None, description="新描述")


class SetAvatarBody(BaseModel):
    preset_id: Optional[str] = Field(default=None, description="头像预设 ID")
