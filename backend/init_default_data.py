#!/usr/bin/env python3
"""
初始化默认租户和用户数据脚本
"""

import sys
import os

# 添加common.db模块路径
sys.path.append(os.path.join(os.path.dirname(__file__)))

from common.db import execute
from app.main.security import hash_password

def init_default_data():
    """初始化默认租户和用户数据"""
    
    # 1. 创建默认租户 "public"
    print("创建默认租户: public")
    try:
        execute(
            """
            INSERT INTO tenants (tenant_id, name, description, is_active, created_at, updated_at)
            VALUES ('public', '默认租户', '系统默认租户', TRUE, NOW(), NOW())
            ON CONFLICT (tenant_id) DO UPDATE SET 
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                is_active = EXCLUDED.is_active,
                updated_at = NOW()
            """
        )
        print("✓ 默认租户创建成功")
    except Exception as e:
        print(f"✗ 创建默认租户失败: {e}")
        return
    
    # 2. 创建超级管理员用户
    print("创建超级管理员用户: admin@local")
    try:
        # 生成密码哈希
        password = "ChangeMe123"
        hashed_password = hash_password(password)
        
        execute(
            """
            INSERT INTO tenant_users (id, tenant_id, email, hashed_password, full_name, is_admin, is_super_admin, is_active, created_at, updated_at)
            VALUES (
                '00000000-0000-0000-0000-000000000000', 
                'public', 
                'admin@local', 
                :hashed_password, 
                '系统管理员', 
                TRUE, 
                TRUE, 
                TRUE, 
                NOW(), 
                NOW()
            )
            ON CONFLICT (tenant_id, email) DO UPDATE SET 
                hashed_password = EXCLUDED.hashed_password,
                full_name = EXCLUDED.full_name,
                is_admin = EXCLUDED.is_admin,
                is_super_admin = EXCLUDED.is_super_admin,
                is_active = EXCLUDED.is_active,
                updated_at = NOW()
            """,
            hashed_password=hashed_password
        )
        print("✓ 超级管理员用户创建成功")
        print(f"   用户名: admin@local")
        print(f"   密码: ChangeMe123")
    except Exception as e:
        print(f"✗ 创建超级管理员用户失败: {e}")
        return
    
    # 3. 创建测试租户和用户
    print("创建测试租户: test")
    try:
        execute(
            """
            INSERT INTO tenants (tenant_id, name, description, is_active, created_at, updated_at)
            VALUES ('test', '测试租户', '用于测试的租户', TRUE, NOW(), NOW())
            ON CONFLICT (tenant_id) DO UPDATE SET 
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                is_active = EXCLUDED.is_active,
                updated_at = NOW()
            """
        )
        print("✓ 测试租户创建成功")
    except Exception as e:
        print(f"✗ 创建测试租户失败: {e}")
        return
    
    # 4. 创建测试用户
    print("创建测试用户: test@local")
    try:
        password = "Test123456"
        hashed_password = hash_password(password)
        
        execute(
            """
            INSERT INTO tenant_users (id, tenant_id, email, hashed_password, full_name, is_admin, is_super_admin, is_active, created_at, updated_at)
            VALUES (
                '11111111-1111-1111-1111-111111111111', 
                'test', 
                'test@local', 
                :hashed_password, 
                '测试用户', 
                TRUE, 
                FALSE, 
                TRUE, 
                NOW(), 
                NOW()
            )
            ON CONFLICT (tenant_id, email) DO UPDATE SET 
                hashed_password = EXCLUDED.hashed_password,
                full_name = EXCLUDED.full_name,
                is_admin = EXCLUDED.is_admin,
                is_super_admin = EXCLUDED.is_super_admin,
                is_active = EXCLUDED.is_active,
                updated_at = NOW()
            """,
            hashed_password=hashed_password
        )
        print("✓ 测试用户创建成功")
        print(f"   用户名: test@local")
        print(f"   密码: Test123456")
    except Exception as e:
        print(f"✗ 创建测试用户失败: {e}")
        return
    
    print("\n✅ 默认数据初始化完成!")
    print("\n可用账户:")
    print("1. 超级管理员 - admin@local / ChangeMe123 (租户: public)")
    print("2. 测试用户 - test@local / Test123456 (租户: test)")

if __name__ == "__main__":
    init_default_data()