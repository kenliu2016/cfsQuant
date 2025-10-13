Trading Suite Full Package
Backend: backend/app
Frontend: frontend/src
Run backend: cd backend; pip install -r requirements.txt; uvicorn app.main:app --reload --port 8000
Run frontend: cd frontend; npm install; npm run dev
Database: backend/config/db_config.yaml contains default Postgres settings.

在后台启动Redis
redis-server --daemonize yes 

brew services restart postgresql


启动后端：
cd backend
uvicorn app.main.main:app --reload --port 8000


启动前端（若使用我之前更新的前端）：
cd frontend
npm install
npm run dev

启动队列
celery -A config.celery_config.celery_app worker --loglevel=info --pool=solo -Q tuning,backtest

## Multi-tenant Setup

- Run the migration script `backend/dbscripts/202501_multi_tenant.sql` against your PostgreSQL instance before starting the upgraded backend.
- All API calls now require the `X-Tenant-ID` header. The frontend automatically adds it and provides a selector in the top bar.
- Manage tenant records in the Settings page under “租户管理”. New tenants are available immediately and can be activated/deactivated from the UI.

## Real-time Trading Integration

- A new `/api/live-trading` namespace exposes account management and trading endpoints powered by `ccxt`.
- Configure exchange API keys per tenant from Settings → “实时交易账户”. Connection tests, enable/disable toggles, and account deletion are supported.
- Once an account is configured you can interact with the endpoints to pull balances, open orders, place or cancel orders programmatically.

