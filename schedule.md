K线数据获取
# CMC加密货币列表采集定时任务
# 每隔2小时执行一次
0 */2 * * * cd /Users/aaronkliu/Documents/project/cfsQuant/backend/fetchdata && /usr/bin/python3 collect_market_crypto_listings.py >> /Users/aaronkliu/Documents/project/cfsQuant/logs/crypto_listings.log 2>&1

