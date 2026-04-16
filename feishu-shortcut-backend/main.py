from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
import logging
from datetime import datetime, timedelta
import asyncio
import asyncpg
import json
import httpx
from dotenv import load_dotenv
import uuid
import redis
from celery import Celery
import time
import traceback

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Celery配置
celery_app = Celery(
    "feishu_coze_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Celery任务配置
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_routes={
        'main.process_coze_workflow': {'queue': 'coze_workflow'}
    }
)

# 创建FastAPI应用
app = FastAPI(
    title="飞书捷径后端服务 - 异步版",
    description="异步处理Coze工作流调用，支持高并发和长时间任务",
    version="3.0.0"
)

# CORS中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://*.feishu.cn", "https://*.larksuite.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# 数据库连接配置
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Coze API配置
COZE_API_URL = "https://api.coze.cn/v1/workflow/run"

# Redis客户端
try:
    redis_client = redis.from_url(REDIS_URL)
    # 测试Redis连接
    redis_client.ping()
    logger.info("Redis连接成功")
except Exception as e:
    error_details = f"Redis连接失败: {str(e)}\n堆栈信息: {traceback.format_exc()}"
    logger.error(error_details)
    
    # 发送Webhook错误通知
    import asyncio
    asyncio.create_task(send_webhook_error_notification(
        "Redis连接错误",
        error_details,
        {"Redis URL": REDIS_URL}
    ))
    
    # 创建空的Redis客户端，但标记为不可用
    redis_client = None

# Webhook配置
WEBHOOK_URL = os.getenv("webhook_url")

# 错误去重缓存 - 存储已发送的错误类型和时间戳
error_cache = {}
CACHE_EXPIRY = 3600  # 1小时，同一种错误1小时内只发送一次

async def should_send_notification(error_type: str, error_details: str) -> bool:
    """判断是否应该发送错误通知（去重逻辑）"""
    current_time = time.time()
    
    # 生成错误指纹（基于错误类型和关键错误信息）
    error_fingerprint = f"{error_type}:{error_details[:100]}"  # 取前100个字符作为指纹
    
    # 检查缓存中是否存在未过期的相同错误
    if error_fingerprint in error_cache:
        last_sent_time = error_cache[error_fingerprint]
        if current_time - last_sent_time < CACHE_EXPIRY:
            logger.info(f"错误通知已发送过，跳过重复发送: {error_type}")
            return False
    
    # 更新缓存
    error_cache[error_fingerprint] = current_time
    
    # 清理过期缓存（避免内存泄漏）
    expired_keys = [key for key, timestamp in error_cache.items() 
                   if current_time - timestamp > CACHE_EXPIRY]
    for key in expired_keys:
        del error_cache[key]
    
    return True

# 异步发送Webhook错误通知
async def send_webhook_error_notification(error_type: str, error_details: str, task_info: dict = None):
    """发送Webhook错误通知（带去重功能）"""
    if not WEBHOOK_URL:
        logger.warning("Webhook URL未配置，跳过错误通知")
        return False
    
    # 检查是否应该发送通知
    if not await should_send_notification(error_type, error_details):
        return False
    
    try:
        # 构造详细的错误信息
        error_message = f"🚨 **后端服务错误通知**\n\n"
        error_message += f"**错误类型**: {error_type}\n"
        error_message += f"**发生时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        error_message += f"**错误详情**: {error_details}\n"
        
        if task_info:
            error_message += f"**任务信息**:\n"
            for key, value in task_info.items():
                error_message += f"  - {key}: {value}\n"
        
        # 添加系统状态信息
        try:
            system_status = await get_system_status()
            error_message += f"\n**系统状态**:\n"
            error_message += f"  - 活跃任务数: {system_status.get('active_tasks', '未知')}\n"
            error_message += f"  - Redis连接: {'正常' if system_status.get('redis_connected') else '异常'}\n"
            if 'celery_stats' in system_status:
                celery_stats = system_status['celery_stats']
                error_message += f"  - Celery工作进程: {celery_stats.get('active_workers', 0)}\n"
                error_message += f"  - Celery活跃任务: {celery_stats.get('active_tasks', 0)}\n"
        except Exception as e:
            error_message += f"\n**系统状态获取失败**: {str(e)}\n"
        
        # 构造Webhook请求体
        webhook_data = {
            "msgtype": "markdown",
            "markdown": {
                "content": error_message
            }
        }
        
        # 发送Webhook请求
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                WEBHOOK_URL,
                json=webhook_data,
                headers={"Content-Type": "application/json"}
            )
        
        if response.status_code == 200:
            logger.info(f"Webhook错误通知发送成功: {error_type}")
            return True
        else:
            logger.error(f"Webhook错误通知发送失败: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"发送Webhook错误通知时发生异常: {str(e)}")
        return False

# 同步版本的去重判断函数
def should_send_notification_sync(error_type: str, error_details: str) -> bool:
    """同步版本：判断是否应该发送错误通知（去重逻辑）"""
    current_time = time.time()
    
    # 生成错误指纹（基于错误类型和关键错误信息）
    error_fingerprint = f"{error_type}:{error_details[:100]}"  # 取前100个字符作为指纹
    
    # 检查缓存中是否存在未过期的相同错误
    if error_fingerprint in error_cache:
        last_sent_time = error_cache[error_fingerprint]
        if current_time - last_sent_time < CACHE_EXPIRY:
            logger.info(f"错误通知已发送过，跳过重复发送: {error_type}")
            return False
    
    # 更新缓存
    error_cache[error_fingerprint] = current_time
    
    # 清理过期缓存（避免内存泄漏）
    expired_keys = [key for key, timestamp in error_cache.items() 
                   if current_time - timestamp > CACHE_EXPIRY]
    for key in expired_keys:
        del error_cache[key]
    
    return True

# 同步版本（用于Celery任务中）
def send_webhook_error_notification_sync(error_type: str, error_details: str, task_info: dict = None):
    """同步发送Webhook错误通知（带去重功能）"""
    if not WEBHOOK_URL:
        logger.warning("Webhook URL未配置，跳过错误通知")
        return False
    
    # 检查是否应该发送通知
    if not should_send_notification_sync(error_type, error_details):
        return False
    
    try:
        # 构造详细的错误信息
        error_message = f"🚨 **后端服务错误通知**\n\n"
        error_message += f"**错误类型**: {error_type}\n"
        error_message += f"**发生时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        error_message += f"**错误详情**: {error_details}\n"
        
        if task_info:
            error_message += f"**任务信息**:\n"
            for key, value in task_info.items():
                error_message += f"  - {key}: {value}\n"
        
        # 构造Webhook请求体
        webhook_data = {
            "msgtype": "markdown",
            "markdown": {
                "content": error_message
            }
        }
        
        # 发送Webhook请求
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                WEBHOOK_URL,
                json=webhook_data,
                headers={"Content-Type": "application/json"}
            )
        
        if response.status_code == 200:
            logger.info(f"Webhook错误通知发送成功: {error_type}")
            return True
        else:
            logger.error(f"Webhook错误通知发送失败: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"发送Webhook错误通知时发生异常: {str(e)}")
        return False

# 请求模型
class TaskRequest(BaseModel):
    api_key_binding: str  # API Key绑定（直接传递给Coze）
    task_selection: str   # 任务选择
    information_input: str  # 信息输入

# 响应模型
class TaskResponse(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# 任务状态模型
class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: Optional[int] = None
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# 异步数据库连接池
_db_pool = None

async def get_db_pool():
    """获取数据库连接池"""
    global _db_pool
    if _db_pool is None:
        try:
            _db_pool = await asyncpg.create_pool(
                host=DB_HOST,
                port=int(DB_PORT),
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                min_size=5,
                max_size=20
            )
        except Exception as e:
            error_details = f"数据库连接池创建失败: {str(e)}\n堆栈信息: {traceback.format_exc()}"
            logger.error(error_details)
            
            # 发送Webhook错误通知
            asyncio.create_task(send_webhook_error_notification(
                "数据库连接错误",
                error_details,
                {
                    "数据库主机": DB_HOST,
                    "数据库端口": DB_PORT,
                    "数据库名称": DB_NAME,
                    "用户名": DB_USER
                }
            ))
            
            raise
    return _db_pool

async def init_database():
    """异步初始化数据库表结构"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # 检查task_coze表是否存在
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'task_coze'
                )
            """)
            
            if not exists:
                logger.info("创建task_coze表...")
                
                # 创建task_coze表
                await conn.execute("""
                CREATE TABLE task_coze (
                    id SERIAL PRIMARY KEY,
                    task_selection VARCHAR(100) UNIQUE NOT NULL,
                    coze_workflow_id VARCHAR(100) NOT NULL,
                    coze_token VARCHAR(500) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                # 插入默认任务配置
                tasks = [
                    ('情感分析', '7559512802530082868', 'pat_zKTocOtiWn1QRQDvs3hSWL1PGAYlTPcHoV2NoiVfdxCqkdAyM6SWPSIGO5f2qwBX'),
                    ('文本摘要', '7559512802530082868', 'pat_zKTocOtiWn1QRQDvs3hSWL1PGAYlTPcHoV2NoiVfdxCqkdAyM6SWPSIGO5f2qwBX'),
                    ('翻译', '7559512999729348635', 'pat_zKTocOtiWn1QRQDvs3hSWL1PGAYlTPcHoV2NoiVfdxCqkdAyM6SWPSIGO5f2qwBX'),
                    ('实体提取', '7559512999729348635', 'pat_zKTocOtiWn1QRQDvs3hSWL1PGAYlTPcHoV2NoiVfdxCqkdAyM6SWPSIGO5f2qwBX')
                ]
                
                await conn.executemany(
                    "INSERT INTO task_coze (task_selection, coze_workflow_id, coze_token) VALUES ($1, $2, $3)",
                    tasks
                )
                logger.info("task_coze表创建完成")
            else:
                logger.info("task_coze表已存在，跳过初始化")
        
        logger.info("数据库初始化完成")
        return True
        
    except Exception as e:
        error_details = f"数据库初始化失败: {str(e)}\n堆栈信息: {traceback.format_exc()}"
        logger.error(error_details)
        
        # 发送Webhook错误通知
        asyncio.create_task(send_webhook_error_notification(
            "数据库初始化错误",
            error_details,
            {"错误位置": "数据库表结构初始化"}
        ))
        
        return False

# 应用启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时自动初始化数据库"""
    logger.info("异步应用启动中...")
    
    # 初始化数据库连接池
    try:
        await get_db_pool()
        logger.info("数据库连接池初始化成功")
    except Exception as e:
        logger.error(f"数据库连接池初始化失败: {str(e)}")
        return
    
    # 初始化数据库表结构
    max_retries = 10
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            if await init_database():
                logger.info("数据库初始化成功")
                break
            else:
                logger.warning(f"数据库初始化失败，重试中... ({retry_count + 1}/{max_retries})")
        except Exception as e:
            logger.warning(f"数据库连接失败，重试中... ({retry_count + 1}/{max_retries}): {str(e)}")
        
        retry_count += 1
        await asyncio.sleep(5)
    
    if retry_count == max_retries:
        logger.error("数据库初始化失败，应用将继续启动但数据库功能可能不可用")
    else:
        logger.info("异步应用启动完成")

# 应用关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        logger.info("数据库连接池已关闭")

# 异步获取Coze配置
async def get_coze_config(task_selection: str):
    """异步从数据库获取COZE_TOKEN和Coze工作流ID"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT coze_workflow_id, coze_token FROM task_coze WHERE task_selection = $1", 
                task_selection
            )
            
            if result:
                workflow_id, coze_token = result['coze_workflow_id'], result['coze_token']
                logger.info(f"获取任务配置成功: {task_selection}")
                return workflow_id, coze_token
            
            logger.warning(f"任务配置不存在: {task_selection}")
            return None, None
            
    except Exception as e:
        logger.error(f"获取Coze配置失败: {str(e)}")
        return None, None

# 异步调用Coze工作流
async def call_coze_workflow_async(api_key_binding: str, task_selection: str, information_input: str):
    """异步调用Coze工作流"""
    try:
        # 从数据库获取COZE_TOKEN和工作流ID
        workflow_id, coze_token = await get_coze_config(task_selection)
        
        if workflow_id is None or coze_token is None:
            raise Exception("任务找不到")
        
        if not coze_token:
            raise Exception("Coze令牌未配置")
        if not workflow_id:
            raise Exception(f"任务 '{task_selection}' 未找到对应的Coze工作流")
        
        # 构造请求参数
        request_body = {
            "workflow_id": workflow_id,
            "parameters": {
                "api": api_key_binding,
                "mission": task_selection,
                "text": information_input
            }
        }
        
        logger.info(f"发送异步Coze API请求: 工作流ID={workflow_id}")
        
        # 使用httpx进行异步HTTP请求
        async with httpx.AsyncClient(timeout=httpx.Timeout(900.0)) as client:  # 15分钟超时
            response = await client.post(
                COZE_API_URL,
                json=request_body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {coze_token}"
                }
            )
        
        logger.info(f"Coze API响应状态码: {response.status_code}")
        
        # 检查响应内容类型
        content_type = response.headers.get('Content-Type', '')
        
        if 'application/json' not in content_type:
            logger.warning(f"Coze API返回非JSON响应，内容类型: {content_type}")
            raise Exception(f"Coze API返回非JSON响应: {response.status_code} - {response.text[:200]}")
        
        try:
            response_data = response.json()
            logger.info(f"Coze API响应JSON解析成功")
        except ValueError as e:
            logger.error(f"Coze API返回无效JSON: {e}")
            raise Exception(f"Coze API返回无效JSON: {response.text[:200]}")
        
        if response.status_code != 200:
            raise Exception(f"Coze API调用失败: {response.status_code} - {response_data}")
        
        # 检查Coze API特定的错误码
        if isinstance(response_data, dict):
            if response_data.get("code") != 0:
                raise Exception(f"Coze工作流执行失败: {response_data.get('msg', '未知错误')}")
            
            # 提取返回结果
            data_field = response_data.get("data", "")
            
            # 如果data字段是字符串，尝试解析为JSON
            if isinstance(data_field, str):
                try:
                    data_field = json.loads(data_field)
                except json.JSONDecodeError:
                    output = data_field
                else:
                    output = data_field.get("output") or data_field.get("result") or "任务执行完成"
            elif isinstance(data_field, dict):
                output = data_field.get("output") or data_field.get("result") or "任务执行完成"
            else:
                output = str(data_field)
        else:
            output = str(response_data)
        
        return output
        
    except Exception as e:
        error_details = f"异步调用Coze工作流失败: {str(e)}\n堆栈信息: {traceback.format_exc()}"
        logger.error(error_details)
        
        # 发送Webhook错误通知
        asyncio.create_task(send_webhook_error_notification(
            "Coze API调用错误",
            error_details,
            {
                "任务类型": task_selection,
                "API Key": api_key_binding[:10] + "..." if api_key_binding else "未提供",
                "输入信息长度": len(information_input)
            }
        ))
        
        raise

# Celery任务 - 处理Coze工作流
@celery_app.task(bind=True, name="main.process_coze_workflow")
def process_coze_workflow(self, task_id: str, api_key_binding: str, task_selection: str, information_input: str):
    """Celery任务：处理Coze工作流（使用异步HTTP客户端）"""
    try:
        # 更新任务状态为处理中
        task_status = {
            "task_id": task_id,
            "status": "processing",
            "progress": 0,
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        if redis_client:
            redis_client.setex(f"task:{task_id}", 3600, json.dumps(task_status))
        else:
            logger.warning("Redis不可用，跳过任务状态更新")
        
        # 模拟进度更新（实际应用中可以根据需要实现）
        for i in range(1, 6):
            import asyncio
            asyncio.sleep(1)  # 异步模拟处理时间
            task_status["progress"] = i * 20
            task_status["updated_at"] = datetime.now().isoformat()
            if redis_client:
                redis_client.setex(f"task:{task_id}", 3600, json.dumps(task_status))
            else:
                logger.warning("Redis不可用，跳过任务状态更新")
            
            # 更新Celery任务状态
            self.update_state(
                state='PROGRESS',
                meta={'current': i * 20, 'total': 100}
            )
        
        # 使用httpx进行同步HTTP请求（Celery任务内使用同步版本）
        import httpx
        
        # 获取Coze配置（同步版本，使用httpx）
        def get_coze_config_sync(task_selection: str):
            import asyncpg
            import asyncio
            
            # 在同步函数中运行异步代码
            async def async_get_config():
                try:
                    pool = await asyncpg.create_pool(
                        host=DB_HOST,
                        port=DB_PORT,
                        database=DB_NAME,
                        user=DB_USER,
                        password=DB_PASSWORD
                    )
                    async with pool.acquire() as conn:
                        result = await conn.fetchrow(
                            "SELECT coze_workflow_id, coze_token FROM task_coze WHERE task_selection = $1", 
                            task_selection
                        )
                        if result:
                            return result['coze_workflow_id'], result['coze_token']
                        return None, None
                except Exception as e:
                    logger.error(f"获取Coze配置失败: {str(e)}")
                    return None, None
            
            return asyncio.run(async_get_config())
        
        workflow_id, coze_token = get_coze_config_sync(task_selection)
        
        if workflow_id is None or coze_token is None:
            raise Exception("任务找不到")
        
        # 同步调用Coze API（使用httpx同步客户端）
        request_body = {
            "workflow_id": workflow_id,
            "parameters": {
                "api": api_key_binding,
                "mission": task_selection,
                "text": information_input
            }
        }
        
        with httpx.Client(timeout=900.0) as client:  # 15分钟超时
            response = client.post(
                COZE_API_URL,
                json=request_body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {coze_token}"
                }
            )
        
        if response.status_code != 200:
            raise Exception(f"Coze API调用失败: {response.status_code}")
        
        response_data = response.json()
        
        if response_data.get("code") != 0:
            raise Exception(f"Coze工作流执行失败: {response_data.get('msg', '未知错误')}")
        
        # 提取结果
        data_field = response_data.get("data", "")
        if isinstance(data_field, str):
            try:
                data_field = json.loads(data_field)
                output = data_field.get("output") or data_field.get("result") or "任务执行完成"
            except json.JSONDecodeError:
                output = data_field
        elif isinstance(data_field, dict):
            output = data_field.get("output") or data_field.get("result") or "任务执行完成"
        else:
            output = str(data_field)
        
        # 更新任务状态为完成
        task_status["status"] = "completed"
        task_status["progress"] = 100
        task_status["result"] = output
        task_status["updated_at"] = datetime.now().isoformat()
        if redis_client:
            redis_client.setex(f"task:{task_id}", 3600, json.dumps(task_status))
        else:
            logger.warning("Redis不可用，跳过任务状态更新")
        
        return {"result": output}
        
    except Exception as e:
        error_details = f"Celery任务执行失败: {str(e)}\n堆栈信息: {traceback.format_exc()}"
        
        # 更新任务状态为失败
        task_status = {
            "task_id": task_id,
            "status": "failed",
            "progress": 100,
            "result": None,
            "error": str(e),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        redis_client.setex(f"task:{task_id}", 3600, json.dumps(task_status))
        
        # 发送Webhook错误通知
        send_webhook_error_notification_sync(
            "Celery任务执行错误",
            error_details,
            {
                "任务ID": task_id,
                "任务类型": task_selection,
                "API Key": api_key_binding[:10] + "..." if api_key_binding else "未提供",
                "输入信息长度": len(information_input)
            }
        )
        
        raise

# 健康检查端点
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "service": "feishu-shortcut-backend-async",
        "mode": "async"
    }

# 异步任务执行端点（等待Coze返回结果）
@app.post("/api/chat", response_model=TaskResponse)
async def execute_task_async(request: TaskRequest):
    """异步执行任务 - 等待Coze返回结果后返回"""
    try:
        # 生成唯一任务ID
        task_id = str(uuid.uuid4())
        
        # 创建初始任务状态
        task_status = {
            "task_id": task_id,
            "status": "processing",
            "progress": 0,
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # 将任务状态存储到Redis（1小时过期）
        if redis_client:
            redis_client.setex(f"task:{task_id}", 3600, json.dumps(task_status))
        else:
            logger.warning("Redis不可用，跳过任务状态存储")
        
        # 直接异步调用Coze工作流，等待结果
        result = await call_coze_workflow_async(
            api_key_binding=request.api_key_binding,
            task_selection=request.task_selection,
            information_input=request.information_input
        )
        
        # 更新任务状态
        task_status["status"] = "completed"
        task_status["progress"] = 100
        task_status["result"] = result
        task_status["updated_at"] = datetime.now().isoformat()
        if redis_client:
            redis_client.setex(f"task:{task_id}", 3600, json.dumps(task_status))
        else:
            logger.warning("Redis不可用，跳过任务状态更新")
        
        logger.info(f"任务执行完成: {task_id}")
        
        return TaskResponse(
            task_id=task_id,
            status="completed",
            result=result,
            created_at=datetime.fromisoformat(task_status["created_at"]),
            updated_at=datetime.fromisoformat(task_status["updated_at"])
        )
        
    except Exception as e:
        error_details = f"异步任务执行失败: {str(e)}\n堆栈信息: {traceback.format_exc()}"
        logger.error(error_details)
        
        # 更新任务状态为失败
        task_status = {
            "task_id": task_id,
            "status": "failed",
            "progress": 100,
            "result": None,
            "error": str(e),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        redis_client.setex(f"task:{task_id}", 3600, json.dumps(task_status))
        
        # 发送Webhook错误通知
        asyncio.create_task(send_webhook_error_notification(
            "异步任务执行错误",
            error_details,
            {
                "任务ID": task_id,
                "任务类型": request.task_selection,
                "API Key": request.api_key_binding[:10] + "..." if request.api_key_binding else "未提供",
                "输入信息长度": len(request.information_input)
            }
        ))
        
        return TaskResponse(
            task_id=task_id,
            status="failed",
            error=str(e),
            created_at=datetime.fromisoformat(task_status["created_at"]),
            updated_at=datetime.fromisoformat(task_status["updated_at"])
        )

# 查询任务状态端点
@app.get("/api/task/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """查询任务状态"""
    try:
        if not redis_client:
            # 发送Webhook通知
            asyncio.create_task(send_webhook_error_notification(
                "Redis服务不可用",
                "查询任务状态时发现Redis服务不可用",
                {"任务ID": task_id, "Redis URL": REDIS_URL}
            ))
            raise HTTPException(status_code=503, detail="Redis服务不可用")
        
        task_data = redis_client.get(f"task:{task_id}")
        if not task_data:
            raise HTTPException(status_code=404, detail="任务不存在或已过期")
        
        task_status = json.loads(task_data)
        
        return TaskStatus(
            task_id=task_status["task_id"],
            status=task_status["status"],
            progress=task_status.get("progress"),
            result=task_status.get("result"),
            error=task_status.get("error"),
            created_at=datetime.fromisoformat(task_status["created_at"]),
            updated_at=datetime.fromisoformat(task_status["updated_at"])
        )
        
    except Exception as e:
        error_details = f"查询任务状态失败: {str(e)}\n堆栈信息: {traceback.format_exc()}"
        logger.error(error_details)
        
        # 发送Webhook错误通知
        asyncio.create_task(send_webhook_error_notification(
            "查询任务状态错误",
            error_details,
            {"任务ID": task_id}
        ))
        
        raise HTTPException(status_code=500, detail=f"查询任务状态失败: {str(e)}")

# 获取任务列表端点
@app.get("/api/tasks/all")
async def get_tasks_all():
    """获取所有任务列表"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            tasks = await conn.fetch("SELECT task_selection, coze_workflow_id, coze_token FROM task_coze ORDER BY id")
            
            task_list = []
            for task in tasks:
                task_list.append({
                    "task_selection": task["task_selection"],
                    "coze_workflow_id": task["coze_workflow_id"],
                    "coze_token": task["coze_token"]
                })
            
            return {"tasks": task_list}
            
    except Exception as e:
        error_details = f"获取任务列表失败: {str(e)}\n堆栈信息: {traceback.format_exc()}"
        logger.error(error_details)
        
        # 发送Webhook错误通知
        asyncio.create_task(send_webhook_error_notification(
            "数据库连接错误",
            error_details,
            {"错误位置": "获取任务列表"}
        ))
        
        return {"tasks": []}

# 系统状态端点
@app.get("/api/system/status")
async def get_system_status():
    """获取系统状态信息"""
    try:
        # 获取活跃任务数量
        active_tasks = 0
        if redis_client:
            for key in redis_client.scan_iter("task:*"):
                task_data = redis_client.get(key)
                if task_data:
                    task_status = json.loads(task_data)
                    if task_status["status"] in ["pending", "processing"]:
                        active_tasks += 1
        else:
            logger.warning("Redis不可用，跳过活跃任务统计")
            # 发送Webhook通知
            asyncio.create_task(send_webhook_error_notification(
                "Redis连接错误",
                "系统状态检查时发现Redis连接不可用",
                {"Redis URL": REDIS_URL}
            ))
        
        # 获取Celery工作状态
        celery_stats = {}
        try:
            inspector = celery_app.control.inspect()
            active_tasks_info = inspector.active()
            if active_tasks_info:
                celery_stats["active_workers"] = len(active_tasks_info)
                celery_stats["active_tasks"] = sum(len(tasks) for tasks in active_tasks_info.values())
            else:
                celery_stats["active_workers"] = 0
                celery_stats["active_tasks"] = 0
        except Exception as e:
            celery_stats["error"] = str(e)
            # 发送Webhook通知
            asyncio.create_task(send_webhook_error_notification(
                "Celery状态检查错误",
                f"检查Celery工作状态失败: {str(e)}",
                {}
            ))
        
        # 检查Redis连接状态
        redis_connected = False
        if redis_client:
            try:
                redis_connected = redis_client.ping()
            except Exception as e:
                logger.error(f"Redis连接检查失败: {str(e)}")
                # 发送Webhook通知
                asyncio.create_task(send_webhook_error_notification(
                    "Redis连接检查错误",
                    f"Redis连接检查失败: {str(e)}",
                    {"Redis URL": REDIS_URL}
                ))
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "active_tasks": active_tasks,
            "celery_stats": celery_stats,
            "redis_connected": redis_connected
        }
        
    except Exception as e:
        error_details = f"获取系统状态失败: {str(e)}\n堆栈信息: {traceback.format_exc()}"
        logger.error(error_details)
        
        # 发送Webhook错误通知
        asyncio.create_task(send_webhook_error_notification(
            "系统状态检查错误",
            error_details,
            {}
        ))
        
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6921)