import requests
import json
import time

# 测试日行情数据接口
def test_daily_market_data():
    url = "http://localhost:8000/api/market/daily"
    
    # 测试BTCUSDT的日行情数据
    params = {
        "code": "BTCUSDT",
        "start": "2025-09-02 00:00:00",
        "end": "2025-09-08 23:59:00"
    }
    
    try:
        print(f"测试日行情数据接口: {url}")
        print(f"请求参数: {params}")
        start_time = time.time()
        response = requests.get(url, params=params)
        end_time = time.time()
        
        print(f"响应状态码: {response.status_code}")
        print(f"请求耗时: {end_time - start_time:.4f} 秒")
        
        if response.status_code == 200:
            data = response.json()
            print(f"数据条数: {len(data.get('rows', []))}")
            print(f"数据结构: {json.dumps(data.get('columns', []), ensure_ascii=False, indent=2)}")
            if data.get('rows'):
                print(f"示例数据: {json.dumps(data.get('rows', [])[:2], ensure_ascii=False, indent=2)}")
            else:
                print("没有返回数据")
        else:
            print(f"错误响应: {response.text}")
    except Exception as e:
        print(f"请求异常: {str(e)}")

if __name__ == "__main__":
    test_daily_market_data()