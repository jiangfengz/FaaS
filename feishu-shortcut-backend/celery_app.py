from celery import Celery
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# Redis配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# 创建Celery应用
celery_app = Celery(
    "feishu_coze_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["main"]  # 包含任务模块
)

# Celery配置
celery_app.conf.update(
    # 基本配置
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    
    # 任务路由配置
    task_routes={
        'main.process_coze_workflow': {'queue': 'coze_workflow'}
    },
    
    # 队列配置
    task_default_queue='default',
    task_queues={
        'default': {
            'exchange': 'default',
            'routing_key': 'default'
        },
        'coze_workflow': {
            'exchange': 'coze_workflow',
            'routing_key': 'coze_workflow'
        }
    },
    
    # 任务超时配置
    task_time_limit=1800,  # 30分钟超时
    task_soft_time_limit=900,  # 15分钟软超时
    
    # 重试配置
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    
    # 工作进程配置
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    
    # 结果后端配置
    result_expires=3600,  # 1小时过期
    result_backend_max_retries=3,
    
    # 监控配置
    worker_send_task_events=True,
    task_send_sent_event=True
)

if __name__ == '__main__':
    celery_app.start()