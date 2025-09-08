#!/usr/bin/env python3
"""验证策略文件内容是否正确"""

from pathlib import Path

# 指定要验证的文件路径
file_path = Path("core/strategies/fixed_template_test.py")

# 检查文件是否存在
if not file_path.exists():
    print(f"错误: 文件不存在 - {file_path}")
    exit(1)

# 读取文件内容
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 显示文件的完整内容
print(f"=== {file_path} 的完整内容 ===")
print(content)
print("=== 内容结束 ===")

# 验证内容是否正确
if content.startswith("Strategy: fixed_template_test"):
    print("\n✓ 验证通过: 文件内容正确包含'Strategy: fixed_template_test'开头")
else:
    print("\n✗ 验证失败: 文件内容不以'Strategy: fixed_template_test'开头")
    print(f"实际开头: {repr(content[:30])}")

# 检查文件的行数和第一行内容
lines = content.split('\n')
print(f"\n文件共有 {len(lines)} 行")
print(f"第一行: {repr(lines[0])}")
print(f"第二行: {repr(lines[1])}")
print(f"第三行: {repr(lines[2])}")