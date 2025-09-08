import requests
import json
import time
import uuid

BASE_URL = "http://localhost:8000/api"

class APITester:
    def __init__(self):
        self.session = requests.Session()
        self.results = []
        self.test_backtest_id = None
        self.test_task_id = None
        self.test_monitor_id = None
    
    def log_result(self, endpoint, status, message=""):
        self.results.append({
            "endpoint": endpoint,
            "status": "PASS" if status else "FAIL",
            "message": message
        })
        print(f"{endpoint}: {'PASS' if status else 'FAIL'} - {message}")
    
    def test_health(self):
        endpoint = f"{BASE_URL}/health"
        try:
            response = self.session.get(endpoint)
            if response.status_code == 200 and response.json().get("status") == "ok":
                self.log_result(endpoint, True, "Health check passed")
                return True
            else:
                self.log_result(endpoint, False, f"Unexpected status: {response.status_code} or content: {response.text}")
                return False
        except Exception as e:
            self.log_result(endpoint, False, f"Exception: {str(e)}")
            return False
    
    def test_market_endpoints(self):
        # Test daily candles
        endpoint = f"{BASE_URL}/market/daily"
        params = {
            "code": "BTCUSDT",
            "start": "2023-01-01 00:00:00",
            "end": "2023-01-07 23:59:59"
        }
        try:
            response = self.session.get(endpoint, params=params)
            if response.status_code == 200:
                data = response.json()
                if "rows" in data:
                    self.log_result(endpoint, True, f"Returned {len(data['rows'])} rows")
                else:
                    self.log_result(endpoint, False, "No 'rows' key in response")
            else:
                self.log_result(endpoint, False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result(endpoint, False, f"Exception: {str(e)}")
    
    def test_strategies_endpoints(self):
        # List strategies
        endpoint = f"{BASE_URL}/strategies"
        try:
            response = self.session.get(endpoint)
            if response.status_code == 200:
                data = response.json()
                if "rows" in data:
                    self.log_result(endpoint, True, f"Found {len(data['rows'])} strategies")
                else:
                    self.log_result(endpoint, False, "No 'rows' key in response")
            else:
                self.log_result(endpoint, False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result(endpoint, False, f"Exception: {str(e)}")
    
    def test_backtest_endpoints(self):
        # Create a backtest
        endpoint = f"{BASE_URL}/backtest"
        payload = {
            "code": "BTCUSDT",
            "start": "2023-01-01 00:00:00",
            "end": "2023-01-07 23:59:59",
            "strategy": "demo",
            "params": {}
        }
        try:
            response = self.session.post(endpoint, json=payload)
            if response.status_code == 200:
                data = response.json()
                if "backtest_id" in data:
                    self.test_backtest_id = data["backtest_id"]
                    self.log_result(endpoint, True, f"Created backtest with ID: {self.test_backtest_id}")
                else:
                    self.log_result(endpoint, False, "No 'backtest_id' in response")
            else:
                self.log_result(endpoint, False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result(endpoint, False, f"Exception: {str(e)}")
    
    def test_runs_endpoints(self):
        # Get recent runs
        endpoint = f"{BASE_URL}/runs?limit=5"
        try:
            response = self.session.get(endpoint)
            if response.status_code == 200:
                data = response.json()
                if "rows" in data:
                    self.log_result(endpoint, True, f"Found {len(data['rows'])} recent runs")
                else:
                    self.log_result(endpoint, False, "No 'rows' key in response")
            else:
                self.log_result(endpoint, False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result(endpoint, False, f"Exception: {str(e)}")
    
    def test_tuning_endpoints(self):
        # Start tuning (async, just check if it starts)
        endpoint = f"{BASE_URL}/tuning"
        payload = {
            "strategy": "demo",
            "code": "BTCUSDT",
            "start": "2023-01-01 00:00:00",
            "end": "2023-01-07 23:59:59",
            "params": {"short": [5, 10], "long": [20, 30]}
        }
        try:
            response = self.session.post(endpoint, json=payload)
            if response.status_code == 200:
                data = response.json()
                if "task_id" in data:
                    self.test_task_id = data["task_id"]
                    self.log_result(endpoint, True, f"Started tuning task: {self.test_task_id}")
                else:
                    self.log_result(endpoint, False, "No 'task_id' in response")
            else:
                self.log_result(endpoint, False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result(endpoint, False, f"Exception: {str(e)}")
    
    def test_monitor_endpoints(self):
        # Start monitor (async, just check if it starts)
        endpoint = f"{BASE_URL}/monitor/start"
        payload = {
            "strategy": "demo",
            "code": "BTCUSDT",
            "start": "2023-01-01 00:00:00",
            "interval": 10
        }
        try:
            response = self.session.post(endpoint, json=payload)
            if response.status_code == 200:
                data = response.json()
                if "monitor_id" in data:
                    self.test_monitor_id = data["monitor_id"]
                    self.log_result(endpoint, True, f"Started monitor: {self.test_monitor_id}")
                else:
                    self.log_result(endpoint, False, "No 'monitor_id' in response")
            else:
                self.log_result(endpoint, False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result(endpoint, False, f"Exception: {str(e)}")
    
    def test_export_endpoints(self):
        # Check export endpoint (we'll use a basic test)
        endpoint = f"{BASE_URL}/export/market/BTCUSDT/daily/2023-01-01/2023-01-07"
        try:
            response = self.session.get(endpoint)
            # We're just checking if the endpoint exists and responds
            if response.status_code in [200, 404]:  # 404 could be expected if no data
                self.log_result(endpoint, True, f"Endpoint accessible with status {response.status_code}")
            else:
                self.log_result(endpoint, False, f"Unexpected status code: {response.status_code}")
        except Exception as e:
            self.log_result(endpoint, False, f"Exception: {str(e)}")
    
    def test_predictions_endpoints(self):
        # Check predictions endpoint
        endpoint = f"{BASE_URL}/predictions"
        params = {
            "code": "BTCUSDT",
            "start": "2023-01-01 00:00:00",
            "end": "2023-01-07 23:59:59"
        }
        try:
            response = self.session.get(endpoint, params=params)
            # Similar to market endpoints, but predictions may not have data
            if response.status_code == 200:
                self.log_result(endpoint, True, "Endpoint accessible")
            else:
                self.log_result(endpoint, False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result(endpoint, False, f"Exception: {str(e)}")
    
    def run_all_tests(self):
        print("=== Starting API Endpoint Tests ===")
        
        # Start with health check
        if not self.test_health():
            print("API server not available. Exiting tests.")
            return
        
        # Add a small delay between tests
        time.sleep(0.5)
        
        # Run all other tests
        self.test_market_endpoints()
        time.sleep(0.5)
        
        self.test_strategies_endpoints()
        time.sleep(0.5)
        
        self.test_backtest_endpoints()
        time.sleep(0.5)
        
        self.test_runs_endpoints()
        time.sleep(0.5)
        
        self.test_tuning_endpoints()
        time.sleep(0.5)
        
        self.test_monitor_endpoints()
        time.sleep(0.5)
        
        self.test_export_endpoints()
        time.sleep(0.5)
        
        self.test_predictions_endpoints()
        
        # Print summary
        self.print_summary()
        
    def print_summary(self):
        print("\n=== API Test Summary ===")
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        
        for result in self.results:
            print(f"{result['status']}: {result['endpoint']} - {result['message']}")
        
        print(f"\nTotal tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success rate: {(passed/total)*100:.2f}%")

if __name__ == "__main__":
    tester = APITester()
    tester.run_all_tests()