# 使用Python官方镜像作为基础镜像
# 使用Python官方镜像作为基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app/backend

# 设置时区
ARG TZ=Asia/Shanghai
ENV TZ=${TZ}

# 安装系统依赖
RUN apt-get update && apt-get install -y gcc libpq-dev curl && apt-get clean

# 复制requirements.txt文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PATH=/app/backend:$PATH

# 设置日志目录
RUN mkdir -p /app/backend/logs && chmod 777 /app/backend/logs

# 暴露端口
EXPOSE 8000

# 创建健康检查脚本
RUN echo '#!/bin/sh' > /app/backend/healthcheck.sh && \
    echo 'curl -sf http://localhost:8000/api/health || exit 1' >> /app/backend/healthcheck.sh && \
    chmod +x /app/backend/healthcheck.sh

# 设置健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 CMD ["/app/backend/healthcheck.sh"]

# 启动命令 - 支持动态工作线程数
CMD ["bash", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WORKERS_COUNT:-1}"]