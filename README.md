# FaaS · 飞书捷径智能任务系统

一个端到端的「**飞书多维表格字段捷径 → 自建后端 → Coze 工作流**」示例系统：用户在飞书多维表格的「字段捷径」中选择任务类型并输入文本，前端插件调用自建的 FastAPI 后端，后端再调用对应的 [Coze](https://www.coze.cn/) 工作流完成 **情感分析 / 文本摘要 / 翻译 / 实体提取** 等 NLP 任务，并将结果写回表格字段。

> 本项目为「易有料」实习期间的项目，仓库以演示与学习为目的。

## 📦 仓库组成

这是一个 monorepo，包含两个相互配合的子项目，各自有独立的 README：

| 子项目 | 角色 | 技术栈 | 文档 |
|--------|------|--------|------|
| [`field-demo-main/`](field-demo-main/README.md) | **前端**：飞书多维表格「字段捷径」插件，提供配置界面并调用后端 | TypeScript + `@lark-opdev/block-basekit-server-api` | [README](field-demo-main/README.md) |
| [`feishu-shortcut-backend/`](feishu-shortcut-backend/README.md) | **后端**：接收请求、按任务类型路由并调用 Coze 工作流，返回结果 | FastAPI + Celery + PostgreSQL + Redis | [README](feishu-shortcut-backend/README.md) |

此外，根目录还包含：

- [`faas.md`](faas.md) — 详细的系统设计与实现说明文档。
- [`系统架构图.html`](系统架构图.html) — 可在浏览器中打开查看的架构图。

## 🏗️ 整体架构与数据流

```text
┌─────────────────────────────────────────────┐
│ 飞书多维表格 · 字段捷径 (field-demo-main 前端) │
│ 用户配置：API 凭证 / 任务类型 / 信息输入        │
└───────────────────────┬─────────────────────┘
                        │  POST /api/chat
                        ▼
┌─────────────────────────────────────────────┐
│ FastAPI 后端 (feishu-shortcut-backend, :6921) │
│ 1. 校验请求 (api_key_binding)                  │
│ 2. 查询 task_coze 表，按 task_selection        │
│    取得对应的 Coze workflow_id / token         │
│ 3. 在请求处理过程中通过 httpx 直接调用 Coze     │
│    工作流并等待结果                             │
└───────────────────────┬─────────────────────┘
                        │  https://api.coze.cn/v1/workflow/run
                        ▼
┌─────────────────────────────────────────────┐
│ Coze 工作流（情感分析/摘要/翻译/实体提取）       │
└───────────────────────┬─────────────────────┘
                        │  返回结果
                        ▼
        结果写回飞书多维表格字段（task_id / status / result / ...）
```

> **关于 Celery/Flower**：后端已集成 Celery 任务队列与 Flower 监控（端口 `5555`）作为异步基础设施，但当前 `/api/chat` 路径是在请求处理过程中通过 `httpx` 直接调用 Coze 工作流并同步返回结果，并未经过 Celery 队列分发。详见后端 README。

## 🛠️ 技术栈

| 层 | 主要技术 |
|----|----------|
| 前端插件 | TypeScript，`@lark-opdev/block-basekit-server-api`（CLI：`@lark-opdev/block-basekit-cli`） |
| 后端框架 | FastAPI 0.104.1，Uvicorn |
| 异步任务 | Celery 5.3.4，Flower 2.0.1 |
| 数据库 | PostgreSQL 16.3（`asyncpg`） |
| 缓存 / 消息代理 | Redis 7 |
| HTTP 客户端 | httpx 0.25.2 |
| 外部能力 | Coze 工作流（`api.coze.cn`） |
| 部署 | Docker & Docker Compose |

## 🚀 快速开始

两个子项目分别启动，完整步骤请见各自的 README。

### 1. 启动后端（feishu-shortcut-backend）

```bash
cd feishu-shortcut-backend
cp .env.example .env        # 按需填写数据库、Redis、webhook 等配置
docker-compose up -d --build
docker-compose exec backend python init_db.py init   # 初始化数据库与任务配置
```

- 后端服务：`http://localhost:6921`
- API 文档：`http://localhost:6921/docs`
- Celery 监控（Flower）：`http://localhost:5555`

详见 [`feishu-shortcut-backend/README.md`](feishu-shortcut-backend/README.md)。

### 2. 构建并发布前端插件（field-demo-main）

```bash
cd field-demo-main
npm install
npm run start    # 本地调试
npm run pack     # 打包，生成 output/output.zip
```

将 `output/output.zip` 上传到飞书多维表格「字段捷径」平台即可。

> ⚠️ 前端默认请求的后端地址硬编码在 [`field-demo-main/src/index.ts`](field-demo-main/src/index.ts) 中（`apiUrl` 及 `addDomainList`），部署到自己的服务器时请改为你自己的后端地址，并同步更新 `addDomainList` 白名单。

详见 [`field-demo-main/README.md`](field-demo-main/README.md)。

## 📂 目录结构

```text
FaaS/
├── feishu-shortcut-backend/   # FastAPI + Celery 后端服务
│   ├── main.py                # FastAPI 应用与 API 端点
│   ├── celery_app.py          # Celery 配置
│   ├── init_db.py             # 数据库初始化脚本
│   ├── docker-compose.yml     # 一键部署编排
│   ├── Dockerfile
│   ├── .env.example           # 环境变量示例
│   └── README.md
├── field-demo-main/           # 飞书多维表格字段捷径插件（前端）
│   ├── src/index.ts           # 插件主逻辑（表单、调用后端、结果渲染）
│   ├── config.json            # 本地调试配置
│   ├── package.json
│   └── README.md
├── faas.md                    # 详细设计文档
└── 系统架构图.html             # 架构图（浏览器打开）
```

## 🔌 后端核心接口（速览）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat` | 执行任务：传入 `api_key_binding` / `task_selection` / `information_input`，调用 Coze 工作流并返回结果 |
| `GET` | `/api/task/{task_id}` | 查询任务状态 |
| `GET` | `/api/tasks/all` | 获取所有可用任务类型 |
| `GET` | `/api/system/status` | 系统状态（活跃任务、Redis/Celery 状态等） |
| `GET` | `/health` | 健康检查 |
| `GET` | `/docs` | 自动生成的 API 文档 |

## 🔐 安全说明

- 请勿将真实的数据库密码、Coze Token、webhook 地址等敏感信息提交到仓库；后端使用 `.env`（已在示例中以占位符给出），请在本地/服务器自行填写。
- 前端 `config.json` 中的账号密码仅为本地调试占位示例，正式使用请替换。
- 部署前请修改前端硬编码的后端地址（见上文）。

## 📄 许可证

本仓库为实习期间项目，暂未声明开源许可证；如需复用代码，请先与作者及相关方确认授权。
