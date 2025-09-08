import yaml
import os
import psycopg2
from psycopg2 import OperationalError

print("测试PostgreSQL数据库连接...")

# 获取配置文件路径
cfg_path = os.getenv("DB_CONFIG", os.path.join(os.path.dirname(__file__), "backend", "config", "db_config.yaml"))

# 读取配置文件
if os.path.exists(cfg_path):
    print(f"找到配置文件: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    
    pg = cfg.get("postgres", {})
    print(f"数据库配置: {pg}")
    
    # 构建连接字符串
    db_params = {
        'host': pg.get('host'),
        'port': pg.get('port'),
        'dbname': pg.get('dbname'),
        'user': pg.get('user'),
        'password': pg.get('password')
    }
    
    try:
        # 尝试连接数据库
        print("尝试连接到数据库...")
        conn = psycopg2.connect(**db_params)
        print("数据库连接成功!")
        
        # 尝试执行一个简单的查询
        print("尝试执行简单查询...")
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        print(f"PostgreSQL版本: {db_version}")
        
        # 检查表是否存在
        print("检查表是否存在...")
        cursor.execute("""SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'minute_realtime'
        );""")
        table_exists = cursor.fetchone()[0]
        print(f"minute_realtime表存在: {table_exists}")
        
        # 关闭连接
        cursor.close()
        conn.close()
        
    except OperationalError as e:
        print(f"数据库连接失败: {e}")
        print("\n可能的问题:")
        print("1. PostgreSQL服务器未启动")
        print("2. 主机名或端口错误")
        print("3. 数据库名称不存在")
        print("4. 用户名或密码错误")
        print("5. 防火墙阻止连接")
        print("6. PostgreSQL配置不允许远程连接")
else:
    print(f"配置文件不存在: {cfg_path}")