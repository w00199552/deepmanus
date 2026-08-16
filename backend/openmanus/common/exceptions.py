from __future__ import annotations

class OpenManusError(Exception):
    pass

class NotFoundError(OpenManusError):
    pass

class ValidationError(OpenManusError):
    pass

class TopicDeleteError(OpenManusError):
    pass

class AgentError(OpenManusError):
    pass

class SandboxError(OpenManusError):
    pass

class SkillError(OpenManusError):
    pass
