import os

# 定义路由目录
router_dir = os.path.join(os.path.dirname(__file__), 'app', 'routers')

# 获取所有路由文件
router_files = [f for f in os.listdir(router_dir) if f.endswith('.py')]

# 检查每个路由文件
print("检查路由文件导入问题：")
for file_name in router_files:
    file_path = os.path.join(router_dir, file_name)
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    missing = []
    if 'APIRouter' in content and 'from fastapi import APIRouter' not in content:
        missing.append('APIRouter')
    if 'Query' in content and 'from fastapi import Query' not in content:
        missing.append('Query')
    
    if missing:
        print(f"{file_name}: 缺少导入 {', '.join(missing)}")
    else:
        print(f"{file_name}: 导入检查通过")