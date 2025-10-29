#!/bin/bash

# 物化视图自动刷新服务启动脚本
# 该脚本启动物化视图的自动刷新服务，实现每15分钟自动更新

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKEND_DIR="${PROJECT_ROOT}/backend"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到python3命令"
    exit 1
fi

# 检查脚本文件是否存在
REFRESH_SCRIPT="${SCRIPT_DIR}/refresh_materialized_views.py"
if [ ! -f "${REFRESH_SCRIPT}" ]; then
    echo "错误: 刷新脚本不存在: ${REFRESH_SCRIPT}"
    exit 1
fi

echo "=== 启动物化视图自动刷新服务 ==="
echo "项目根目录: ${PROJECT_ROOT}"
echo "后端目录: ${BACKEND_DIR}"
echo "刷新脚本: ${REFRESH_SCRIPT}"
echo "配置: 每15分钟自动刷新物化视图"
echo ""

# 切换到后端目录
cd "${BACKEND_DIR}"

# 检查数据库连接
echo "检查数据库连接..."
python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='localhost',
        port='5432',
        database='quant',
        user='cfs',
        password='Cc563479,.'
    )
    print('✓ 数据库连接成功')
    conn.close()
except Exception as e:
    print('✗ 数据库连接失败:', e)
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "数据库连接检查失败，请确保数据库服务正在运行"
    exit 1
fi

# 检查物化视图是否存在
echo "检查物化视图状态..."
python3 -c "
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port='5432',
    database='quant',
    user='cfs',
    password='Cc563479,.'
)

cursor = conn.cursor()

views_to_check = [
    'dashboard_market_sentiment',
    'dashboard_strong_weak_coins',
    'dashboard_coin_analysis',
    'dashboard_24h_performance'
]

print('物化视图状态:')
for view_name in views_to_check:
    cursor.execute('''
        SELECT schemaname, matviewname, ispopulated 
        FROM pg_matviews 
        WHERE schemaname = 'public' 
        AND matviewname = %s;
    ''', (view_name,))
    
    result = cursor.fetchone()
    if result:
        schema, name, populated = result
        status = '已填充' if populated else '未填充'
        print(f'  ✓ {name}: {status}')
    else:
        print(f'  ⚠ {view_name}: 不存在')

cursor.close()
conn.close()
"

echo ""
echo "启动自动刷新服务..."

# 启动刷新服务
python3 "${REFRESH_SCRIPT}"

# 如果服务退出，显示退出信息
echo "物化视图自动刷新服务已停止"