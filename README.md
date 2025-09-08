Trading Suite Full Package
Backend: backend/app
Frontend: frontend/src
Run backend: cd backend; pip install -r requirements.txt; uvicorn app.main:app --reload --port 8000
Run frontend: cd frontend; npm install; npm run dev
Database: backend/config/db_config.yaml contains default Postgres settings.



启动后端：
cd backend
uvicorn app.main:app --reload --port 8000


启动前端（若使用我之前更新的前端）：
cd frontend
npm install
npm run dev
