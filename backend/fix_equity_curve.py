from app.db import fetch_df, to_sql

# 修复equity_curve表数据 - 历史迁移脚本
# 注意：当前系统已全面使用equity_curve表，此脚本仅用于首次数据迁移
def fix_equity_curve():
    try:
        print("注意：当前系统已全面使用equity_curve表，此脚本仅用于首次数据迁移")
        # 查询equity表中的所有数据
        print("正在查询equity表中的数据...")
        equity_df = fetch_df('SELECT * FROM equity')
        print(f"成功获取 {len(equity_df)} 条equity数据")
        
        if equity_df.empty:
            print("equity表为空，无需修复")
            return
        
        # 复制数据到equity_curve表
        print("正在将数据复制到equity_curve表...")
        to_sql(equity_df, 'equity_curve', if_exists='replace')
        print(f"成功复制 {len(equity_df)} 条数据到equity_curve表")
        
        # 验证修复结果
        check_df = fetch_df('SELECT * FROM equity_curve LIMIT 5')
        print("修复后的equity_curve表数据预览:")
        print(check_df)
        
    except Exception as e:
        print(f"修复过程中出错: {e}")

if __name__ == "__main__":
    fix_equity_curve()