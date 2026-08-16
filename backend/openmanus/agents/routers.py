from __future__ import annotations

import random
from fastapi import APIRouter

from openmanus.agents import avatar
from openmanus.agents.entities import (
    AvatarPreset,
    CreateAgentBody,
    SetAvatarBody,
    UpdateAgentBody,
)
from openmanus.agents.loader import agent_loader
from openmanus.common.response import ApiListResponse, ApiResponse
from openmanus.skills.loader import skill_loader
from openmanus.tools.entities import Tool
from openmanus.tools.tool_loader import tool_loader

router = APIRouter(prefix="/agents", tags=["agents"])

_DEEPAGENTS_TOOL_DESCRIPTIONS = {
    "read_file": "Read a file (supports offset/limit paging, multimodal)",
    "write_file": "Write content to a file",
    "edit_file": "String-replace edit (requires read first; supports replace_all)",
    "ls": "List files in a directory",
    "glob": "Find files by glob pattern (**, *, ?)",
    "grep": "Search file contents (files_with_matches / content / count)",
    "execute": "Run a shell command (supports timeout)",
    "write_todos": "Manage a todo list",
    "task": "Spawn a synchronous sub-agent (needs sub_agents configured)",
}
_OPENMANUS_TOOLS = [
    Tool(name="dispatch", description="Delegate a task to another agent", source="builtin"),
    Tool(name="send_message", description="Send a message to another agent", source="builtin"),
    Tool(name="read_mailbox", description="Read your inbox messages", source="builtin"),
    Tool(name="whiteboard_write", description="Write an artefact to the whiteboard", source="builtin"),
    Tool(name="whiteboard_read", description="Read whiteboard artefacts", source="builtin"),
]


def _tool_catalog() -> list[Tool]:
    catalog = [
        Tool(name=name, description=desc, source="deepagents")
        for name, desc in _DEEPAGENTS_TOOL_DESCRIPTIONS.items()
    ]
    catalog.extend(_OPENMANUS_TOOLS)
    return catalog


@router.get("", response_model=ApiListResponse)
@router.get("/", response_model=ApiListResponse, include_in_schema=False)
async def api_list_agents():
    try:
        result = list(agent_loader.configs.values())
        result.sort(key=lambda a: (not a.is_builtin, a.name))
        return ApiListResponse.ok(data=result, total=len(result))
    except Exception as e:
        return ApiListResponse.fail(message=str(e))


@router.get("/meta/tools", response_model=ApiListResponse)
async def api_list_all_tools():
    try:
        tools = _tool_catalog()
        for name, instance in tool_loader().tools.items():
            tools.append(Tool(
                name=name,
                description=getattr(instance, "description", "")[:200],
                source="user",
            ))
        return ApiListResponse.ok(data=tools, total=len(tools))
    except Exception as e:
        return ApiListResponse.fail(message=str(e))


@router.get("/meta/skills", response_model=ApiListResponse)
async def api_list_all_skills():
    try:
        skills = list(skill_loader.skills.values())
        return ApiListResponse.ok(data=skills, total=len(skills))
    except Exception as e:
        return ApiListResponse.fail(message=str(e))


@router.get("/avatar-presets", response_model=ApiResponse)
async def api_list_avatar_presets_endpoint():
    try:
        presets = avatar.list_avatar_presets()
        return ApiResponse.ok({
            "count": len(presets),
            "presets": [AvatarPreset(**p).model_dump() for p in presets],
        })
    except Exception as e:
        return ApiResponse.fail(message=str(e))


@router.get("/{name}", response_model=ApiResponse)
async def api_get_agent(name: str):
    try:
        cfg = agent_loader.get(name)
        if not cfg:
            return ApiResponse.fail(message="agent not found")
        return ApiResponse.ok(cfg)
    except Exception as e:
        return ApiResponse.fail(message=str(e))


@router.post("/{name}/avatar/regenerate", response_model=ApiResponse)
async def api_regenerate_avatar(name: str, body: SetAvatarBody | None = None):
    try:
        if not agent_loader.get(name):
            return ApiResponse.fail(message="agent not found")
        presets = avatar.list_avatar_presets()
        if not presets:
            return ApiResponse.fail(
                message="no avatar presets bundled (seed/avatars/ missing)",
            )
        preset_id = (body.preset_id if body and body.preset_id else None)
        if preset_id is None:
            preset_id = random.choice(presets)["id"]
        applied = agent_loader.save_avatar(name, preset_id)
        return ApiResponse.ok({"ok": True, "avatar": applied})
    except Exception as e:
        return ApiResponse.fail(message=str(e))


@router.post("", response_model=ApiResponse)
@router.post("/", response_model=ApiResponse, include_in_schema=False)
async def api_create_agent(body: CreateAgentBody):
    try:
        agent_loader.create(body.name, body.prompt, body.tools, body.description)
        if body.skills:
            agent_loader.save_skills(body.name.strip(), body.skills)
        return ApiResponse.ok({"ok": True, "name": body.name.strip()})
    except Exception as e:
        return ApiResponse.fail(message=str(e))


@router.put("/{name}", response_model=ApiResponse)
async def api_update_agent(name: str, body: UpdateAgentBody):
    try:
        if not agent_loader.get(name):
            return ApiResponse.fail(message="agent not found")
        if body.prompt is not None:
            agent_loader.save_prompt(name, body.prompt)
        if body.tools is not None:
            agent_loader.save_tools(name, body.tools)
        if body.skills is not None:
            agent_loader.save_skills(name, body.skills)
        if body.description is not None:
            agent_loader.save_description(name, body.description)
        return ApiResponse.ok({"ok": True, "name": name})
    except Exception as e:
        return ApiResponse.fail(message=str(e))


@router.delete("/{name}", response_model=ApiResponse)
async def api_delete_agent(name: str):
    try:
        agent_loader.delete(name)
        return ApiResponse.ok({"ok": True, "name": name})
    except Exception as e:
        return ApiResponse.fail(message=str(e))
