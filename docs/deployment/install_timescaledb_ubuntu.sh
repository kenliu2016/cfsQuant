#!/bin/bash
set -e

echo "🚀 开始安装 TimescaleDB for PostgreSQL 16 on Ubuntu 24.04..."

# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要工具
sudo apt install -y wget gnupg lsb-release apt-transport-https ca-certificates software-properties-common

# 添加 TimescaleDB 官方 GPG key
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -

# 添加 TimescaleDB 仓库源
echo "deb https://packagecloud.io/timescale/timescaledb/ubuntu $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/timescaledb.list

# 更新仓库列表
sudo apt update

# 安装 TimescaleDB 2.x (适配 PostgreSQL 16)
sudo apt install -y timescaledb-2-postgresql-16

# 自动调整 PostgreSQL 配置
sudo timescaledb-tune --yes

# 重启 PostgreSQL 服务
sudo systemctl restart postgresql

# 创建测试数据库并启用扩展
sudo -u postgres psql -c "CREATE DATABASE timescaledb_test;"
sudo -u postgres psql -d timescaledb_test -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
sudo -u postgres psql -d timescaledb_test -c "\dx"

echo "✅ TimescaleDB 安装完成并已启用！"
echo "🎯 你可以使用以下命令进入数据库:"
echo "    sudo -u postgres psql -d timescaledb_test"
