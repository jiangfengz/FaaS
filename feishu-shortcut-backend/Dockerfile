# 使用Python 3.11作为基础镜像
FROM python:3.11-slim

# 使用国内镜像源安装系统依赖
RUN rm -f /etc/apt/sources.list.d/* && \
    echo 'deb http://mirrors.aliyun.com/debian/ bullseye main non-free contrib' > /etc/apt/sources.list && \
    echo 'deb http://mirrors.aliyun.com/debian-security bullseye-security main' >> /etc/apt/sources.list && \
    echo 'deb http://mirrors.aliyun.com/debian/ bullseye-updates main non-free contrib' >> /etc/apt/sources.list && \
    apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 复制依赖文件
COPY requirements.txt .

# 使用国内镜像源安装Python依赖
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 6921 5555

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:6921/health || exit 1

# 默认启动异步版本
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "6921", "--workers", "4"]