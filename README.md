Trading Suite Full Package
Backend: backend/app
Frontend: frontend/src
Run backend: cd backend; pip install -r requirements.txt; uvicorn app.main:app --reload --port 8000
Run frontend: cd frontend; npm install; npm run dev
Database: backend/config/db_config.yaml contains default Postgres settings.

在后台启动Redis
redis-server --daemonize yes 


启动后端：
cd backend
uvicorn app.main:app --reload --port 8000


启动前端（若使用我之前更新的前端）：
cd frontend
npm install
npm run dev


# 每分钟抓分钟线
* * * * * /usr/bin/python3 /path/to/fetch_klines.py --interval 1m >> /var/log/fetch_klines.log 2>&1

# 每小时抓小时线
5 * * * * /usr/bin/python3 /path/to/fetch_klines.py --interval 1h >> /var/log/fetch_klines.log 2>&1

# 每天抓日线
5 0 * * * /usr/bin/python3 /path/to/fetch_klines.py --interval 1d >> /var/log/fetch_klines.log 2>&1
