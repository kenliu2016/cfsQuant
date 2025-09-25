#!/bin/bash

# 部署测试脚本
# 用于验证Docker环境和docker-compose配置是否正确

set -e

# 检查Docker是否安装
if ! command -v docker &> /dev/null
then
    echo "Docker未安装，请先安装Docker"
    exit 1
fi

echo "✅ Docker已安装"
docker --version

# 检查Docker Compose是否安装
if ! command -v docker-compose &> /dev/null
then
    echo "Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

echo "✅ Docker Compose已安装"
docker-compose --version

# 检查docker-compose.yml文件是否存在
if [ ! -f "docker-compose.yml" ]
then
    echo "docker-compose.yml文件不存在，请确保在项目根目录运行此脚本"
    exit 1
fi

echo "✅ docker-compose.yml文件已找到"

# 验证docker-compose.yml文件格式是否正确
docker-compose config -q
if [ $? -eq 0 ]
then
    echo "✅ docker-compose.yml文件格式正确"
else
    echo "❌ docker-compose.yml文件格式错误，请检查文件内容"
    exit 1
fi

# 检查项目目录结构
required_dirs=("backend" "frontend")
for dir in "${required_dirs[@]}"
do
    if [ ! -d "$dir" ]
    then
        echo "❌ 缺少必要的目录: $dir"
        exit 1
    fi
    echo "✅ 目录 $dir 已找到"
done

# 检查后端Dockerfile是否存在
if [ ! -f "backend/Dockerfile" ]
then
    echo "❌ 后端Dockerfile不存在"
    exit 1
fi
echo "✅ 后端Dockerfile已找到"

# 检查前端Dockerfile是否存在
if [ ! -f "frontend/Dockerfile" ]
then
    echo "❌ 前端Dockerfile不存在"
    exit 1
fi
echo "✅ 前端Dockerfile已找到"

# 检查后端requirements.txt是否存在
if [ ! -f "backend/requirements.txt" ]
then
    echo "❌ 后端requirements.txt不存在"
    exit 1
fi
echo "✅ 后端requirements.txt已找到"

# 检查前端package.json是否存在
if [ ! -f "frontend/package.json" ]
then
    echo "❌ 前端package.json不存在"
    exit 1
fi
echo "✅ 前端package.json已找到"

# 检查后端主文件是否存在
if [ ! -f "backend/app/main.py" ]
then
    echo "❌ 后端主文件app/main.py不存在"
    exit 1
fi
echo "✅ 后端主文件已找到"

# 检查前端API客户端配置
if [ ! -f "frontend/src/api/client.ts" ]
then
    echo "❌ 前端API客户端配置文件不存在"
    exit 1
fi

# 检查客户端配置中是否包含环境变量支持
grep -q "import.meta.env.VITE_API_BASE_URL" frontend/src/api/client.ts
if [ $? -eq 0 ]
then
    echo "✅ 前端API客户端配置支持环境变量设置"
else
    echo "⚠️ 前端API客户端配置可能不支持环境变量，请检查client.ts文件"
fi

# 检查Celery配置文件是否存在
if [ ! -f "backend/app/celery_config.py" ]
then
    echo "❌ Celery配置文件app/celery_config.py不存在"
    exit 1
fi
echo "✅ Celery配置文件已找到"

# 检查.env文件是否存在（可选）
if [ -f ".env" ]
then
    echo "✅ .env文件已找到"
    # 检查必要的环境变量是否配置
    required_env_vars=("PGHOST" "PGUSER" "PGPASSWORD" "REDIS_HOST")
    echo "正在检查.env文件中的必要环境变量..."
    for var in "${required_env_vars[@]}"
    do
        if grep -q "^$var=" .env
        then
            echo "  ✅ $var 已配置"
        else
            echo "  ⚠️ $var 未配置（部署前请确保设置）"
        fi
    done
else
    echo "⚠️ .env文件不存在，建议创建并配置外部数据库和Redis连接信息"
    echo "请参考DEPLOYMENT_GUIDE.md文档中的环境变量配置部分"
fi

# 显示成功信息
echo -e "\n🎉 基本环境检查已通过！请确保您已正确配置外部数据库和Redis连接。\n"
echo "部署前请确保："
echo "  1. 已配置.env文件或直接在docker-compose.yml中设置环境变量"
echo "  2. 外部PostgreSQL数据库可访问"
echo "  3. 外部Redis服务器可访问"
echo -e "\n您可以使用以下命令开始部署："
echo "  docker-compose up -d --build"
echo -e "\n部署完成后，可以使用以下命令查看服务状态："
echo "  docker-compose ps"
echo "  docker-compose logs -f backend"
echo "  docker-compose logs -f celery_worker_tuning"

echo -e "\n部署架构概览："
echo "  - 前端服务：Nginx (端口80)"
echo "    可通过VITE_API_BASE_URL环境变量配置后端接口地址"
echo "  - 后端服务：FastAPI (端口8000)"
echo "  - Celery服务：参数调优worker、默认队列worker、定时任务beat"
echo "  - 外部服务：PostgreSQL数据库、Redis缓存"

# 询问是否立即开始部署
read -p "是否立即开始部署？(y/n): " deploy_now

if [ "$deploy_now" = "y" ] || [ "$deploy_now" = "Y" ]
then
    echo "开始部署..."
    docker-compose up -d --build
    echo "部署命令已执行，请使用'docker-compose logs -f'查看部署进度"
    echo "部署完成后，可以使用'docker-compose ps'检查所有服务的运行状态"
else
    echo "部署测试完成，您可以稍后手动执行'docker-compose up -d --build'开始部署"
fi