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

## Role-based Permissions

- **Super Administrator** (`is_super_admin = true`)
  - Full visibility into all tenants (active and inactive) and their data.
  - May switch tenant context via `X-Tenant-ID`, manage tenants, users, and audit logs across the platform.
- **Tenant Administrator** (`is_admin = true`)
  - Manage users within their tenant (create, disable, promote/demote admin).
  - Configure trading accounts for any tenant user.
  - View all business data and audit logs inside the tenant, but cannot delete historical data.
- **Tenant User**
  - Manage only their own trading accounts.
  - View only business data they created (e.g. backtests); no destructive operations are permitted.

## Audit Logging

- Every authenticated request is recorded in `tenant_audit_logs` with user, tenant, endpoint, status, and client metadata.
- Super/Tenant administrators can query logs via `GET /api/audit-logs?offset=0&limit=100` (front-end Settings page will surface this in upcoming iterations).

## Real-time Trading Integration

- A new `/api/live-trading` namespace exposes account management and trading endpoints powered by `ccxt`.
- Configure exchange API keys per tenant from Settings → “实时交易账户”. Connection tests, enable/disable toggles, and account deletion are supported.
- Once an account is configured you can interact with the endpoints to pull balances, open orders, place or cancel orders programmatically.



┌─────────────────────────────────────────────────────────────┐
│                     选币系统工作流程                           │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   数据源      │────▶│  选币引擎     │────▶│  结果输出      │
│              │     │              │     │              │
│ • VMR指标表   │     │ • VMR加权     │     │ • 结果表      │
│ • K线数据表   │     │ • 涨幅计算     │     │ • API接口    │
│ • 市值数据    │     │ • 排序筛选     │     │ • 通知推送    │
└──────────────┘     └──────────────┘     └──────────────┘
       │                     │                     │
       ▼                     ▼                     ▼
  [定时更新]           [定时执行]            [实时查询]
   每小时               每4小时              随时访问


### 评分系统（总分范围：-7 到 +7）
系统采用 6个维度 进行综合评分，每个维度有特定的权重和判定标准：
 1. 价格与长期移动平均线关系（权重：2分）
- 看涨条件 ：当前价格 > 长期移动平均线（200周期）
- 看跌条件 ：当前价格 < 长期移动平均线
- 权重最高 ：反映长期趋势方向 
2. 短期与长期移动平均线关系（权重：1分）
- 看涨条件 ：短期移动平均线（50周期） > 长期移动平均线
- 看跌条件 ：短期移动平均线 < 长期移动平均线
- 反映趋势强度 ：金叉/死叉信号 
3. 价格结构斜率分析（权重：1分）
- 看涨条件 ：高点斜率 > 0 且 低点斜率 > 0（高点更高、低点更高）
- 看跌条件 ：高点斜率 < 0 且 低点斜率 < 0（高点更低、低点更低）
- 分析趋势结构 ：基于最近24小时的价格结构 
4. 量价相关性分析（权重：1分）
- 看涨条件 ：量价相关系数 > 0.1（正相关）
- 看跌条件 ：量价相关系数 < -0.1（负相关）
- 中性条件 ：相关系数在-0.1到0.1之间（不评分） 
5. 资金费率信号（权重：1分）
- 看涨条件 ：资金费率 > 0（正费率）
- 看跌条件 ：资金费率 < 0（负费率）
- 反映市场情绪 ：永续合约的资金费率 
6. 稳定币流入信号（权重：1分）
- 看涨条件 ：稳定币流入量 > 0（资金流入）
- 看跌条件 ：稳定币流入量 < 0（资金流出）
- 反映资金流向 ：市场资金面的变化
### 牛熊判定标准 牛市判定（总分 ≥ 3）
- 需要至少3个看涨信号，或者2个看涨信号（其中包含权重2分的价格与长期均线关系）
- 表明市场处于明显的上涨趋势 熊市判定（总分 ≤ -3）
- 需要至少3个看跌信号，或者2个看跌信号（其中包含权重2分的价格与长期均线关系）
- 表明市场处于明显的下跌趋势 中性状态（总分在-2到+2之间）
- 市场信号不明确，多空力量相对均衡
- 需要等待更明确的趋势信号
### 技术指标参数
- 移动平均线 ：短期50周期，长期200周期
- 价格结构分析 ：基于24小时数据
- 量价相关性 ：24个数据点窗口
- 数据回溯 ：48小时K线数据
### 判定特点
1. 1.
   多维度综合 ：结合技术指标和基本面信号
2. 2.
   权重差异化 ：价格与长期均线关系权重最高
3. 3.
   阈值明确 ：±3分作为牛熊分界线
4. 4.
   实时更新 ：每次运行都会重新计算和判定