import requests
import json

url = "http://localhost:8000/api/market/daily"
params = {
    "code": "BTCUSDT",
    "start": "2025-09-02 00:00:00",
    "end": "2025-09-08 23:59:00"
}

try:
    print(f"Testing endpoint: {url} with params: {params}")
    response = requests.get(url, params=params)
    print(f"Response status code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Response data count: {len(data.get('rows', []))}")
        print(f"Sample data: {json.dumps(data.get('rows', [])[:2], indent=2) if data.get('rows') else 'No data'}")
    else:
        print(f"Error response: {response.text}")
except Exception as e:
    print(f"Exception occurred: {str(e)}")