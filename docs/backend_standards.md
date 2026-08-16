# 后端开发规范

> 本文档定义 OpenManus 后端代码的模块化结构、分层职责、命名约定和类型系统。
> 所有后端开发必须遵循以下规范，确保代码一致性、类型安全和可维护性。

---

## 1. 垂直领域模块化

**每个领域模块包含自己的分层文件，消除 `api/` 中间层。**

### 标准目录结构

```
module/
├── entities.py    # Pydantic 模型（请求/响应/内部实体）
├── service.py     # 或 loader.py — 业务逻辑
├── routers.py     # REST 层（FastAPI router）
├── store.py       # DB 存储（如需要）
└── __init__.py    # 必须导出关键类/函数，不能留空
```

### 示例：tools/ 模块完整结构

```
tools/
├── __init__.py        # 导出 ToolLoader、Tool
├── entities.py        # Tool、FileNode、ToolFile
├── tool_loader.py     # ToolLoader（业务逻辑 + 加载）
├── routers.py         # /tools 路由
├── dispatch_tool.py   # deepagents dispatch 工具
├── mailbox_tools.py   # 邮箱工具
└── whiteboard_tool.py # 白板工具
```

### 每个文件的职责

| 文件 | 职责 | 依赖方向 |
|------|------|---------|
| `entities.py` | 定义 Pydantic 模型，无业务逻辑 | 被所有文件依赖 |
| `service.py` / `loader.py` | 业务逻辑，操作 DB / 文件系统 | 依赖 entities / store |
| `routers.py` | HTTP 入口，调用 service/loader | 依赖 service / entities / common.response |
| `store.py` | 纯 DB CRUD，不包含业务语义 | 依赖 entities / db |
| `__init__.py` | 重新导出模块公开 API | 依赖模块内部文件 |

---

## 2. Router 层规范

**Router 保持薄层，业务逻辑在 service/loader 中。禁止 `raise HTTPException`。**

### 正确示例

```python
# tools/routers.py
from openmanus.common.response import ApiResponse, ApiListResponse
from openmanus.tools.tool_loader import tool_loader

router = APIRouter(prefix="/tools", tags=["tools"])

@router.get("", response_model=ApiListResponse)
async def list_tools():
    """List all tools."""
    try:
        tools = tool_loader.list_tools()
        return ApiListResponse.ok(data=tools, total=len(tools))
    except Exception as e:
        return ApiListResponse.fail(message=str(e))

@router.get("/{name}", response_model=ApiResponse)
async def get_tool(name: str):
    """Get a single tool by name."""
    try:
        tool = tool_loader.get(name)
        if tool is None:
            return ApiResponse.fail(message="tool not found")
        return ApiResponse.ok(tool)
    except Exception as e:
        return ApiResponse.fail(message=str(e))
```

### 错误示例

```python
# ❌ 错误 - 在 router 中直接 raise HTTPException
@router.get("/{name}")
async def get_tool(name: str):
    tool = tool_loader.get(name)
    if not tool:
        raise HTTPException(status_code=404, detail="not found")  # ❌
    return tool

# ❌ 错误 - 在 router 中编写业务逻辑
@router.get("")
async def list_tools():
    tools = []
    for f in Path("~/.openmanus/tools").iterdir():  # ❌ 直接操作文件系统
        tools.append(parse_tool(f))
    return tools
```

---

## 3. 导入规则

**全部使用 `from openmanus.xxx` 绝对导入，禁止相对导入。**

### 导入顺序

按以下三组排序，组间空一行：

1. **Python 标准库**：`os`、`sys`、`pathlib`、`json`、`asyncio`、`uuid` ...
2. **第三方库**：`fastapi`、`pydantic`、`aiosqlite`、`loguru` ...
3. **项目内部**：`openmanus.config`、`openmanus.common.response` ...

### 正确示例

```python
# ✅ 标准库
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

# ✅ 第三方库
import aiosqlite
from fastapi import APIRouter
from pydantic import BaseModel, Field

# ✅ 项目内部
from openmanus.common.response import ApiResponse, ApiListResponse
from openmanus.config import settings
from openmanus.db import get_db_path
```

### 错误示例

```python
# ❌ 相对导入
from .entities import Tool
from ..common.response import ApiResponse

# ❌ 导入顺序混乱
from openmanus.config import settings
import json
from fastapi import APIRouter
from pathlib import Path

# ❌ wildcard 导入
from openmanus.common.response import *
```

### 例外

`__init__.py` 中的重新导出允许使用相对导入：

```python
# openmanus/tools/__init__.py
from openmanus.tools.tool_loader import ToolLoader  # ✅ 仍然用绝对导入
from openmanus.tools.entities import Tool, FileNode, ToolFile

__all__ = ["ToolLoader", "Tool", "FileNode", "ToolFile"]
```

---

## 4. 命名规则

### 公开函数

使用动词开头，语义清晰：

| 前缀 | 用途 | 示例 |
|------|------|------|
| `get_` | 获取单个对象 | `get_db_path()`、`get_checkpointer()` |
| `list_` | 获取列表 | `list_tools()`、`list_topics()` |
| `create_` | 创建 | `create_session()` |
| `update_` | 更新 | `update_workdir()` |
| `delete_` | 删除 | `delete_topic()` |
| `build_` | 构建/组装 | `build_agent()` |
| `compute_` | 计算 | `compute_thread_id()` |
| `setup_` | 初始化配置 | `setup_logger()` |

### 私有函数

以 `_` 开头，且**不得被外部模块引用**：

```python
# ✅ 正确 - 只在模块内部使用
def _row_to_topic(row: aiosqlite.Row) -> Topic: ...

# ❌ 错误 - 以 _ 开头但被外部引用
# db/path.py
def _db_path() -> str: ...

# topics/topic_store.py
from openmanus.db import _db_path  # ❌ 引用了私有函数
```

---

## 5. 返回类型

**所有 loader/service/store 方法返回 Pydantic 对象，禁止返回裸 `dict`。**

### 正确示例

```python
# ✅ 返回 Pydantic 对象
class TopicStore:
    @classmethod
    async def get(cls, topic_id: str) -> Topic | None:
        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM topics WHERE id = ?", (topic_id,))
            row = await cur.fetchone()
            return _row_to_topic(row) if row else None

def _row_to_topic(row: aiosqlite.Row) -> Topic:
    return Topic(
        id=row["id"],
        title=row["title"],
        workdir=row["workdir"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
```

### 错误示例

```python
# ❌ 返回裸 dict
class TopicStore:
    @classmethod
    async def get(cls, topic_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM topics WHERE id = ?", (topic_id,))
            row = await cur.fetchone()
            return dict(row) if row else None  # ❌
```

### 特例排除清单

以下场景允许返回 `dict`，需在 docstring 中注明原因：

| 场景 | 原因 | 示例 |
|------|------|------|
| LangGraph `RunnableConfig` | 框架要求 dict 格式 | `AgentContext.to_config() -> dict[str, Any]` |
| FastAPI SSE 事件帧 | SSE 协议需要裸 JSON dict | `event_schema.ev_text_delta() -> dict[str, Any]` |
| `_row_to_*` 辅助函数 | 仅供模块内部 row→entity 转换 | `_row_to_topic() -> Topic`（已返回 Pydantic） |

---

## 6. 统一响应包装

**所有 router 必须通过 `ApiResponse` / `ApiListResponse` 包装返回值。**

### 响应结构

| 封装类 | 字段结构 | 适用场景 |
|--------|---------|---------|
| `ApiResponse[T]` | `{ result: T, error?: ApiError }` | 单对象操作 |
| `ApiListResponse[T]` | `{ data: list[T], total: int, error?: ApiError }` | 列表查询 |
| `ApiError` | `{ message: str }` | 错误信息 |

### 使用方式

```python
from openmanus.common.response import ApiResponse, ApiListResponse

# 列表接口
tools = tool_loader.list_tools()
return ApiListResponse.ok(data=tools, total=len(tools))

# 单对象接口 - 成功
return ApiResponse.ok(tool)

# 单对象接口 - 失败
return ApiResponse.fail(message="tool not found")

# 列表接口 - 失败
return ApiListResponse.fail(message="internal error")
```

### Router 声明

每个路由必须声明 `response_model`：

```python
@router.get("", response_model=ApiListResponse)
@router.get("/{name}", response_model=ApiResponse)
@router.delete("/{topic_id}", response_model=ApiResponse)
```

---

## 7. Store 层模式

**Store 类全部使用 `@classmethod`，无需实例化。DB 连接使用 `aiosqlite.connect(get_db_path())`。**

### 标准格式

```python
import aiosqlite
from openmanus.db import get_db_path

class TopicStore:
    """CRUD for topics.

    All methods are classmethod — no instance creation needed.
    """

    @classmethod
    async def get(cls, topic_id: str) -> Topic | None:
        """Get a topic by ID.

        Args:
            topic_id: Topic identifier.

        Returns:
            Topic object, or None if not found.
        """
        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM topics WHERE id = ?", (topic_id,)
            )
            row = await cur.fetchone()
            return _row_to_topic(row) if row else None

    @classmethod
    async def list_topics(cls) -> list[Topic]:
        """List all topics, newest first.

        Returns:
            List of Topic objects.
        """
        async with aiosqlite.connect(get_db_path()) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM topics ORDER BY updated_at DESC"
            )
            rows = await cur.fetchall()
            return [_row_to_topic(r) for r in rows]
```

---

## 8. 对象定义（Pydantic 优先）

**优先使用 Pydantic `BaseModel` 定义对象，禁止使用 `dataclass`。所有字段使用 `Field()` 定义，包括 default 和 description。description 使用中文。**

### 正确示例

```python
from typing import Optional
from pydantic import BaseModel, Field

class Topic(BaseModel):
    id: Optional[str] = Field(default=None, description="ID")
    title: Optional[str] = Field(default=None, description="标题")
    workdir: Optional[str] = Field(default=None, description="工作目录")
    kind: str = Field(default="root", description="类型")
    status: str = Field(default="active", description="状态")
    agents: list[str] = Field(default_factory=list, description="agent名称列表")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")

class CdBody(BaseModel):
    path: str = Field(default="", description="CD进入的目录路径")
```

### 错误示例

```python
# ❌ 使用 dataclass
from dataclasses import dataclass

@dataclass(frozen=True)
class AgentContext:
    session_id: str
    topic_id: str

# ❌ 字段缺少 Field() 和 description
class Tool(BaseModel):
    name: str                  # ❌ 无 Field()、无 description
    description: str = ""      # ❌ 直接赋默认值
    source: str = "user"       # ❌
```

### Field 规范

| 场景 | 写法 |
|------|------|
| 必填字段 | `name: str = Field(description="名称")` |
| 可选字段 | `title: Optional[str] = Field(default=None, description="标题")` |
| 带默认值 | `kind: str = Field(default="root", description="类型")` |
| 列表默认值 | `agents: list[str] = Field(default_factory=list, description="列表")` |
| 计算字段 | `@computed_field @property def avatar_url(self) -> Optional[str]:` |

---

## 9. 注释风格

**采用 Google 风格 docstring，包含 Summary / Args / Returns / Raises。**

### 函数/方法

```python
async def reset_topic(cls, topic_id: str) -> bool:
    """Reset a topic's conversation history.

    Clear all checkpoints and sessions in the specified topic.
    The topic itself (row in topics table) is preserved.

    Args:
        topic_id: The topic identifier to reset.

    Returns:
        True if reset was successful.

    Raises:
        OpenManusError: If the topic does not exist.
    """
```

### 类

```python
class TopicStore:
    """CRUD for topics (task/conversation groups).

    All methods are classmethod — no instance creation needed.
    DB connections are opened per-call via aiosqlite.connect().
    """
```

### 模块

```python
"""TopicStore — CRUD for topics (task/conversation groups).

Tables:
    topics — one row per task/conversation group.
"""
```

### 格式要求

| 元素 | 要求 |
|------|------|
| Summary | 首行简短描述，首字母大写，句号结尾 |
| Args | 每个参数一行，`名称: 描述。` |
| Returns | 描述返回值类型和含义 |
| Raises | 列出可能抛出的异常类和原因 |
| 空行 | Summary 与 Args 之间空一行 |

---

## 10. 类型注解

**除 routers 外，所有函数/方法必须定义参数类型和返回类型。routers 由 FastAPI 自动推导，只要求声明 `response_model`。**

### 正确示例

```python
# ✅ service/loader/store — 完整类型注解
def list_tools(self) -> list[Tool]:
    ...

async def get_topic_history(cls, topic_id: str) -> TopicHistory:
    ...

def _row_to_topic(row: aiosqlite.Row) -> Topic:
    ...

# ✅ router — 只要求 response_model，不要求返回类型注解
@router.get("", response_model=ApiListResponse)
async def list_tools():
    tools = tool_loader.list_tools()
    return ApiListResponse.ok(data=tools, total=len(tools))
```

### 错误示例

```python
# ❌ 缺少返回类型
def list_tools(self):         # ❌ 无返回类型
    ...

# ❌ 缺少参数类型
async def get(self, topic_id):  # ❌ 参数无类型
    ...

# ❌ router 有多余的类型注解（不禁止，但不是必须的）
@router.get("", response_model=ApiListResponse)
async def list_tools() -> ApiListResponse:  # 冗余，response_model 已声明
    ...
```

### 类型注解使用 Python 3.12+ 语法

```python
# ✅ Python 3.12+ 内建类型
def list_items() -> list[Topic]: ...
def get_mapping() -> dict[str, Any]: ...
def get_one() -> Topic | None: ...

# ❌ 使用 typing 旧语法
from typing import List, Dict, Optional
def list_items() -> List[Topic]: ...   # ❌
def get_one() -> Optional[Topic]: ...  # ❌
```

---

## 11. 错误处理

**使用自定义异常层级，禁止 bare except，使用异常链保留上下文。**

### 自定义异常层级

```python
# openmanus/common/exceptions.py
class OpenManusError(Exception):
    """Base exception for all OpenManus application errors."""
    pass

class NotFoundError(OpenManusError):
    """Raised when a requested resource is not found."""
    pass

class ValidationError(OpenManusError):
    """Raised when input validation fails."""
    pass

class TopicDeleteError(OpenManusError):
    """Raised when a topic cannot be deleted (e.g. 'main' topic)."""
    pass
```

### 正确示例

```python
# ✅ 抛出特定异常
async def delete_topic(cls, topic_id: str) -> bool:
    if topic_id == MAIN_TOPIC_ID:
        raise TopicDeleteError("main topic cannot be deleted")
    topic = await TopicStore.get(topic_id)
    if not topic:
        raise NotFoundError(f"topic not found: {topic_id}")
    ...

# ✅ 异常链 — 保留原始 traceback
async def load_config(path: str) -> Config:
    try:
        with open(path) as f:
            return Config.from_json(f.read())
    except FileNotFoundError as e:
        raise OpenManusError(f"Config file not found: {path}") from e
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in config: {path}") from e

# ✅ 特定异常捕获
try:
    await checkpointer.adelete_thread(thread_id)
except (OSError, aiosqlite.Error) as e:
    logger.warning("Failed to delete thread %s: %s", thread_id, e)
```

### 错误示例

```python
# ❌ bare except
try:
    await risky_operation()
except:                    # ❌ 捕获所有异常包括 KeyboardInterrupt
    pass

# ❌ 吞没异常
try:
    await risky_operation()
except Exception:
    pass                  # ❌ 无日志、无处理

# ❌ 丢失异常上下文
try:
    parsed = json.loads(data)
except json.JSONDecodeError as e:
    raise ValueError(f"Parse failed")  # ❌ 缺少 from e

# ❌ 抛出裸 Exception
raise Exception("topic not found")  # ❌ 应使用 NotFoundError
```

### Router 中的异常处理

Router 层统一用 `try/except Exception` + `ApiResponse.fail()`，这是唯一允许宽泛捕获的地方：

```python
@router.get("/{name}", response_model=ApiResponse)
async def get_tool(name: str):
    try:
        tool = tool_loader.get(name)
        if tool is None:
            return ApiResponse.fail(message="tool not found")
        return ApiResponse.ok(tool)
    except Exception as e:
        return ApiResponse.fail(message=str(e))
```

---

## 12. 异步编程

**I/O 操作必须使用 `async def`，禁止在异步端点中调用阻塞操作。**

### 规则

| 规则 | 说明 |
|------|------|
| `async def` 用于 I/O | DB 查询、HTTP 请求、文件读写 |
| 同步端点用 `def` | 纯计算、无 I/O 的简单操作 |
| 禁止阻塞调用 | 不在 async 函数中使用 `requests`、`time.sleep()`、同步文件 I/O |
| 禁止混用 | 不在 async 函数中直接调用同步 I/O 函数 |

### 正确示例

```python
# ✅ 异步 DB 操作
async def get(cls, topic_id: str) -> Topic | None:
    async with aiosqlite.connect(get_db_path()) as db:
        cur = await db.execute("SELECT * FROM topics WHERE id = ?", (topic_id,))
        row = await cur.fetchone()
        return _row_to_topic(row) if row else None

# ✅ 同步计算函数 — 不需要 async
def compute_thread_id(topic_id: str, agent_name: str) -> str:
    return f"{topic_id}:{agent_name}"
```

### 错误示例

```python
# ❌ 在 async 函数中使用同步阻塞调用
async def fetch_data(url: str) -> dict:
    import requests
    resp = requests.get(url)  # ❌ 阻塞！应使用 httpx.AsyncClient
    return resp.json()

# ❌ 在 async 函数中使用 time.sleep
async def retry_operation():
    import time
    time.sleep(5)  # ❌ 阻塞事件循环！应使用 asyncio.sleep(5)

# ❌ 给纯计算函数加 async
async def compute_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()  # ❌ 无 I/O，不需要 async
```

---

## 13. 安全规范

### SQL 查询

**必须使用参数化查询，禁止 f-string / 字符串拼接 SQL。**

```python
# ✅ 参数化查询
cur = await db.execute(
    "SELECT * FROM topics WHERE id = ?", (topic_id,)
)

# ✅ 动态 WHERE 子句仍使用参数
clauses = []
params = []
if kind:
    clauses.append("kind = ?")
    params.append(kind)
where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
cur = await db.execute(f"SELECT * FROM sessions {where}", params)

# ❌ SQL 注入风险
cur = await db.execute(
    f"SELECT * FROM topics WHERE id = '{topic_id}'"  # ❌
)
```

### 命令注入

**禁止将未校验的用户输入传入 shell 命令。使用 `subprocess` 时用列表参数。**

```python
# ✅ 列表参数
proc = subprocess.run(["git", "status"], cwd=workdir, capture_output=True)

# ❌ 字符串拼接
proc = subprocess.run(f"git status {user_input}", shell=True)  # ❌
```

### 路径遍历

**校验用户提供的路径，拒绝 `..` 和绝对路径越界。**

```python
# ✅ 校验路径
def safe_path(base: Path, user_path: str) -> Path:
    target = (base / user_path).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise ValidationError("path traversal detected")
    return target
```

### 密钥管理

**禁止硬编码密钥，使用环境变量或配置文件。**

```python
# ✅ 从环境变量 / 配置读取
api_key = settings.api_key

# ❌ 硬编码
api_key = "sk-abc123"  # ❌
```

---

## 14. 日志规范

**使用 loguru 包，统一通过 `openmanus.log` 模块获取 logger。禁止使用 `print()`。**

### Logger 初始化

```python
# openmanus/log/logger.py
import sys
from pathlib import Path

def setup_logger(log_path: str | None = None):
    """Setup loguru logger with console and file handlers.

    Args:
        log_path: Log file path. Defaults to ~/.openmanus/logs/openmanus.log.

    Returns:
        Configured loguru logger instance.
    """
    from loguru import logger

    if log_path is None:
        log_path = str(Path.home() / ".openmanus" / "logs" / "openmanus.log")

    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    logger.remove()

    # 控制台输出（彩色）
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
               "<level>{message}</level>",
        level="DEBUG",
    )

    # 文件输出（自动轮转）
    logger.add(
        log_path,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    return logger


logger = setup_logger()
```

```python
# openmanus/log/__init__.py
from openmanus.log.logger import logger, setup_logger

__all__ = ["logger", "setup_logger"]
```

### 使用方式

```python
from openmanus.log import logger

logger.info("Agent %s started in topic %s", agent_name, topic_id)
logger.warning("Mailbox push failed for %s/%s", topic_id, agent_name)
logger.error("Failed to delete thread: %s", e)
logger.debug("SQL: %s, params: %s", sql, params)
```

### 日志级别约定

| 级别 | 用途 | 示例 |
|------|------|------|
| `DEBUG` | 详细调试信息，仅开发时关注 | SQL 语句、函数入参、中间变量 |
| `INFO` | 正常业务流程 | Agent 启动、Topic 创建、请求处理 |
| `WARNING` | 可恢复的异常或非预期情况 | 重试成功、可选功能降级、配置缺失使用默认值 |
| `ERROR` | 需要关注的错误 | 外部服务调用失败、DB 写入失败 |
| `CRITICAL` | 系统级故障 | 无法启动、存储空间耗尽 |

### 错误示例

```python
# ❌ 使用 print
print(f"Agent {name} started")  # ❌

# ❌ 使用 logging 模块（项目统一用 loguru）
import logging
logger = logging.getLogger(__name__)  # ❌

# ❌ 在日志中暴露敏感信息
logger.debug("API key: %s", api_key)  # ❌
```

---

## 15. 测试规范

**使用 pytest，测试文件放在 `backend/tests/`，共享 fixture 放在 `conftest.py`。**

### 测试配置

`pyproject.toml` 中已配置：

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**`asyncio_mode = "auto"` — async `test_*` 函数自动识别，无需添加 `@pytest.mark.asyncio` 标记。**

### 文件组织

```
backend/tests/
├── conftest.py                 # 共享 fixture（tmp_openmanus_home 等）
├── test_build_agent_tools.py   # Agent 构建工具测试
├── test_tool_guard.py          # ToolGuard 中间件测试
├── test_tool_loader.py         # 工具加载测试
├── test_tool_whitelist.py      # 工具白名单测试
├── test_topics_sessions.py     # Topic/Session CRUD 测试
└── test_whiteboard_mailbox.py  # 白板/邮箱测试
```

### Fixture 隔离

**测试涉及文件系统时，必须使用 `tmp_openmanus_home` fixture 隔离 `~/.openmanus`，禁止写入真实用户配置。**

```python
# tests/conftest.py
@pytest.fixture
def tmp_openmanus_home(tmp_path, monkeypatch):
    """Provide isolated ~/.openmanus directory for tests."""
    home = tmp_path / "openmanus_home"
    home.mkdir()
    monkeypatch.setenv("OPENMANUS_HOME", str(home))
    return home
```

### 测试命名

`test_<场景>_<预期>`：

```python
# ✅ 清晰的测试命名
def test_list_tools_returns_deepagents_builtin_and_user():
    ...

def test_delete_main_topic_raises_error():
    ...

def test_get_nonexistent_topic_returns_none():
    ...

# ❌ 模糊的命名
def test_tools():
    ...

def test_error():
    ...
```

### 异步测试

```python
# ✅ 自动识别 async 测试（asyncio_mode = "auto"）
async def test_create_topic():
    topic = await TopicStore.create(title="Test")
    assert topic.id is not None

# ❌ 不要手动添加 @pytest.mark.asyncio
@pytest.mark.asyncio   # ❌ 多余
async def test_create_topic():
    ...
```

### 覆盖率目标

**80%+ 代码覆盖率，关键路径 100%。**

```bash
cd backend && uv run pytest tests/ --cov=openmanus --cov-report=term-missing
```

---

## 16. 代码复杂度

**控制函数规模和嵌套深度，保持可读性。**

| 指标 | 阈值 | 超出时的处理 |
|------|------|-------------|
| 函数体行数 | ≤ 50 行 | 拆分为子函数 |
| 函数参数数量 | ≤ 5 个 | 使用 Pydantic model 封装参数 |
| 嵌套层级 | ≤ 4 层 | 提前 return / 提取子函数 |
| 文件行数 | ≤ 400 行 | 拆分为多个模块 |

### 正确示例

```python
# ✅ 参数过多时用 model 封装
class CreateTopicRequest(BaseModel):
    title: str = Field(description="标题")
    workdir: Optional[str] = Field(default=None, description="工作目录")
    agent_name: Optional[str] = Field(default=None, description="Agent名称")

async def create_topic(req: CreateTopicRequest) -> Topic:
    ...
```

### 错误示例

```python
# ❌ 参数过多
async def create_topic(
    title: str, workdir: str, agent: str,
    model: str, kind: str, metadata: dict,
) -> Topic:
    ...

# ❌ 嵌套过深
async def process(data):
    if data:
        if data.items:
            for item in data.items:
                if item.active:
                    if item.type == "task":
                        ...  # 5 层嵌套 ❌
```

---

## 17. 反模式清单

**以下模式在 OpenManus 代码库中禁止使用。**

### 可变默认参数

```python
# ❌ 可变默认参数 — 共享状态 bug
def append_to(item: str, items: list[str] = []):
    items.append(item)
    return items

# ✅ 使用 None + 内部创建
def append_to(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items
```

### None 比较

```python
# ❌ ==
if value == None:
    ...

# ✅ is
if value is None:
    ...

# ✅ is not
if value is not None:
    ...
```

### Wildcard 导入

```python
# ❌ 命名空间污染
from os.path import *
from openmanus.common.response import *

# ✅ 显式导入
from os.path import join, exists
from openmanus.common.response import ApiResponse, ApiListResponse
```

### 字符串拼接循环

```python
# ❌ O(n²)
result = ""
for item in items:
    result += str(item)

# ✅ O(n)
result = "".join(str(item) for item in items)
```

### print() 替代 logging

```python
# ❌ print
print(f"Processing {name}")

# ✅ loguru
from openmanus.log import logger
logger.info("Processing %s", name)
```

### type() 比较

```python
# ❌
if type(obj) == list:
    ...

# ✅
if isinstance(obj, list):
    ...
```

### 遮蔽内建名称

```python
# ❌ 遮蔽 list / dict / str / id
def process(list: list[str], id: str) -> dict: ...

# ✅ 使用描述性名称
def process(items: list[str], item_id: str) -> dict: ...
```

---

## 附录 A：模块索引

| 模块 | 路径 | 职责 |
|------|------|------|
| `agents` | `openmanus/agents/` | Agent 定义、加载、工厂、头像 |
| `llm` | `openmanus/llm/` | LLM 接入层（ChatGLM） |
| `skills` | `openmanus/skills/` | Skill 加载、嵌入 Python 执行 |
| `tools` | `openmanus/tools/` | 工具加载、调度、邮箱/白板工具 |
| `sandbox` | `openmanus/sandbox/` | 文件读写沙箱、目录监听 |
| `runtime` | `openmanus/runtime/` | SSE 引擎、事件协议、Channel、健康检查 |
| `topics` | `openmanus/topics/` | Topic/Session CRUD、邮箱/白板存储、TopicFlow |
| `db` | `openmanus/db/` | DB 路径、Schema DDL、初始化 |
| `common` | `openmanus/common/` | 响应包装、异常定义 |
| `middleware` | `openmanus/middleware/` | AgentTrace、Retry、ToolGuard 中间件 |
| `memory` | `openmanus/memory/` | LangGraph Checkpointer |
| `log` | `openmanus/log/` | loguru 日志初始化 |

---

## 附录 B：检查清单

每次代码提交前，确认：

### 模块结构
- [ ] 新文件放在正确的领域模块下
- [ ] `__init__.py` 已导出关键类/函数
- [ ] 无 `api/` 中间层残留

### Router
- [ ] 无 `raise HTTPException`
- [ ] 使用 `ApiResponse.ok()` / `ApiResponse.fail()` / `ApiListResponse.ok()` / `ApiListResponse.fail()`
- [ ] 每个路由声明了 `response_model`

### 导入
- [ ] 全部 `from openmanus.xxx` 绝对导入
- [ ] 导入顺序：stdlib → third-party → local
- [ ] 无 wildcard import

### 命名
- [ ] 公开函数动词开头
- [ ] 无以 `_` 开头但被外部引用的函数

### 类型与返回
- [ ] loader/service/store 返回 Pydantic 对象，不返回裸 `dict`
- [ ] 所有函数/方法（除 router 外）有参数类型和返回类型
- [ ] 使用 Python 3.12+ 类型语法（`list[]`、`X | None`）

### 对象定义
- [ ] 使用 `BaseModel`，未使用 `dataclass`
- [ ] 字段使用 `Field()` 定义，包含 `description`（中文）

### 错误处理
- [ ] 无 bare `except`
- [ ] 异常链使用 `from e`
- [ ] 抛出 `OpenManusError` 子类，不抛裸 `Exception`

### 异步
- [ ] I/O 操作使用 `async def`
- [ ] async 函数中无阻塞调用（`requests`、`time.sleep`）

### 安全
- [ ] SQL 参数化查询，无 f-string 拼接
- [ ] 无硬编码密钥

### 日志
- [ ] 使用 `from openmanus.log import logger`
- [ ] 无 `print()` 语句
- [ ] 日志级别正确（DEBUG/INFO/WARNING/ERROR）

### 测试
- [ ] 涉及文件系统的测试使用 `tmp_openmanus_home` fixture
- [ ] 测试命名 `test_<场景>_<预期>`
- [ ] async 测试无 `@pytest.mark.asyncio` 标记

### 代码复杂度
- [ ] 函数体 ≤ 50 行
- [ ] 函数参数 ≤ 5 个
- [ ] 嵌套 ≤ 4 层
- [ ] 文件 ≤ 400 行

### 反模式
- [ ] 无可变默认参数
- [ ] 使用 `is None` 而非 `== None`
- [ ] 无字符串拼接循环
- [ ] 无内建名称遮蔽
