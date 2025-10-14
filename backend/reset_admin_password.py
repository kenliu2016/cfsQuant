#!/usr/bin/env python3
"""
重置管理员密码脚本
"""

import bcrypt
from common.db import execute

def reset_admin_password():
    """重置admin@local用户的密码为ChangeMe123"""
    
    # 生成新的bcrypt哈希
    password = "ChangeMe123"
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    hashed_password_str = hashed_password.decode('utf-8')
    
    print(f"新密码哈希: {hashed_password_str}")
    print(f"哈希长度: {len(hashed_password_str)}")
    
    # 更新数据库
    sql = "UPDATE tenant_users SET hashed_password = :hashed_password, updated_at = NOW() WHERE email = 'admin@local'"
    
    try:
        result = execute(sql, hashed_password=hashed_password_str)
        print(f"密码更新成功，影响行数: {result}")
        
        # 验证更新是否成功
        from common.db import fetch_df
        df = fetch_df("SELECT email, hashed_password FROM tenant_users WHERE email = 'admin@local'")
        print(f"更新后的密码哈希: {df['hashed_password'].iloc[0]}")
        
        # 测试密码验证
        test_result = bcrypt.checkpw(password.encode('utf-8'), df['hashed_password'].iloc[0].encode('utf-8'))
        print(f"密码验证测试: {test_result}")
        
    except Exception as e:
        print(f"更新密码时出错: {e}")

if __name__ == "__main__":
    reset_admin_password()