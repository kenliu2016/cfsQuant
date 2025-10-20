K线数据获取
# CMC加密货币列表采集定时任务
# 每天凌晨00:01分执行
1 0 * * * cd /Users/aaronkliu/Documents/project/cfsQuant/backend/fetchdata && /usr/bin/python3 collect_market_crypto_listings.py >> /Users/aaronkliu/Documents/project/cfsQuant/logs/crypto_listings.log 2>&1

