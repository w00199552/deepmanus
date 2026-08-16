from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

class Skill(BaseModel):

    name: str = Field(description="Skill 名称")
    description: str = Field(default="", description="Skill 描述")
    dir: str = Field(default="", description="Skill 目录的绝对路径")
    has_scripts: bool = Field(default=False, description="是否带 scripts/ 脚本目录")
    has_references: bool = Field(default=False, description="是否带 references/ 参考目录")
