#!/bin/bash
set -e

echo "⚠️ 开始卸载 TimescaleDB for PostgreSQL 16 ..."

# 停止 PostgreSQL 服务
sudo systemctl stop postgresql

# 删除 TimescaleDB 扩展（如存在）
sudo -u postgres psql -c "DROP DATABASE IF EXISTS timescaledb_test;" || true
sudo -u postgres psql -c "DROP EXTENSION IF EXISTS timescaledb CASCADE;" || true

# 卸载 TimescaleDB 软件包
sudo apt remove --purge -y timescaledb-2-postgresql-16
sudo apt autoremove -y
sudo apt clean

# 删除仓库源文件与缓存
sudo rm -f /etc/apt/sources.list.d/timescaledb.list
sudo apt update

# 重启 PostgreSQL 服务
sudo systemctl start postgresql

echo "✅ TimescaleDB 卸载完成。"
echo "🎯 PostgreSQL 已恢复为纯净版本。"
