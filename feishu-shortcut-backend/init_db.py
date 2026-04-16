#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步版数据库初始化脚本
用于创建task_coze表
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv
import sys

# 加载环境变量
load_dotenv()

# 数据库连接配置
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

async def get_db_connection():
    """获取异步数据库连接"""
    try:
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except Exception as e:
        print(f"数据库连接失败: {str(e)}")
        return None

async def init_database():
    """异步初始化数据库"""
    conn = await get_db_connection()
    if not conn:
        return False
    
    try:
        print("检查task_coze表...")
        
        # 检查表是否已存在
        table_exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'task_coze'
        )
        """)
        
        if table_exists:
            print("task_coze表已存在，维持原状")
            # 显示当前表中的记录数
            record_count = await conn.fetchval("SELECT COUNT(*) FROM task_coze")
            print(f"当前表中有 {record_count} 条记录")
        else:
            print("创建task_coze表...")
            
            # 创建task_coze表（包含coze_token字段）
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
            print("task_coze表创建完成")
        
        # 不再创建coze_config表，因为coze_token已经集成到task_coze表中
        print("新的设计不再使用coze_config表，coze_token已集成到task_coze表中")
        
        await conn.close()
        
        print("数据库初始化完成!")
        return True
        
    except Exception as e:
        print(f"数据库初始化失败: {str(e)}")
        return False

async def show_data():
    """异步显示数据库中的数据"""
    conn = await get_db_connection()
    if not conn:
        return False
    
    try:
        # 显示任务配置（包含coze_token）
        print("\ntask_coze表数据:")
        rows = await conn.fetch("SELECT * FROM task_coze")
        for row in rows:
            print(f"  {row['task_selection']} -> 工作流ID: {row['coze_workflow_id']}, Token: {row['coze_token'][:20]}...")
        
        # 不再显示coze_config表，因为新的设计不再使用此表
        print("\ncoze_config表: 新的设计不再使用此表")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"显示数据失败: {str(e)}")
        return False

async def main():
    """异步主函数"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python init_db.py init    - 初始化数据库")
        print("  python init_db.py show    - 显示数据")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "init":
        success = await init_database()
    elif command == "show":
        success = await show_data()
    else:
        print(f"未知命令: {command}")
        sys.exit(1)
    
    if success:
        print("操作成功完成")
        sys.exit(0)
    else:
        print("操作失败")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())