#!/bin/bash

# PostgreSQL 17 完全重装脚本
# 包括清理、安装、数据库和用户创建

echo "=== PostgreSQL 17 完全重装开始 ==="

# --- 1. 停止并卸载现有 PostgreSQL 17 ---
echo "1. 停止并卸载现有 PostgreSQL 17..."
brew services stop postgresql@17 2>/dev/null || true
brew uninstall --force postgresql@17 2>/dev/null || true

# 清理残留文件
echo "清理残留文件..."
sudo rm -rf /usr/local/var/postgresql@17 2>/dev/null || true
sudo rm -rf /usr/local/etc/postgresql@17 2>/dev/null || true
sudo rm -rf /usr/local/opt/postgresql@17 2>/dev/null || true

# --- 2. 重新安装 PostgreSQL 17 ---
echo "2. 重新安装 PostgreSQL 17..."
brew install postgresql@17

# --- 3. 初始化数据库 ---
echo "3. 初始化数据库..."
initdb /usr/local/var/postgresql@17 -E utf8

# --- 4. 启动 PostgreSQL 服务 ---
echo "4. 启动 PostgreSQL 服务..."
brew services start postgresql@17

# 等待服务启动
sleep 5

# --- 5. 创建数据库和用户 ---
echo "5. 创建数据库和用户..."

# 使用默认的postgres用户连接到默认数据库
PG_BIN="/usr/local/opt/postgresql@17/bin"

# 创建用户cfs
"$PG_BIN/psql" -h localhost -U $(whoami) -d postgres -c "CREATE USER cfs WITH PASSWORD 'Cc563479,.';" 2>/dev/null || echo "用户cfs可能已存在"

# 创建数据库quant
"$PG_BIN/psql" -h localhost -U $(whoami) -d postgres -c "CREATE DATABASE quant OWNER cfs;" 2>/dev/null || echo "数据库quant可能已存在"

# 授予用户权限
"$PG_BIN/psql" -h localhost -U $(whoami) -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE quant TO cfs;"

# --- 6. 验证安装 ---
echo "6. 验证安装..."

# 检查服务状态
brew services list | grep postgresql@17

# 测试连接
echo "测试数据库连接..."
"$PG_BIN/psql" -h localhost -U cfs -d quant -c "SELECT version();"

echo "=== PostgreSQL 17 重装完成 ==="
echo "数据库信息："
echo "- 数据库名: quant"
echo "- 用户名: cfs"
echo "- 密码: Cc563479,."
echo "- 主机: localhost"
echo "- 端口: 5432"