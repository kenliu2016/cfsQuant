import requests

def get_exchange_symbols(base_url):
    url = f"{base_url}/api/v3/exchangeInfo"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return [s["symbol"] for s in data["symbols"] if s["status"] == "TRADING"]

# Binance.com
symbols_com = get_exchange_symbols("https://api.binance.com")

# Binance.US
symbols_us = get_exchange_symbols("https://api.binance.us")

print("Binance.com 支持交易对数量:", len(symbols_com))
print("Binance.US 支持交易对数量:", len(symbols_us))
for s in symbols_com:
    print(s)