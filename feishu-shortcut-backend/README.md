# 飞书捷径后端服务

这是一个基于FastAPI和Celery的异步后端服务，用于处理飞书捷径中的Coze工作流调用。该服务支持高并发和长时间任务，提供异步任务处理能力。

## 项目概述

飞书捷径后端服务是一个现代化的异步Web服务，主要用于：
- 处理飞书捷径中的Coze工作流调用
- 提供高并发的异步任务处理能力
- 支持情感分析、文本摘要、翻译和实体提取等任务
- 提供任务状态跟踪和系统监控功能

## 技术栈

- **Web框架**: FastAPI 0.104.1
- **异步任务队列**: Celery 5.3.4
- **数据库**: PostgreSQL 16.3
- **缓存/消息代理**: Redis 7
- **异步数据库驱动**: asyncpg 0.29.0
- **HTTP客户端**: httpx 0.25.2
- **容器化**: Docker & Docker Compose
- **任务监控**: Flower 2.0.1
- **错误通知**: Webhook集成（支持飞书、钉钉等）

## 项目结构

```
feishu-shortcut-backend/
├── main.py                 # 主应用文件，包含FastAPI应用和API端点
├── celery_app.py          # Celery应用配置
├── init_db.py             # 数据库初始化脚本
├── deploy.sh              # 部署脚本
├── Dockerfile             # Docker镜像构建文件
├── docker-compose.yml     # Docker Compose配置
├── requirements.txt       # Python依赖列表
├── .env                   # 环境变量配置
└── data/                  # 数据目录（当前为空）
```

## 核心功能

### 1. 任务处理

系统支持以下四种任务类型：
- **情感分析**: 分析文本的情感倾向
- **文本摘要**: 生成文本的摘要内容
- **翻译**: 文本翻译功能
- **实体提取**: 从文本中提取关键实体

### 2. API端点

- `POST /api/chat`: 异步执行任务，等待Coze返回结果
- `GET /api/task/{task_id}`: 查询任务状态
- `GET /api/tasks/all`: 获取所有可用任务列表
- `GET /api/system/status`: 获取系统状态信息
- `GET /health`: 健康检查端点
- `GET /docs`: 自动生成的API文档

### 3. 异步任务处理

- 使用Celery实现异步任务队列
- 支持任务进度跟踪
- 任务结果缓存（Redis，1小时过期）
- 任务失败重试机制

### 4. 错误监控与通知

- **Webhook错误通知**: 自动发送系统级错误通知
- **错误类型覆盖**: 数据库连接错误、Redis连接错误、Coze API错误、任务执行错误
- **详细错误信息**: 包含错误类型、时间、堆栈跟踪、任务信息和系统状态
- **Markdown格式**: 支持飞书、钉钉等平台的Markdown消息格式
- **异步通知**: 不影响主业务流程的异步错误通知机制

## 安装与部署

### 环境要求

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+（本地开发）

### 快速部署

1. 克隆项目到本地
```bash
git clone <repository-url>
cd feishu-shortcut-backend
```

2. 配置环境变量
```bash
# .env文件已预配置，可根据需要修改
cp .env.example .env
```

3. 使用部署脚本一键部署
```bash
chmod +x deploy.sh
./deploy.sh
```

4. 验证部署
- 服务地址: http://localhost:6921
- API文档: http://localhost:6921/docs
- Celery监控面板: http://localhost:5555

### 手动部署

1. 构建并启动服务
```bash
docker-compose up -d --build
```

2. 初始化数据库
```bash
docker-compose exec backend python init_db.py init
```

3. 检查服务状态
```bash
docker-compose ps
```

## 开发指南

### 本地开发环境设置

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 启动PostgreSQL和Redis
```bash
docker-compose up -d postgres redis
```

3. 初始化数据库
```bash
python init_db.py init
```

4. 启动FastAPI应用
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 6921
```

5. 启动Celery Worker（新终端）
```bash
celery -A celery_app worker --loglevel=info
```

6. 启动Celery Beat（新终端，可选）
```bash
celery -A celery_app beat --loglevel=info
```

7. 启动Flower监控（新终端，可选）
```bash
celery -A celery_app flower --port=5555
```

### API使用示例

#### 执行任务

```bash
curl -X POST "http://localhost:6921/api/chat" \
-H "Content-Type: application/json" \
-d '{
  "api_key_binding": "your_api_key",
  "task_selection": "情感分析",
  "information_input": "今天天气真好，心情很愉快！"
}'
```

#### 查询任务状态

```bash
curl -X GET "http://localhost:6921/api/task/{task_id}"
```

#### 获取任务列表

```bash
curl -X GET "http://localhost:6921/api/tasks/all"
```

#### 获取系统状态

```bash
curl -X GET "http://localhost:6921/api/system/status"
```

## 配置说明

### 环境变量

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| PORT | 服务端口 | 6921 |
| DB_HOST | 数据库主机 | postgres |
| DB_PORT | 数据库端口 | 5432 |
| DB_NAME | 数据库名称 | postgre |
| DB_USER | 数据库用户名 | postgres |
| DB_PASSWORD | 数据库密码 | your_db_password |
| REDIS_URL | Redis连接URL | redis://redis:6380/0 |
| LOG_LEVEL | 日志级别 | INFO |
| CACHE_TTL | 缓存过期时间(秒) | 3600 |
| webhook_url | Webhook错误通知URL | 无 |

### 数据库配置

系统使用PostgreSQL作为主数据库，包含一个主要表：

- `task_coze`: 存储任务配置和Coze工作流信息
  - `task_selection`: 任务类型（情感分析、文本摘要等）
  - `coze_workflow_id`: Coze工作流ID
  - `coze_token`: Coze API访问令牌

### Celery配置

- 任务序列化: JSON
- 时区: Asia/Shanghai
- 任务超时: 30分钟（硬限制），15分钟（软限制）
- 结果过期时间: 1小时
- 工作进程最大任务数: 100

## 监控与日志

### 日志

- 应用日志: 使用Python标准logging模块
- 日志级别: INFO（可通过环境变量调整）
- 日志格式: 包含时间戳、级别和消息

### 监控

- **Flower**: Celery任务监控面板
  - 地址: http://localhost:5555
  - 功能: 查看任务状态、工作进程信息、任务执行历史

- **系统状态API**: `/api/system/status`
  - 活跃任务数量
  - Celery工作状态
  - Redis连接状态

### Webhook错误通知

系统集成了Webhook错误通知机制，支持以下错误场景的自动通知：

#### 支持的错误类型
- **数据库连接错误**: 数据库连接池创建失败时触发
- **Redis连接错误**: Redis客户端初始化失败时触发
- **Coze API错误**: Coze工作流调用失败时触发
- **任务执行错误**: Celery任务执行过程中发生错误时触发
- **异步任务错误**: 异步任务端点执行失败时触发

#### 通知内容格式
错误通知采用Markdown格式，包含以下信息：
- 错误类型和时间戳
- 详细的错误信息和堆栈跟踪
- 相关任务信息（任务ID、任务类型、API Key等）
- 当前系统状态（活跃任务数、Redis连接状态、Celery工作进程等）

#### 配置方式
在`.env`文件中设置`webhook_url`环境变量，指向您的Webhook接收地址：
```bash
webhook_url=https://your-webhook-url.com/endpoint
```

#### 自动触发场景
- 服务启动时的数据库/Redis连接检查
- 任务执行过程中的异常捕获
- 系统关键组件的健康状态监控

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查PostgreSQL服务是否正常运行
   - 验证数据库连接参数是否正确
   - 确保数据库已初始化
   - 系统会自动发送Webhook错误通知（如已配置）

2. **Redis连接失败**
   - 检查Redis服务是否正常运行
   - 验证Redis连接URL是否正确
   - 系统会自动发送Webhook错误通知（如已配置）
   - 服务会继续运行但跳过Redis相关功能

3. **任务执行失败**
   - 检查Coze API令牌是否有效
   - 验证Coze工作流ID是否正确
   - 查看Celery Worker日志获取详细错误信息
   - 系统会自动发送Webhook错误通知（如已配置）

4. **服务启动失败**
   - 检查端口是否被占用
   - 验证Docker服务是否正常运行
   - 查看容器日志获取详细错误信息

5. **Webhook错误通知失败**
   - 检查`webhook_url`环境变量是否正确配置
   - 验证Webhook接收端是否可访问
   - 查看应用日志中的Webhook发送状态
   - 确保网络连接正常，防火墙未阻止出站请求

### 日志查看

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f celery-worker
docker-compose logs -f postgres
docker-compose logs -f redis
```

## 性能优化

### 数据库优化

- 使用连接池（最小5个连接，最大20个连接）
- 异步数据库操作
- 适当的索引优化

### 缓存策略

- Redis缓存任务状态（1小时过期）
- 任务结果缓存
- 适当的缓存失效策略

### 并发处理

- FastAPI多进程（4个工作进程）
- Celery多工作进程（2个并发）
- 异步HTTP客户端（httpx）

## 安全考虑

- API密钥安全存储和传输
- 数据库访问控制
- 容器网络隔离
- 环境变量敏感信息保护

## 扩展指南

### 添加新任务类型

1. 在数据库中添加新任务配置
```sql
INSERT INTO task_coze (task_selection, coze_workflow_id, coze_token) 
VALUES ('新任务类型', '工作流ID', 'Coze令牌');
```

2. 更新API文档和示例

### 扩展API功能

1. 在`main.py`中添加新的端点
2. 更新请求/响应模型
3. 添加适当的错误处理

### 部署扩展

1. 修改`docker-compose.yml`添加新服务
2. 更新`Dockerfile`如需新依赖
3. 调整部署脚本

## 许可证

[请在此处添加许可证信息]

## 联系方式

[请在此处添加联系方式]