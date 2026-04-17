# AutoPipe Dashboard - Complete Stack

## Overview
This is the AutoPipe Dashboard, a full-stack ML pipeline monitoring system built with:
- **Backend**: FastAPI + SQLAlchemy + SQLite
- **Frontend**: React + TypeScript + Vite + Tailwind CSS

## Project Structure
```
autopipe/dashboard/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py         # FastAPI app entry
│   │   ├── db/
│   │   │   ├── models.py   # SQLAlchemy ORM models
│   │   │   ├── session.py  # Database connection
│   │   │   └── __init__.py
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── router.py       # Main API router
│   │   │       └── endpoints/
│   │   │           ├── auth.py
│   │   │           ├── dashboard.py
│   │   │           ├── pipelines.py
│   │   │           ├── runs.py
│   │   │           ├── models.py
│   │   │           ├── experiments.py
│   │   │           ├── drift.py
│   │   │           └── websocket.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── auth.py
│   │   │   └── events.py
│   │   ├── schemas/
│   │   │   └── __init__.py   # Pydantic schemas
│   │   ├── seed.py           # Database seeding
│   │   ├── requirements.txt
│   │   └── start.sh
│
└── frontend/               # React frontend
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── routes.tsx
    │   ├── api/
    │   │   ├── client.ts
    │   │   └── endpoints/
    │   │       ├── index.ts
    │   │       ├── auth.ts
    │   │       ├── dashboard.ts
    │   │       ├── pipelines.ts
    │   │       ├── runs.ts
    │   │       ├── models.ts
    │   │       ├── experiments.ts
    │   │       └── drift.ts
    │   ├── components/
    │   │   ├── layout/
    │   │   │   └── Layout.tsx
    │   │   └── ui/
    │   │       └── index.tsx
    │   ├── pages/
    │   │   ├── auth/
    │   │   ├── dashboard/
    │   │   ├── pipelines/
    │   │   ├── runs/
    │   │   ├── models/
    │   │   ├── experiments/
    │   │   ├── drift/
    │   │   └── settings/
    │   ├── stores/
    │   ├── types/
    │   ├── utils/
    │   └── styles/
    ├── dist/               # Built frontend
    ├── package.json
    ├── vite.config.ts
    └── tailwind.config.js
```

## Backend API Endpoints

### Authentication
- `POST /api/v1/auth/login` - Login with credentials
- `GET /api/v1/auth/me` - Get current user info
- `POST /api/v1/auth/register` - Register new user

### Dashboard
- `GET /api/v1/dashboard/overview` - Get dashboard statistics
- `GET /api/v1/dashboard/activity` - Get recent activity feed
- `GET /api/v1/dashboard/health` - Get system health status

### Pipelines
- `GET /api/v1/pipelines` - List pipelines
- `POST /api/v1/pipelines` - Create pipeline
- `GET /api/v1/pipelines/{id}` - Get pipeline details
- `PUT /api/v1/pipelines/{id}` - Update pipeline
- `DELETE /api/v1/pipelines/{id}` - Delete pipeline
- `POST /api/v1/pipelines/{id}/runs` - Trigger pipeline run

### Runs
- `GET /api/v1/runs` - List runs
- `GET /api/v1/runs/{id}` - Get run details
- `PATCH /api/v1/runs/{id}` - Update run
- `DELETE /api/v1/runs/{id}` - Delete run
- `GET /api/v1/runs/{id}/logs` - Get run logs
- `GET /api/v1/runs/{id}/steps` - Get run steps

### Models
- `GET /api/v1/models` - List registered models
- `POST /api/v1/models` - Register model
- `GET /api/v1/models/{id}` - Get model details
- `GET /api/v1/models/{id}/versions` - List model versions
- `POST /api/v1/models/{id}/versions` - Create model version

### Experiments
- `GET /api/v1/experiments` - List experiments
- `POST /api/v1/experiments` - Create experiment
- `GET /api/v1/experiments/{id}` - Get experiment details

### Drift Detection
- `GET /api/v1/drift` - List drift reports
- `POST /api/v1/drift/detect` - Trigger drift detection
- `GET /api/v1/drift/alerts` - List drift alerts
- `POST /api/v1/drift/alerts/{id}/acknowledge` - Acknowledge alert

### WebSocket
- `WS /api/v1/ws/runs/{run_id}` - Real-time run updates
- `WS /api/v1/ws/dashboard` - Dashboard real-time updates

## How to Run

### Prerequisites
- Python 3.8+ with uvicorn
- Node.js 18+ with pnpm/npm

### Install Dependencies
```bash
# Backend
cd autopipe/dashboard/backend
pip install -r requirements.txt

# Frontend
cd autopipe/dashboard/frontend
pnpm install
```

### Start the Backend
```bash
cd autopipe/dashboard/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend API will be available at:
- API: http://localhost:8000/api/v1
- Docs: http://localhost:8000/api/v1/docs
- Health: http://localhost:8000/health

### Build and Serve Frontend
```bash
cd autopipe/dashboard/frontend

# Build for production
pnpm exec vite build

# Serve built files (backend serves them automatically from /static)
# Or use dev server:
pnpm dev
```

## Default Credentials
- **Username**: admin
- **Password**: admin123
- **Role**: Admin (full access)

## Seeded Data
The database includes sample data:
- 4 users (admin, data_scientist, ml_engineer, viewer)
- 6 pipelines (customer_churn_training, fraud_detection, etc.)
- 15+ runs with various statuses
- Sample models and versions
- Drift detection reports
- Dashboard metrics

## Configuration
All configuration is in `backend/app/core/config.py`:
- Database: SQLite by default (configured for async)
- CORS origins: localhost:3000, localhost:5173
- JWT token expiry: 8 days
- Secret key: Auto-generated

## Notes
- The backend uses SQLite with aiosqlite for async support
- Password hashing is simplified SHA256 (use bcrypt for production)
- WebSocket support is implemented for real-time updates
- All API endpoints have OpenAPI documentation
