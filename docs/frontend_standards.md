# 前端开发规范

> 本文档定义 OpenManus 前端代码的组织结构、数据流、命名约定、样式系统和组件设计模式。
> 所有前端开发必须遵循以下规范，确保代码一致性、可维护性和类型安全。

---

## 1. 单向数据流

**只允许 `view → store → service` 的调用链路，禁止 `view → service` 直接调用。**

### 正确示例

```javascript
// ✅ 正确
const AgentsView = observer(() => {
    const {agentStore} = useStore();
    useEffect(() => {
        agentStore.loadAgents();
    }, []);
    return <div>{agentStore.agents.map(...)}</div>;
});

// stores/agent-store.js
class AgentStore {
    async loadAgents() {
        const resp = await agentService.listAgents();
        runInAction(() => {
            this.agents = resp.data || [];
        });
    }
}
```

### 错误示例

```javascript
// ❌ 错误 - view 直接调用 service
const AgentsView = () => {
    const [agents, setAgents] = useState([]);
    useEffect(() => {
        agentService.listAgents().then(resp => setAgents(resp.data));
    }, []);
};
```

---

## 2. 数据状态管理

**对象数据** → store 层管理
- 多个组件共用的数据（如 topics、agents）
- 需要持久化的业务数据
- 跨页面共享的状态

**交互状态数据** → view 层管理（通过 `useState` hook）
- loading / saving 等加载状态
- 表单输入的临时状态
- UI 交互状态（展开/折叠、选中项等）

### 正确示例

```javascript
// ✅ 对象数据在 store，交互状态在 view
class AgentStore {
    agents = [];         // ✅ 共享数据
    current = null;      // ✅ 业务数据
    
    async loadAgents() {
        const resp = await agentService.listAgents();
        runInAction(() => {
            this.agents = resp.data || [];
        });
    }
}

const AgentsView = observer(() => {
    const {agentStore} = useStore();
    const [loading, setLoading] = useState(false);  // ✅ 交互状态
    
    useEffect(() => {
        setLoading(true);
        agentStore.loadAgents().finally(() => setLoading(false));
    }, []);
});
```

### 错误示例

```javascript
// ❌ 把 loading 放在 store 中
class AgentStore {
    agents = [];
    loading = false;     // ❌ loading 是 UI 交互状态，不属于 store
}

// ❌ 把共享数据放在 view
const TopicListView = () => {
    const [topics, setTopics] = useState([]);  // ❌ topics 是共享数据
};
```

---

## 3. ES6 语法与导入规范

**全部使用 ES6+ 语法。导入按分组排序，使用 `@/` 路径别名。**

### ES6 语法要求

| 语法 | 正确 | 错误 |
|------|------|------|
| 变量声明 | `const` / `let` | `var` |
| 组件 | 箭头函数 `const X = () => {}` | `function X() {}` |
| 导出 | `export default` / `export const` | `module.exports` |
| 解构 | `const {a, b} = obj` | `obj.a; obj.b` |
| 模板字面量 | `` `Hello ${name}` `` | `"Hello " + name` |
| 可选链 | `user?.name` | `user && user.name` |

### 导入顺序

按以下四组排序，组间空一行：

1. **React 核心**：`react`、`react-dom`、`react-router-dom`
2. **第三方库**：`mobx`、`axios`、`lucide-react`、`sonner`
3. **项目内部**：`@/stores/`、`@/services/`、`@/components/`、`@/hooks/`、`@/utils/`
4. **样式**：`@/index.css`、组件样式

### 正确示例

```javascript
// ✅ React 核心
import {observer} from "mobx-react-lite";
import {useEffect, useState} from "react";
import {useNavigate} from "react-router-dom";

// ✅ 第三方库
import {Bot, Lock, Wrench} from "lucide-react";

// ✅ 项目内部
import {useStore} from "@/hooks/use-store.jsx";
import {AgentAvatar} from "@/components/avatar.jsx";
import {FancyButton} from "@/components/ui/fancy-button.jsx";

// ✅ 样式（如有）
import "@/index.css";
```

### 错误示例

```javascript
// ❌ 导入顺序混乱
import {FancyButton} from "@/components/ui/fancy-button.jsx";
import {useEffect} from "react";
import {Bot} from "lucide-react";
import {useStore} from "@/hooks/use-store.jsx";

// ❌ 使用相对路径
import {AgentAvatar} from "../../components/avatar.jsx";  // ❌ 应使用 @/

// ❌ wildcard 导入
import * as React from "react";  // ❌
```

---

## 4. Service 层与错误处理

**Service 层仅封装 HTTP 调用，不包含业务逻辑。错误通过 axios 拦截器统一 toast 提示。**

### Service 标准格式

```javascript
// services/tool-service.js
import axios from "@/services/axios.js";

class ToolService {
    service = import.meta.env.VITE_BACKEND_URL;

    async listTools() {
        return await axios.get(`${this.service}/tools`);
    }

    async getToolTree(name) {
        return await axios.get(`${this.service}/tools/${name}/tree`);
    }

    async getToolFile(name, path) {
        return await axios.get(`${this.service}/tools/${name}/file`, {
            params: {path}
        });
    }
}

export default new ToolService();
```

### Axios 拦截器统一错误提示

**错误信息通过 shadcn/ui 的 sonner 组件统一 toast，无需在各 view 中手动处理网络错误。**

```javascript
// services/axios.js
import Axios from "axios";
import {toast} from "sonner";

const axios = Axios.create({
    baseURL: import.meta.env.VITE_BACKEND_URL,
    timeout: 30000,
});

// Response interceptor
axios.interceptors.response.use(
    (response) => response.data,  // ✅ 自动解包 response.data
    (error) => {
        const msg = error.response?.data?.error?.message
            || error.response?.data?.detail
            || error.response?.data?.message
            || error.message
            || "Network error";
        
        toast.error(msg);  // ✅ 统一错误 toast
        return Promise.reject(error);
    },
);

export default axios;
```

### 错误提示规则

| 场景 | 处理方式 | 执行者 |
|------|---------|--------|
| 网络/服务端错误 | `toast.error(msg)` | axios 拦截器（自动） |
| 业务校验失败 | `toast.error(msg)` | axios 拦截器（自动） |
| 操作成功提示 | `toast.success(msg)` | View 层（自主决策） |
| 操作确认提示 | `toast.info(msg)` | View 层（自主决策） |

### Store 层错误处理

Store 层 **不** 处理 UI 提示，只捕获和存储错误状态：

```javascript
// ✅ 正确 - Store 只存储错误状态
class TopicStore {
    error = null;
    
    async load() {
        this.error = null;
        try {
            const resp = await topicService.listTopics();
            runInAction(() => { this.topics = resp.data || []; });
        } catch (e) {
            // toast 已由 axios 拦截器处理，Store 只存储错误状态
            runInAction(() => { this.error = e.message; });
        }
    }
}

// ❌ 错误 - Store 中调用 toast
class TopicStore {
    async load() {
        try {
            // ...
        } catch (e) {
            toast.error(e.message);  // ❌ 不应由 Store 处理 UI 提示
        }
    }
}
```

---

## 5. Store 层规范

**使用 MobX observable store，`makeAutoObservable` 管理响应式状态。异步操作使用 `runInAction` 更新状态。**

### Store 标准格式

```javascript
import {makeAutoObservable, runInAction} from "mobx";
import topicService from "@/services/topic-service.js";

class TopicStore {
    topics = [];
    activeTopicId = null;

    constructor() {
        makeAutoObservable(this);
    }

    get active() {
        return this.topics.find((t) => t.id === this.activeTopicId) || null;
    }

    async load() {
        try {
            const resp = await topicService.listTopics();
            runInAction(() => {
                this.topics = resp.data || [];
            });
        } catch (e) {
            // toast 已由 axios 拦截器处理
            runInAction(() => { this.error = e.message; });
        }
    }
}

export default TopicStore;
```

### MobX 规则

| 规则 | 说明 |
|------|------|
| `makeAutoObservable` | Store 构造函数中调用，自动追踪所有属性 |
| `runInAction` | async 函数中更新 observable 必须包裹在 `runInAction` 中 |
| `get` 计算属性 | 不需要 `runInAction`，MobX 自动追踪 |
| 单例 | service 类用 `export default new XxxService()`，store 类由 `StoreProvider` 管理 |

---

## 6. View 层组件拆分

**View 层只负责 UI 渲染和交互状态，业务数据通过 store 获取。按职责拆分为容器组件和展示组件。**

### 组件拆分原则

| 组件类型 | 职责 | 可使用 |
|----------|------|--------|
| 容器组件 | 数据获取、路由、store 交互 | store、useEffect、router |
| 展示组件 | 纯 UI 渲染 | props、useState（交互状态） |
| 页面组件 | 页面布局 + 容器组合 | 容器组件 + 展示组件 |

### 正确示例

```javascript
// ✅ 容器组件 — 拥有数据
const AgentsView = observer(() => {
    const {agentStore} = useStore();
    const navigate = useNavigate();

    useEffect(() => {
        agentStore.loadAgents().then();
    }, [agentStore]);

    return (
        <div>
            {agentStore.agents.map((a) => (
                <AgentCard key={a.name} agent={a} onClick={() => navigate(a.name)}/>
            ))}
        </div>
    );
});

// ✅ 展示组件 — 纯渲染
const AgentCard = ({agent, onClick}) => {
    return (
        <button onClick={onClick} className="rounded-card p-6">
            <AgentAvatar agent={agent} size={44}/>
            <span>{agent.name}</span>
        </button>
    );
};
```

### 复杂度阈值

| 指标 | 阈值 | 超出时的处理 |
|------|------|-------------|
| 组件函数体 | ≤ 80 行 | 拆分子组件 |
| 嵌套层级 | ≤ 4 层 | 提前 return / 提取子组件 |
| Props 数量 | ≤ 6 个 | 合并为对象 prop |
| 文件行数 | ≤ 400 行 | 拆分为多个组件文件 |

---

## 7. 自定义 Hook

**Hook 文件使用 `use-xxx.jsx` 命名，导出 `useXxx` 函数。**

### 标准格式

```javascript
// hooks/use-store.jsx
import {useContext} from "react";
import {MobxContext} from "@/stores/index.js";

export function useStore() {
    const context = useContext(MobxContext);
    if (!context) throw new Error("useStore must be used within StoreProvider");
    return context;
}

export const StoreProvider = MobxContext.Provider;
```

### Hook 规则

| 规则 | 说明 |
|------|------|
| 命名 | `use-xxx.jsx` 文件，`useXxx` 函数名 |
| 只在最顶层调用 | 不在循环、条件、嵌套函数中调用 |
| 只在组件/其他 Hook 中调用 | 不在普通 JS 函数中调用 |
| useEffect 依赖完整 | 不遗漏依赖项 |
| useEffect 目的正确 | 仅用于外部系统同步，不用于数据转换 |

---

## 8. Axios 实例与拦截器

**全局唯一 axios 实例，统一配置 baseURL、timeout 和拦截器。**

### 当前配置

```javascript
// services/axios.js
import Axios from "axios";
import {toast} from "sonner";

const axios = Axios.create({
    baseURL: import.meta.env.VITE_BACKEND_URL,
    timeout: 30000,
});

axios.interceptors.response.use(
    (response) => response.data,
    (error) => { /* ... toast.error(msg); ... */ },
);

export default axios;
```

### Vite proxy 配置

Vite proxy 配置（vite.config.js）确保开发时 API 请求正确转发：

```javascript
// vite.config.js — proxy 配置
proxy: {
    '/topics': { target: 'http://127.0.0.1:8999', changeOrigin: true },
    '/agents': { target: 'http://127.0.0.1:8999', changeOrigin: true },
    '/tools': { target: 'http://127.0.0.1:8999', changeOrigin: true },
    '/skills': { target: 'http://127.0.0.1:8999', changeOrigin: true },
    '/sandbox': { target: 'http://127.0.0.1:8999', changeOrigin: true },
}
```

---

## 9. 目录结构规范

### 前端项目结构

```
frontend/src/
├── app.jsx                  # App 根组件
├── main.jsx                 # 入口（createRoot + Provider）
├── router.jsx               # 路由配置
├── providers.jsx            # AppProviders（主题等）
├── index.css                # 全局样式 + Tailwind
├── components/              # 共享组件
│   ├── ui/                  # shadcn/ui 基础组件（button、dialog、toast...）
│   ├── avatar.jsx           # Agent 头像组件
│   ├── header.jsx           # 全局 Header
│   └── window-controls.jsx  # 桌面窗口控制
├── views/                   # 页面视图（按功能域组织）
│   ├── agents/              # Agent 管理域
│   │   ├── agents-view.jsx  # Agent 列表页
│   │   ├── create-agent.jsx # 创建 Agent
│   │   └── agent-editor.jsx # Agent 编辑器
│   └── ...                  # 其他功能域
├── stores/                  # MobX Store（每域一个）
│   ├── index.js             # Store 注册 + MobxContext
│   ├── agent-store.js       # Agent 数据管理
│   ├── topic-store.js       # Topic 数据管理
│   ├── tool-store.js        # Tool 数据管理
│   ├── skill-store.js       # Skill 数据管理
│   └── sandbox-store.js     # Sandbox 数据管理
├── services/                # HTTP Service（每域一个）
│   ├── axios.js             # 全局 axios 实例 + 拦截器
│   ├── agent-service.js     # Agent API
│   ├── topic-service.js     # Topic API
│   ├── tool-service.js      # Tool API
│   ├── skill-service.js     # Skill API
│   ├── sandbox-service.js   # Sandbox API
│   └── runtime-service.js   # Runtime/SSE API
├── hooks/                   # 自定义 Hooks
│   ├── use-store.jsx        # Store 访问 Hook
│   └── use-theme.js         # 主题切换 Hook
├── runtime/                 # SSE 运行时（独立子系统）
│   ├── stream-client.js     # SSE 传输层
│   ├── event-reducer.js     # 事件归约
│   ├── message-store.js     # 消息存储
│   └── agent-runtime.js     # Agent 运行时管理
├── lib/                     # 工具库
│   └── utils.js             # cn() Tailwind 合并工具
└── utils/                   # 业务工具函数
    └── time.js              # 时间格式化
```

### 目录职责

| 目录 | 职责 | 依赖方向 |
|------|------|---------|
| `components/ui/` | shadcn/ui 基础组件，不依赖业务 | 被所有组件依赖 |
| `components/` | 共享业务组件 | 依赖 ui/、stores/、hooks/ |
| `views/` | 页面级视图 | 依赖 components/、stores/、hooks/ |
| `stores/` | 数据状态管理 | 依赖 services/ |
| `services/` | HTTP 调用封装 | 依赖 axios.js |
| `hooks/` | 自定义 React Hook | 依赖 stores/、lib/ |
| `runtime/` | SSE 实时通信 | 依赖 services/ |
| `lib/` | 通用工具 | 无外部依赖 |
| `utils/` | 业务工具函数 | 无外部依赖 |

---

## 10. 命名规范

**组件 PascalCase 命名，文件 kebab-case 命名。使用 `@/` 路径别名。**

### 组件命名

| 类型 | 组件名 | 文件名 |
|------|--------|--------|
| 页面组件 | `AgentsView` | `agents-view.jsx` |
| 展示组件 | `AgentCard` | `agent-card.jsx`（独立文件时） |
| UI 基础组件 | `FancyButton` | `fancy-button.jsx` |
| 自定义 Hook | `useStore` | `use-store.jsx` |
| Store 类 | `TopicStore` | `topic-store.js` |
| Service 类 | `ToolService` | `tool-service.js` |

### 事件处理命名

内部处理函数 `handleXxx`，对应 prop `onXxx`：

```javascript
// ✅ 正确
const AgentCard = ({agent, onClick}) => {
    const handleClick = () => {
        onClick(agent.name);  // prop
    };
    return <button onClick={handleClick}>{agent.name}</button>;
};

// ❌ 错误
const AgentCard = ({agent, onClick}) => {
    return <button onClick={() => onClick(agent.name)}>{agent.name}</button>;
    // 内联函数每次渲染都创建新引用，可能导致子组件不必要的重渲染
};

// ❌ 混淆命名
const AgentCard = ({agent, onSelect}) => {
    const handleClick = () => onSelect(agent.name);
    return <button onClick={handleClick}>{agent.name}</button>;
};  // onSelect vs onClick 不一致
```

### 布尔 Prop 命名

```javascript
// ✅ 加前缀 is/has/can
<FancyButton isLoading={true} hasError={false} canSubmit={true} />

// ❌ 不加前缀
<FancyButton loading={true} error={false} submit={true} />
```

### 变量命名

```javascript
// ✅ 描述性命名
const activeTopics = topics.filter(t => t.id !== MAIN_TOPIC_ID);
const sortedTopics = [...topics].sort(compareByDate);

// ❌ 无意义缩写
const at = topics.filter(t => t.id !== MAIN_TOPIC_ID);
const st = [...topics].sort(compareByDate);
```

---

## 11. 样式规范（Tailwind + shadcn/ui）

**优先使用 shadcn/ui 组件，配合 Tailwind 原子类定制项目风格。禁止内联 style。**

### 组件使用优先级

1. **shadcn/ui 组件**（`components/ui/`）— 优先使用现有组件
2. **Tailwind 原子类** — 用原子类组合自定义样式
3. **@apply** — 仅在无法用原子类直接解决时使用，每个 @apply 最多包含 5 个属性
4. **内联 style** — 禁止

### 当前 shadcn/ui 组件清单

| 组件 | 文件 | 用途 |
|------|------|------|
| `AlertDialog` | `alert-dialog.jsx` | 确认弹窗 |
| `Button` | `button.jsx` | 通用按钮 |
| `Collapsible` | `collapsible.jsx` | 折叠面板 |
| `DropdownMenu` | `dropdown-menu.jsx` | 下拉菜单 |
| `FancyButton` | `fancy-button.jsx` | 高亮按钮 |
| `LoadingState` | `loading-state.jsx` | 加载状态 |
| `Popover` | `popover.jsx` | 浮层弹出 |
| `ScrollArea` | `scroll-area.jsx` | 滚动区域 |
| `Select` | `select.jsx` | 下拉选择 |
| `Sonner/Toaster` | `sonner.jsx` | Toast 提示 |
| `Tabs` | `tabs.jsx` | 标签页切换 |
| `Tooltip` | `tooltip.jsx` | 提示浮层 |

### Tailwind 类名约定

| 场景 | 约定 | 示例 |
|------|------|------|
| 自定义 class | 语义化命名，不以 `tw-` 开头 | `rounded-card`、`h-display`、`font-display` |
| 布局 | 先布局后视觉 | `flex gap-3 p-6 rounded-card` → flex → gap → padding → visual |
| 响应式 | 移动优先 | `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` |
| 深色模式 | 使用 CSS 变量 | `bg-background text-foreground`（而非 `bg-white text-black`） |
| 条件样式 | `cn()` 合并 | `cn("rounded-card", isActive && "border-primary")` |

### cn() 工具

使用 `lib/utils.js` 的 `cn()` 合并 Tailwind 类名：

```javascript
import {cn} from "@/lib/utils.js";

<div className={cn("rounded-card p-6", isActive && "border-primary")} />
```

### JSX 属性顺序

```jsx
// ✅ 属性排序：ref → key → events → className → others
<div
    ref={containerRef}
    key={item.id}
    onClick={handleClick}
    className={cn("rounded-card", isActive && "bg-primary")}
    data-id={item.id}
/>
```

---

## 17. 视觉风格规范

**OpenManus 遵循"editorial dark, bold minimal"设计语言。内容主导，界面隐退。**

### 设计哲学

| 原则 | 说明 | 示例 |
|------|------|------|
| **克制用色** | 单一高饱和度强调色，避免彩虹调色板 | 深色模式：lime accent (#b5ff6d)；亮色模式：deep green (#30af5b) |
| **边界优先** | Hairline 边框代替阴影，分层代替漂浮 | `.rounded-card` 用 1px 边框，无 box-shadow |
| **内容主导** | 界面元素淡化，让内容成为视觉焦点 | muted-foreground 用于标签、辅助信息 |
| **字体对比** | Display 字体（ClashDisplay）+ Body 字体（Satoshi）形成层级 | 标题用 `.h-display`，正文用默认 sans-serif |
| **动效克制** | 有限的 staggered entrance，无装饰性动画 | `.anim-rise` + `.anim-delay-{1..4}`，80ms 间隔 |

---

### 字体系统

**三种字体角色，各自负责不同层级：**

| 字体 | 用途 | CSS class | 来源 |
|------|------|-----------|------|
| **Satoshi** | 正文、UI 控件、标签 | `font-sans`（默认） | Fontshare（self-hosted） |
| **ClashDisplay** | 标题、强调文字 | `.font-display` / `.h-display` / `.h-section` | Fontshare（self-hosted） |
| **JetBrains Mono Variable** | 代码、Agent 输出、状态 | `.font-mono` / `code` / `pre` | @fontsource-variable |

**字体加载策略：**
- Satoshi 和 ClashDisplay 自托管（`/fonts/` 目录），Electron 离线可用
- 字重：Satoshi 400/500/700，ClashDisplay 500/600
- `font-display: swap` 避免 FOIT

**标题层级：**

| Class | 字号 | 行高 | 字间距 | 用途 |
|-------|------|------|--------|------|
| `.h-display` | 30px | 1.1 | -0.015em | 页面标题（Agents、Tools...） |
| `.h-section` | 16px | 1.2 | -0.01em | 区块小标题 |
| 默认 `h1`/`h2`/`h3` | ClashDisplay 500 | - | -0.01em | HTML 标题元素自动应用 |

---

### 色彩系统

#### 深色模式（default signature）

**"tinted near-black + lime accent"：**

| 语义变量 | HSL | 十六进制 | 用途 |
|----------|-----|---------|------|
| `--background` | 240 6% 4% | #0a0a0c | 页面背景（最深） |
| `--card` | 240 5% 7% | #111114 | 卡片背景（中层） |
| `--sidebar` | 240 5% 10% | #18181c | 侧边栏背景（上层） |
| `--foreground` | 230 100% 98% | #f6f7ff | 主文本（冷白） |
| `--muted-foreground` | 240 8% 85% | #d6d6de | 辅助文本、标签 |
| `--accent` | 88 100% 72% | #b5ff6d | **强调色（lime）** |
| `--border` | 240 7% 14% | #232328 | Hairline 边框 |

**分层逻辑：** `background < card < sidebar < popover`，通过明度递增形成层级。

#### 亮色模式（inverted signature）

**"cool off-white + deep green accent"：**

| 语义变量 | HSL | 十六进制 | 用途 |
|----------|-----|---------|------|
| `--background` | 240 20% 99% | #f7f8fa | 页面背景（微冷白） |
| `--card` | 0 0% 100% | #ffffff | 卡片背景 |
| `--sidebar` | 240 20% 96% | #ececee | 侧边栏背景 |
| `--foreground` | 240 6% 10% | #18181b | 主文本（近黑） |
| `--muted-foreground` | 240 5% 45% | #71717a | 辅助文本 |
| `--accent` | 142 57% 44% | #30af5b | **强调色（深绿）** |
| `--border` | 240 5% 90% | #e4e4e7 | Hairline 边框 |

**亮色注意：** lime (#b5ff6d) 在白色背景上对比度不足，必须用深绿 (#30af5b)。

#### 语义色（用于状态提示）

| 状态 | 深色 HSL | 亮色 HSL | 用途 |
|------|---------|---------|------|
| `success` | 152 50% 55% | 142 57% 38% | 成功提示、TeamLeader 角色 |
| `warning` | 38 80% 60% | 38 80% 40% | 警告提示、Coder 角色 |
| `info` | 199 70% 65% | 199 70% 42% | 信息提示、Researcher 角色 |
| `destructive` | 0 60% 55% | 0 70% 48% | 错误提示、删除操作 |

#### Agent 角色色（用于 Avatar 和群聊视图）

| 角色 | 深色 HSL | 用途 |
|------|---------|------|
| `teamleader` | 152 50% 55% | 协调者（绿） |
| `researcher` | 199 70% 65% | 研究者（天蓝） |
| `coder` | 38 80% 60% | 编码者（琥珀） |
| `user` | 240 5% 70% | 用户（灰） |
| `system` | 0 60% 55% | 系统（红） |

**使用方式：** `.dot-teamleader`、`.text-role-coder` 等 utility classes。

---

### 布局原语（Component Primitives）

**预定义 CSS class，避免重复手写 Tailwind 组合：**

| Class | 说明 | 常见用途 |
|-------|------|---------|
| `.surface-card` | 淡色表面 + hairline 边框，无阴影 | 卡片容器 |
| `.surface-raised` | 更强的 raised surface | hover/active 状态 |
| `.rounded-card` | 24px 圆角 + 透明背景 + hairline 边框 | Agent/Tool/Skill 卡片网格 |
| `.hairline-card` | 透明背景 + 底部 hairline（无侧/上边框） | 列表行（简历式布局） |
| `.card-icon-badge` | 圆形图标容器 + faint surface + accent 图标 | 卡片左上图标 |
| `.hairline` | 水平 hairline 分隔线 | 区块分隔 |

**`.rounded-card` 行为：**
- 深色：`background-color: hsl(var(--sidebar) / 0.18)`（浅色表面 lift）
- 亮色：`background-color: hsl(var(--foreground) / 0.025)`（淡暗表面）
- Hover：边框变亮，背景加深

**`.hairline-card` 行为：**
- 透明背景，无 box
- 只有底部 1px 边框
- Hover：边框变亮
- 列表感，非网格感

---

### 间距和圆角

| 变量/值 | 说明 | 常见用途 |
|---------|------|---------|
| `--radius` | 8px（base） | shadcn 组件默认圆角 |
| `rounded-lg` | `var(--radius)` = 8px | 中等圆角 |
| `rounded-3xl` / `.rounded-card` | 24px | 按钮、卡片（pillowy feel） |
| `gap-3` | 12px | Flex/Grid 子元素间距 |
| `gap-6` | 24px | 区块间距 |
| `p-6` | 24px padding | 卡片内边距 |
| `px-5 py-2` | 按钮 padding | FancyButton |

---

### 动效系统

#### 入场动效（Staggered Entrance）

```jsx
// ✅ 限制性 staggered entrance
<div className="anim-rise anim-delay-1">Card 1</div>
<div className="anim-rise anim-delay-2">Card 2</div>
<div className="anim-rise anim-delay-3">Card 3</div>
```

- `.anim-rise`: `translateY(8px) → 0` + `opacity: 0 → 1`
- Easing: `cubic-bezier(0.16, 1, 0.3, 1)`（premium feel）
- Delay: `anim-delay-{1..4}` = 80ms / 160ms / 240ms / 320ms
- **禁止** 全局入场动画，仅用于列表/卡片

#### Hover 微交互

| 交互 | 实现 | 用途 |
|------|------|------|
| Lift | `.lift-on-hover` → `translateY(-1px)` | 卡片、列表项 |
| Border brighten | `.rounded-card:hover` → 边框变亮 | 卡片 |
| Background tint | `.rounded-card:hover` → 背景加深 | 卡片 |
| Rippling fill | `FancyButton` → 色块从底部填充 | CTA 按钮 |

#### 状态动效

| 动效 | Class | 用途 |
|------|-------|------|
| Running pulse | `.animate-pulse-dot` | Session 运行中指示 |
| Typing cursor | `.typing-cursor::after` | Agent 流式输出光标 |
| Accent glow | `.accent-glow` | Active nav、CTA、running states |

#### 时间曲线

| 场景 | Easing | Duration |
|------|--------|----------|
| 入场/出场 | `cubic-bezier(0.16, 1, 0.3, 1)` | 400ms |
| Hover | `ease`（default） | 200ms |
| Button fill | `cubic-bezier(0.4, 0, 0, 1)` | 500ms（ripple） |
| Text roll | `cubic-bezier(0.16, 1, 0.3, 1)` | 700ms |

---

### 视觉层级

**从重到轻：**

| 层级 | 实现 | 示例 |
|------|------|------|
| **主内容** | `text-foreground` | 标题、正文 |
| **辅助内容** | `text-muted-foreground` | 描述、时间戳 |
| **标签** | `text-[11px] uppercase tracking-widest text-foreground/45` | "BUILT-IN"/"CUSTOM" 区块标题 |
| **元信息** | `text-[13px] text-muted-foreground` | Agent 描述 |
| **禁用** | `text-muted-foreground/50` | lock 图标 |

**标题 → 描述 → 标签 → 元信息，逐步淡化。**

---

### 交互模式

#### 按钮占比

| 按钮 | Class | 用途 |
|------|-------|------|
| **CTA / Primary** | `FancyButton`（variant="accent"） | 主操作（New Agent、Send） |
| **Secondary** | `Button` variant="outline" | 次操作 |
| **Text / Ghost** | `Button` variant="ghost" | 取消、辅助链接 |
| **Destructive** | `Button` variant="destructive" | 删除、危险操作 |

**FancyButton 行为：**
- 默认：白色 hairline outline（neutral）
- Hover：accent 色块从底部填充，文字变对比色
- **克制用色：** accent 仅在 hover 出现

#### Focus 状态

```jsx
// ✅ 键盘 focus ring
<button className="focus-ring">...</button>
```

- 双 ring：outer accent，inner background
- 满足 a11y visible focus 要求

#### Scrollbar

- 宽度：6px
- Track: transparent
- Thumb: `hsl(240 5% 20%)`（深色）
- Hover: `hsl(88 100% 72% / 0.4)`（accent-tinted）

---

### 新增页面检查清单

开发新页面/功能时，确保：

- [ ] 使用 `.h-display` 作为页面标题（ClashDisplay 字体）
- [ ] 使用 `.rounded-card` 作为卡片容器（24px 圆角 + hairline 边框）
- [ ] 标签用 `text-[11px] uppercase tracking-widest text-foreground/45`
- [ ] 描述用 `text-[13px] text-muted-foreground`
- [ ] CTA 按钮用 `FancyButton`
- [ ] 列表用 `.hairline-card`（简历式）或 `.rounded-card`（网格式）
- [ ] 深色/亮色模式都验证（accent 颜色不同）
- [ ] 无 box-shadow（用边框 + 背景 tint 代替）
- [ ] 动效仅用于入场/状态，无装饰性动画

---

## 12. 错误处理与提示

**错误信息通过 axios 拦截器 + sonner toast 统一提示，成功信息由 View 层自主决策。**

### 完整流程

```
Service 调用 → axios 发请求 → 响应拦截器
    ├── 成功 → 解包 response.data → 返回给 Store → View 更新
    └── 失败 → toast.error(msg) → Store 捕获 error 状态 → View 展示 error 状态
```

### Store 层错误处理

```javascript
// ✅ 正确
class TopicStore {
    error = null;
    
    async delete(id) {
        this.error = null;
        try {
            await topicService.deleteTopic(id);
            runInAction(() => {
                this.topics = this.topics.filter(t => t.id !== id);
            });
            // 成功提示由 View 层决定是否显示
        } catch (e) {
            runInAction(() => { this.error = e.message; });
            // toast.error 已由 axios 拦截器处理
        }
    }
}
```

### View 层成功提示

```javascript
// ✅ View 自主决定成功提示
const TopicList = observer(() => {
    const {topicStore} = useStore();
    const handleDelete = async (id) => {
        await topicStore.delete(id);
        if (!topicStore.error) {
            toast.success("Topic deleted");  // ✅ View 层自主 toast
        }
    };
});
```

### 禁止事项

```javascript
// ❌ Store 中调用 toast
class TopicStore {
    async delete(id) {
        try { /* ... */ } catch (e) {
            toast.error(e.message);  // ❌ 不应由 Store 处理 UI 提示
        }
    }
}

// ❌ View 中手动处理网络错误
const handleDelete = async (id) => {
    try {
        await topicService.deleteTopic(id);
    } catch (e) {
        toast.error(e.message);  // ❌ axios 拦截器已处理
    }
};

// ❌ 吞没错误
const handleDelete = async (id) => {
    try { /* ... */ } catch (e) { }  // ❌ 无处理
};
```

---

## 13. 安全规范

### XSS 防护

**禁止使用 `dangerouslySetInnerHTML`，除非输入经过 DOMPurify 消毒。**

```javascript
// ❌ 危险 - 未消毒的 HTML
<div dangerouslySetInnerHTML={{__html: userInput}} />

// ✅ 安全 - 纯文本渲染
<div>{userInput}</div>

// ✅ 安全 - 消毒后渲染（如 Markdown）
import DOMPurify from "dompurify";
<div dangerouslySetInnerHTML={{__html: DOMPurify.sanitize(html)}} />
```

### URL 安全

**验证用户输入的 URL scheme，只允许 http/https/mailto。**

```javascript
// ✅ 安全
function safeUrl(url) {
    try {
        const parsed = new URL(url);
        if (["http:", "https:", "mailto:"].includes(parsed.protocol)) return url;
    } catch {}
    return undefined;
}

// ❌ 危险 - 可能注入 javascript: URL
<a href={userUrl}>Visit</a>
```

### 敏感数据

**禁止在 localStorage 存储密钥、token 等敏感信息。** 当前项目 localStorage 使用：
- ✅ `openmanus.activeTopicId` — 主题 ID（低敏感）
- ✅ `openmanus.theme` — 主题偏好（非敏感）
- ❌ 不应存储 API key、access token、password

---

## 14. 组件设计模式

### Container / Presentational 拆分

| 类型 | 职责 | 数据来源 |
|------|------|---------|
| Container | 数据获取、路由、Store 交互 | Store / Service |
| Presentational | 纯 UI 渲染 | Props only |

```javascript
// ✅ Container — 拥有数据
const AgentsView = observer(() => {
    const {agentStore} = useStore();
    useEffect(() => { agentStore.loadAgents() }, [agentStore]);
    return <AgentList agents={agentStore.agents} onSelect={handleSelect}/>;
});

// ✅ Presentational — 纯渲染
const AgentList = ({agents, onSelect}) => (
    <div className="grid grid-cols-3 gap-3">
        {agents.map(a => <AgentCard key={a.name} agent={a} onSelect={onSelect}/>)}
    </div>
);
```

### 条件渲染

```javascript
// ✅ Early return 模式
const AgentDetail = ({agent}) => {
    if (!agent) return <EmptyState/>;
    return <div>...</div>;
};

// ❌ 嵌套三元
const AgentDetail = ({agent}) => (
    agent ? <div>...</div> : <EmptyState/>  // ❌ 复杂场景难以阅读
);

// ✅ 条件子组件
{agent.is_builtin && <Lock className="size-4"/>}
{!agent.is_builtin && <EditButton/>}
```

### 列表渲染

```javascript
// ✅ 始终使用唯一 key
{agents.map(a => <AgentCard key={a.name} agent={a}/>)}

// ❌ 使用 index 作为 key
{agents.map((a, i) => <AgentCard key={i} agent={a}/>)}  // ❌

// ❌ 无 key
{agents.map(a => <AgentCard agent={a}/>)}  // ❌
```

### 组件通信方式

| 场景 | 方式 | 说明 |
|------|------|------|
| 父→子 | Props | 最常见 |
| 子→父 | Callback props | `onSelect`, `onChange` |
| 跨组件 | Store | MobX observable store |
| 全局 | Context | 仅低频数据（theme/locale） |

---

## 15. 代码复杂度

**控制组件规模和嵌套深度，保持可读性。**

| 指标 | 阈值 | 超出时的处理 |
|------|------|-------------|
| 组件函数体 | ≤ 80 行 | 拆分子组件 |
| 嵌套层级 | ≤ 4 层 | 提前 return / 提取子组件 |
| Props 数量 | ≤ 6 个 | 合并为对象 prop |
| 单文件行数 | ≤ 400 行 | 拆分为多个文件 |
| useEffect 行数 | ≤ 20 行 | 提取为自定义 Hook |

### 拆分示例

```javascript
// ✅ 大组件拆分
// agents-view.jsx
const AgentsView = observer(() => {
    return (
        <div className="h-full overflow-y-auto">
            <Header/>
            <AgentGrid agents={agentStore.builtinAgents} title="Built-in"/>
            <AgentGrid agents={agentStore.userAgents} title="Custom"/>
        </div>
    );
});

// ✅ 提取展示子组件
const AgentGrid = ({agents, title}) => (
    <>
        <SectionTitle>{title}</SectionTitle>
        <div className="grid grid-cols-3 gap-3">
            {agents.map(a => <AgentCard key={a.name} agent={a}/>)}
        </div>
    </>
);
```

### Early Return 模式

```javascript
// ✅ Early return 减少嵌套
const ChatView = ({session}) => {
    if (!session) return <EmptyState/>;
    if (session.status === "loading") return <LoadingState/>;
    return <ChatPane session={session}/>;
};

// ❌ 嵌套过深
const ChatView = ({session}) => {
    if (session) {
        if (session.status === "loading") {
            return <LoadingState/>;
        } else {
            return <ChatPane session={session}/>;
        }
    } else {
        return <EmptyState/>;
    }
};
```

### 布尔命名

```javascript
// ✅ 肯定命名
const isVisible = true;
const isEnabled = false;
const hasError = true;

// ❌ 否定命名
const isNotHidden = true;   // ❌
const isNotDisabled = true; // ❌
```

---

## 16. 反模式清单

**以下模式在 OpenManus 前端代码中禁止使用。**

### 内联对象/函数创建

```javascript
// ❌ 每次渲染创建新对象/函数引用，导致子组件不必要重渲染
<Child style={{margin: 10}} onClick={() => doSomething()}/>

// ✅ 使用 useMemo/useCallback 或提前定义
const style = useMemo(() => ({margin: 10}), []);
const handleClick = useCallback(() => doSomething(), []);
<Child style={style} onClick={handleClick}/>
```

### Props 透传

```javascript
// ❌ 无差别透传所有 props
const Wrapper = (props) => <Child {...props}/>;  // ❌

// ✅ 显式声明需要的 props
const Wrapper = ({agent, onSelect}) => <AgentCard agent={agent} onSelect={onSelect}/>;
```

### 可变状态直接修改

```javascript
// ❌ MobX 外直接修改 observable
this.topics.push(newTopic);  // ✅ 在 runInAction 内可以

// ❌ React state 直接修改
state.items.push(newItem);  // ❌
setState(prev => [...prev, newItem]);  // ✅
```

### 数组 index 作为 key

```javascript
// ❌
{items.map((item, i) => <Card key={i} item={item}/>)}

// ✅ 使用唯一 ID
{items.map(item => <Card key={item.id} item={item}/>)}
```

### 条件渲染中的 Hook

```javascript
// ❌ Hook 在条件分支内调用
if (condition) {
    const [value, setValue] = useState(0);  // ❌ 违反 Hook 规则
}

// ✅ Hook 在顶层调用，条件在内部
const [value, setValue] = useState(0);
if (!condition) return null;
```

### useEffect 误用

```javascript
// ❌ 用 useEffect 同步派生状态
useEffect(() => {
    setFullName(`${firstName} ${lastName}`);  // ❌ 直接在 render 中计算
}, [firstName, lastName]);
const fullName = `${firstName} ${lastName}`;  // ✅

// ❌ 缺失依赖
useEffect(() => {
    fetchData(id);  // ❌ 缺少 id 依赖
}, []);

useEffect(() => {
    fetchData(id);  // ✅
}, [id]);
```

### 魔法字符串

```javascript
// ❌ 硬编码字符串
if (topic.id === "main") { /* ... */ }  // ❌

// ✅ 使用常量
import {MAIN_TOPIC_ID} from "@/stores/topic-store.js";
if (topic.id === MAIN_TOPIC_ID) { /* ... */ }  // ✅
```

### 组件内直接调用 print/console

```javascript
// ❌ 生产代码中的 console.log
console.log("debug:", data);  // ❌

// ✅ 移除或使用条件日志（开发环境）
if (import.meta.env.DEV) {
    console.log("debug:", data);  // ✅ 仅开发环境
}
```

---

## 附录 A：目录索引

| 目录 | 路径 | 职责 |
|------|------|------|
| UI 基础组件 | `src/components/ui/` | shadcn/ui 基础组件（button、dialog、toast） |
| 业务组件 | `src/components/` | 共享业务组件（avatar、header） |
| 页面视图 | `src/views/` | 按功能域组织的页面级组件 |
| 状态管理 | `src/stores/` | MobX observable store（每域一个） |
| HTTP 服务 | `src/services/` | API 调用封装（每域一个） + axios.js |
| 自定义 Hook | `src/hooks/` | React Hook（use-store、use-theme） |
| SSE 运行时 | `src/runtime/` | SSE 传输 + 事件归约 + 消息存储 |
| 工具库 | `src/lib/` | 通用工具（cn() 等） |
| 业务工具 | `src/utils/` | 业务工具函数（时间格式化等） |

---

## 附录 B：检查清单

每次代码提交前，确认：

### 数据流
- [ ] View 不直接调用 Service
- [ ] Store 不调用 toast（UI 提示由 axios 拦截器/View 处理）

### 导入
- [ ] 导入按分组排序（React → 第三方 → 项目内部）
- [ ] 使用 `@/` 路径别名，无相对路径
- [ ] 无 wildcard 导入

### 命名
- [ ] 组件 PascalCase，文件 kebab-case
- [ ] 事件处理 `handleXxx`，prop `onXxx`
- [ ] 布尔 prop 加 `is`/`has`/`can` 前缀

### 样式
- [ ] 优先使用 shadcn/ui 组件
- [ ] 样式使用 Tailwind 原子类，禁止内联 style
- [ ] 条件样式使用 `cn()` 合并
- [ ] 属性排序 ref → key → events → className → others

### 错误处理
- [ ] axios 拦截器统一 `toast.error()`（自动）
- [ ] 成功提示 View 层自主 `toast.success()`
- [ ] Store 不调用 toast
- [ ] 无吞没错误（空 catch）

### 安全
- [ ] 无 `dangerouslySetInnerHTML` 或已用 DOMPurify 消毒
- [ ] localStorage 不存敏感信息
- [ ] 外部 URL 验证 scheme

### 组件设计
- [ ] 容器/展示组件拆分合理
- [ ] 列表渲染使用唯一 key
- [ ] 条件渲染偏好 early return

### 代码复杂度
- [ ] 组件 ≤ 80 行，嵌套 ≤ 4 层
- [ ] Props ≤ 6 个
- [ ] 文件 ≤ 400 行

### 反模式
- [ ] 无内联对象/函数创建导致重渲染
- [ ] 无 Props 透传 `{...props}`
- [ ] 无数组 index 作为 key
- [ ] 无 Hook 在条件分支内调用
- [ ] 无 useEffect 同步派生状态
- [ ] 无魔法字符串/数字
- [ ] 无生产代码 console.log
