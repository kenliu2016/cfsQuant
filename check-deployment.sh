#!/bin/bash

# 部署检查脚本 - 用于验证cfsQuant应用是否正常部署

# 打印脚本信息
echo "================================="
echo "        cfsQuant部署检查工具        "
echo "================================="

echo "\n1. 检查Docker服务状态..."
if systemctl is-active --quiet docker; then
    echo "✅ Docker服务正在运行"
else
    echo "❌ Docker服务未运行"
    echo "请执行: sudo systemctl start docker"
    exit 1
fi

# 检查项目目录
echo "\n2. 检查项目目录..."
if [ -f "docker-compose.prod.yml" ] && [ -f ".env" ]; then
    echo "✅ 项目文件存在"
else
    echo "❌ 项目文件不完整"
    echo "请确保在正确的项目目录中运行此脚本"
    exit 1
fi

# 检查环境变量配置
echo "\n3. 检查环境变量配置..."
ENV_VALID=true

# 检查数据库配置
if grep -q "PGHOST=172.31.24.87" .env && \
   grep -q "PGUSER=cfs" .env && \
   grep -q "PGDATABASE=quant" .env; then
    echo "✅ 数据库配置正确"
else
    echo "❌ 数据库配置不正确"
    ENV_VALID=false
fi

# 检查Redis配置
if grep -q "REDIS_HOST=172.31.25.234" .env; then
    echo "✅ Redis配置正确"
else
    echo "❌ Redis配置不正确"
    ENV_VALID=false
fi

if [ "$ENV_VALID" = false ]; then
    echo "请检查并更新.env文件中的配置"
    exit 1
fi

# 检查Docker服务状态
echo "\n4. 检查Docker服务状态..."
docker-compose -f docker-compose.prod.yml ps

# 检查服务健康状态
echo "\n5. 检查服务健康状态..."
BACKEND_HEALTH=$(docker inspect --format='{{json .State.Health.Status}}' quant-backend 2>/dev/null)
FRONTEND_HEALTH=$(docker inspect --format='{{json .State.Health.Status}}' quant-frontend 2>/dev/null)
CELERY_WORKER_HEALTH=$(docker inspect --format='{{json .State.Running}}' quant-celery-worker-tuning 2>/dev/null)
CELERY_BEAT_HEALTH=$(docker inspect --format='{{json .State.Running}}' quant-celery-beat 2>/dev/null)

# 验证后端服务
if [ "$BACKEND_HEALTH" = "\"healthy\"" ]; then
    echo "✅ 后端服务健康状态: $BACKEND_HEALTH"
    # 测试后端API
    API_RESPONSE=$(curl -s http://localhost:8000/api/health)
    if [ "$API_RESPONSE" = '{"status":"ok"}' ]; then
        echo "✅ 后端API测试通过: $API_RESPONSE"
    else
        echo "⚠️  后端API响应异常: $API_RESPONSE"
    fi
else
    echo "❌ 后端服务健康状态: $BACKEND_HEALTH"
    echo "查看日志: docker logs quant-backend"
fi

# 验证前端服务
if [ "$FRONTEND_HEALTH" = "\"healthy\"" ]; then
    echo "✅ 前端服务健康状态: $FRONTEND_HEALTH"
    # 测试前端服务
    FRONTEND_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost)
    if [ "$FRONTEND_RESPONSE" = "200" ]; then
        echo "✅ 前端服务测试通过: HTTP $FRONTEND_RESPONSE"
    else
        echo "⚠️  前端服务响应异常: HTTP $FRONTEND_RESPONSE"
    fi
else
    echo "❌ 前端服务健康状态: $FRONTEND_HEALTH"
    echo "查看日志: docker logs quant-frontend"
fi

# 验证Celery服务
if [ "$CELERY_WORKER_HEALTH" = "true" ]; then
    echo "✅ Celery Worker服务运行状态: $CELERY_WORKER_HEALTH"
else
    echo "❌ Celery Worker服务运行状态: $CELERY_WORKER_HEALTH"
    echo "查看日志: docker logs quant-celery-worker-tuning"
fi

if [ "$CELERY_BEAT_HEALTH" = "true" ]; then
    echo "✅ Celery Beat服务运行状态: $CELERY_BEAT_HEALTH"
else
    echo "❌ Celery Beat服务运行状态: $CELERY_BEAT_HEALTH"
    echo "查看日志: docker logs quant-celery-beat"
fi

# 检查网络连接
echo "\n6. 检查网络连接..."

# 检查到数据库的连接
# 从.env文件读取配置
PGHOST=$(grep -oP '(?<=PGHOST=).*' .env)
PGUSER=$(grep -oP '(?<=PGUSER=).*' .env)
PGDATABASE=$(grep -oP '(?<=PGDATABASE=).*' .env)
PGPASSWORD=$(grep -oP '(?<=PGPASSWORD=).*' .env)

# 测试数据库连接
DB_CONNECT_TEST=$(docker exec -t quant-backend bash -c "PGPASSWORD=$PGPASSWORD psql -h $PGHOST -U $PGUSER -d $PGDATABASE -c 'SELECT 1;'") 2>/dev/null
if [[ $DB_CONNECT_TEST == *"1 row"* ]]; then
    echo "✅ 数据库连接测试通过"
else
    echo "⚠️  数据库连接测试失败"
    echo "请检查网络连接和数据库配置"
fi

# 检查到Redis的连接
REDIS_HOST=$(grep -oP '(?<=REDIS_HOST=).*' .env)
REDIS_PORT=$(grep -oP '(?<=REDIS_PORT=).*' .env)
REDIS_PASSWORD=$(grep -oP '(?<=REDIS_PASSWORD=).*' .env)

# 测试Redis连接
REDIS_CONNECT_TEST=$(docker exec -t quant-backend bash -c "redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD ping") 2>/dev/null
if [ "$REDIS_CONNECT_TEST" = "PONG" ]; then
    echo "✅ Redis连接测试通过"
else
    echo "⚠️  Redis连接测试失败"
    echo "请检查网络连接和Redis配置"
fi

echo "\n================================="
echo "        部署检查完成              "
echo "================================="

echo "\n访问应用: http://$(curl -s ifconfig.me)"
echo "后端API: http://$(curl -s ifconfig.me):8000/api/health"