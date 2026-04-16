#!/bin/bash

# 飞书捷径FastAPI后端部署脚本

echo "=========================================="
echo "飞书捷径FastAPI后端部署脚本"
echo "=========================================="

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: Docker未安装，请先安装Docker"
    exit 1
fi

# 检查Docker Compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "错误: Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

# 设置环境变量
export DB_HOST=postgres
export DB_PORT=5432
export DB_NAME=postgre
export DB_USER=postgres
export DB_PASSWORD=YOUR_DATABASE_PASSWORD
export REDIS_URL=redis://localhost:6380/0

echo "开始部署飞书捷径FastAPI后端服务..."

# 停止现有服务
echo "停止现有服务..."
docker-compose -f docker-compose.yml down

# 构建并启动服务
echo "构建并启动服务..."
docker-compose -f docker-compose.yml up -d --build

# 等待服务启动
echo "等待服务启动..."
sleep 15

# 检查服务状态
echo "检查服务状态..."
docker-compose -f docker-compose.yml ps

# 检查健康状态
echo "检查健康状态..."
for i in {1..5}; do
    if curl -f http://localhost:6921/health > /dev/null 2>&1; then
        echo "✅ 服务启动成功!"
        echo "📍 服务地址: http://localhost:6921"
        echo "📊 健康检查: http://localhost:6921/health"
        echo "🔧 API文档: http://localhost:6921/docs"
        echo "🔍 Celery监控面板: http://localhost:5555"
        echo ""
        echo "API端点:"
        echo "- 异步任务执行: POST http://localhost:6921/api/chat"
        echo "- 任务状态查询: GET http://localhost:6921/api/task/{task_id}"
        echo "- 任务列表查询: GET http://localhost:6921/api/tasks/all"
        echo "- 系统状态: GET http://localhost:6921/api/system/status"
        
        # 等待数据库完全启动
        echo "等待数据库服务完全启动..."
        for i in {1..10}; do
            if docker-compose -f docker-compose.yml exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
                echo "✅ 数据库服务已就绪"
                break
            else
                echo "等待数据库启动... ($i/10)"
                sleep 5
            fi
            
            if [ $i -eq 10 ]; then
                echo "❌ 数据库启动超时，请检查数据库日志"
                docker-compose -f docker-compose.yml logs postgres
                exit 1
            fi
        done
        
        # 数据库初始化
        echo ""
        echo "开始数据库初始化..."
        if docker-compose -f docker-compose.yml exec -T backend python init_db.py init; then
            echo "✅ 数据库初始化成功!"
        else
            echo "❌ 数据库初始化失败，请检查数据库连接和配置"
            echo "提示: 如果这是首次部署，可能需要等待数据库完全启动后再重试"
        fi
        
        break
    else
        echo "等待服务启动... ($i/5)"
        sleep 5
    fi
    
    if [ $i -eq 5 ]; then
        echo "❌ 服务启动失败，请检查日志:"
        docker-compose -f docker-compose.yml logs
        exit 1
    fi
done

echo "=========================================="
echo "部署完成!"
echo "=========================================="

# 显示日志查看命令
echo "查看日志命令:"
echo "docker-compose -f docker-compose.yml logs -f"

echo ""
echo "停止服务命令:"
echo "docker-compose -f docker-compose.yml down"