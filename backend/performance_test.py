#!/usr/bin/env python3
"""
coin-analysis-table接口性能测试脚本
"""

import time
import requests
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置
BASE_URL = "http://localhost:8000"
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NjE2MTI3NDYsInN1YiI6IjExMTExMTExLTExMTEtMTExMS0xMTExLTExMTExMTExMTExMSIsInRlbmFudF9pZCI6InRlc3QiLCJpc19hZG1pbiI6dHJ1ZSwiaXNfc3VwZXJfYWRtaW4iOmZhbHNlfQ.Zu9bEENkhnpZfnv-flMaOnbGlQv6XSOJ160AwYdWjvo"
HEADERS = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json"
}

def test_single_request():
    """测试单次请求性能"""
    params = {
        "page": 1,
        "page_size": 10,
        "force_refresh": False
    }
    
    start_time = time.time()
    try:
        response = requests.get(
            f"{BASE_URL}/api/market/coin-analysis-table",
            headers=HEADERS,
            params=params,
            timeout=30
        )
        end_time = time.time()
        
        response_time = end_time - start_time
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "response_time": response_time,
                "status_code": response.status_code,
                "data_size": len(str(data)),
                "data_keys": list(data.keys()) if isinstance(data, dict) else "N/A"
            }
        else:
            return {
                "success": False,
                "response_time": response_time,
                "status_code": response.status_code,
                "error": response.text
            }
    except Exception as e:
        end_time = time.time()
        return {
            "success": False,
            "response_time": end_time - start_time,
            "error": str(e)
        }

def test_concurrent_requests(num_requests=10):
    """测试并发请求性能"""
    print(f"开始并发性能测试，并发数: {num_requests}")
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(test_single_request) for _ in range(num_requests)]
        
        results = []
        for future in as_completed(futures):
            results.append(future.result())
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # 分析结果
    successful_requests = [r for r in results if r["success"]]
    failed_requests = [r for r in results if not r["success"]]
    
    if successful_requests:
        response_times = [r["response_time"] for r in successful_requests]
        avg_response_time = statistics.mean(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        std_response_time = statistics.stdev(response_times) if len(response_times) > 1 else 0
        
        # 计算吞吐量
        throughput = len(successful_requests) / total_time
        
        return {
            "total_requests": num_requests,
            "successful_requests": len(successful_requests),
            "failed_requests": len(failed_requests),
            "total_time": total_time,
            "throughput": throughput,
            "avg_response_time": avg_response_time,
            "min_response_time": min_response_time,
            "max_response_time": max_response_time,
            "std_response_time": std_response_time,
            "success_rate": len(successful_requests) / num_requests * 100
        }
    else:
        return {
            "total_requests": num_requests,
            "successful_requests": 0,
            "failed_requests": num_requests,
            "error": "所有请求都失败了"
        }

def test_different_parameters():
    """测试不同参数组合的性能"""
    test_cases = [
        {"page": 1, "page_size": 10, "force_refresh": False},
        {"page": 2, "page_size": 20, "force_refresh": False},
        {"page": 1, "page_size": 50, "force_refresh": True},
        {"page": 3, "page_size": 5, "force_refresh": False}
    ]
    
    results = []
    
    for i, params in enumerate(test_cases, 1):
        print(f"测试参数组合 {i}/{len(test_cases)}: {params}")
        
        start_time = time.time()
        try:
            response = requests.get(
                f"{BASE_URL}/api/market/coin-analysis-table",
                headers=HEADERS,
                params=params,
                timeout=30
            )
            end_time = time.time()
            
            response_time = end_time - start_time
            
            if response.status_code == 200:
                data = response.json()
                results.append({
                    "params": params,
                    "response_time": response_time,
                    "status_code": response.status_code,
                    "data_size": len(str(data)),
                    "success": True
                })
            else:
                results.append({
                    "params": params,
                    "response_time": response_time,
                    "status_code": response.status_code,
                    "error": response.text,
                    "success": False
                })
        except Exception as e:
            end_time = time.time()
            results.append({
                "params": params,
                "response_time": end_time - start_time,
                "error": str(e),
                "success": False
            })
    
    return results

def main():
    """主测试函数"""
    print("=" * 60)
    print("coin-analysis-table接口性能测试")
    print("=" * 60)
    
    # 1. 单次请求测试
    print("\n1. 单次请求性能测试:")
    single_result = test_single_request()
    if single_result["success"]:
        print(f"   响应时间: {single_result['response_time']:.3f}秒")
        print(f"   状态码: {single_result['status_code']}")
        print(f"   数据大小: {single_result['data_size']} 字节")
        print(f"   数据键: {single_result['data_keys']}")
    else:
        print(f"   请求失败: {single_result.get('error', 'Unknown error')}")
    
    # 2. 并发请求测试
    print("\n2. 并发请求性能测试:")
    for concurrency in [5, 10, 20]:
        print(f"\n   并发数: {concurrency}")
        concurrent_result = test_concurrent_requests(concurrency)
        
        if concurrent_result.get("successful_requests", 0) > 0:
            print(f"   总时间: {concurrent_result['total_time']:.3f}秒")
            print(f"   吞吐量: {concurrent_result['throughput']:.2f} 请求/秒")
            print(f"   平均响应时间: {concurrent_result['avg_response_time']:.3f}秒")
            print(f"   最小响应时间: {concurrent_result['min_response_time']:.3f}秒")
            print(f"   最大响应时间: {concurrent_result['max_response_time']:.3f}秒")
            print(f"   响应时间标准差: {concurrent_result['std_response_time']:.3f}秒")
            print(f"   成功率: {concurrent_result['success_rate']:.1f}%")
        else:
            print(f"   测试失败: {concurrent_result.get('error', 'Unknown error')}")
    
    # 3. 不同参数测试
    print("\n3. 不同参数组合性能测试:")
    param_results = test_different_parameters()
    
    for result in param_results:
        if result["success"]:
            print(f"   参数 {result['params']}: {result['response_time']:.3f}秒, 数据大小: {result['data_size']}字节")
        else:
            print(f"   参数 {result['params']}: 失败 - {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 60)
    print("性能测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()