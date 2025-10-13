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
- When creating a tenant you can include `admin_email` / `admin_password` to seed the first administrator. This account can then invite additional users through the API or UI.
- Example tenant provisioning payload:

```bash
curl -X POST http://localhost:8000/api/tenants \
  -H 'Content-Type: application/json' \
  -d '{
        "tenant_id": "demo",
        "name": "Demo Tenant",
        "admin_email": "admin@demo.io",
        "admin_password": "ChangeMe123",
        "admin_name": "Demo Admin"
      }'
```

- After running the migration script a default administrator is available:
  - Tenant: `public`
  - Email: `admin@local`
  - Password: `ChangeMe123`

## Authentication & Session Flow

- The backend exposes `/api/auth/login`, `/api/auth/register`, and `/api/auth/me` endpoints and issues JWT access tokens scoped per-tenant.
- All application routers (backtest, market, strategies, tuning, exports, live-trading, etc.) now require a valid bearer token; unauthenticated calls return `401`.
- The frontend shows a login screen before rendering the main layout. Tokens are stored per tenant in `localStorage`, attached automatically to every request, and cleared on logout or 401 responses.
- Example login request:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{ "tenant_id": "demo", "email": "admin@demo.io", "password": "ChangeMe123" }'
```

## Real-time Trading Integration

- A new `/api/live-trading` namespace exposes account management and trading endpoints powered by `ccxt`.
- Configure exchange API keys per tenant from Settings → “实时交易账户”. Connection tests, enable/disable toggles, and account deletion are supported.
- Once an account is configured you can interact with the endpoints to pull balances, open orders, place or cancel orders programmatically.
