# Production Deployment Guide: Code Review Agent

This guide covers complete end-to-end production deployment for the **Code Review Agent** across the centralized architecture:
**Python CLI + Next.js Frontend → FastAPI Backend → Neon PostgreSQL + Hindsight Cloud + Groq LPUs**.

---

## Architecture Overview

```
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│     Next.js Web Dashboard       │       │       Python Terminal CLI       │
│  (Vercel / Netlify / Node.js)   │       │   (Local Workstations / CI-CD)  │
└────────────────┬────────────────┘       └────────────────┬────────────────┘
                 │                                         │
                 │   HTTPS / Bearer Auth (PAT / JWT)       │
                 ▼                                         ▼
         ┌─────────────────────────────────────────────────────────┐
         │             FastAPI Backend Application                 │
         │          (Docker / Railway / Render / AWS)              │
         └─────────────┬───────────────────┬─────────────────┬─────┘
                       │                   │                 │
     SQLAlchemy Async  │      Vector Recall│      LPU Review │
                       ▼                   ▼                 ▼
             ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐
             │ Neon PostgreSQL │ │ Hindsight Cloud │ │  Groq Cloud   │
             │(Source of Truth)│ │ (Memory Banks)  │ │ (LLM Engine)  │
             └─────────────────┘ └─────────────────┘ └───────────────┘
```

---

## 1. Prerequisites & Cloud Accounts

1. **Neon PostgreSQL Database**:
   - Create a project on [Neon](https://neon.tech).
   - Copy the connection string with pooling enabled (`postgresql://...aws.neon.tech/neondb?sslmode=require`).
2. **Groq Cloud API Key**:
   - Generate an API key on [Groq Console](https://console.groq.com/keys).
   - Default model: `llama-3.3-70b-versatile` (or `qwen-2.5-32b`).
3. **Hindsight Cloud API Key**:
   - Obtain an API key from [Vectorize / Hindsight Cloud](https://cloud.vectorize.io).
   - Configure a default bank ID (e.g. `production` or team UUID).

---

## 2. Database Migrations (Neon PostgreSQL)

Before deploying the API server, apply the database schema migrations using Alembic:

```bash
# 1. Export your direct (unpooled) Neon database URL
export DATABASE_URL="postgresql://neondb_owner:YOUR_PASSWORD@ep-example.us-east-2.aws.neon.tech/neondb?sslmode=require"

# 2. Run migrations to the latest head
alembic upgrade head
```

This provisions all core tables:
- `users`, `teams`, `team_members` (RBAC)
- `reviews`, `review_findings`, `review_memories` (Audit logs and provenance)
- `team_rules`, `retained_facts`, `hindsight_banks` (Memory transparency)
- `api_tokens` (Secure Personal Access Tokens)
- `user_github_accounts` (GitHub App OAuth integration)

---

## 3. Backend Deployment (FastAPI)

### Option A: Deploy with Railway / Render (Recommended)

1. Connect your GitHub repository to Railway or Render.
2. Set root directory to `.`.
3. Set build command: `pip install .`
4. Set start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers 2 --proxy-headers`
5. Configure Environment Variables:
   ```env
   ENVIRONMENT=production
   PORT=8000
   DATABASE_URL=postgresql://neondb_owner:...@ep-example.aws.neon.tech/neondb?sslmode=require
   GROQ_API_KEY=gsk_...
   GROQ_MODEL=llama-3.3-70b-versatile
   HINDSIGHT_API_KEY=hsk_...
   HINDSIGHT_BASE_URL=https://cloud.vectorize.io/api/v1
   HINDSIGHT_BANK_ID=default
   CORS_ORIGINS=["https://dashboard.yourcompany.com"]
   ```

### Option B: Deploy with Docker

```bash
# 1. Build the production image
docker build -t code-review-agent-backend -f Dockerfile.backend .

# 2. Run container with environment configuration
docker run -d \
  --name code-review-backend \
  -p 8000:8000 \
  --env-file .env \
  code-review-agent-backend
```

---

## 4. Frontend Deployment (Next.js Dashboard)

### Option A: Deploy to Vercel (Recommended)

1. Connect the repository to [Vercel](https://vercel.com).
2. Set Root Directory to `frontend`.
3. Framework Preset: `Next.js`.
4. Configure Environment Variable:
   ```env
   NEXT_PUBLIC_API_URL=https://api.yourcompany.com
   ```
5. Click **Deploy**. Vercel will automatically build the static and SSR App Router routes.

### Option B: Deploy with Docker

```bash
cd frontend
docker build -t code-review-agent-frontend -f Dockerfile .
docker run -d -p 3000:3000 -e NEXT_PUBLIC_API_URL=https://api.yourcompany.com code-review-agent-frontend
```

---

## 5. CLI Deployment & Team Onboarding

Distribute the CLI to engineering workstations or CI/CD pipelines:

### Workstation Installation
```bash
# 1. Install CLI from source or package
pip install .

# 2. Configure target production backend
export REVIEW_AGENT_API_URL="https://api.yourcompany.com"

# 3. Log in with your corporate email
review-agent login --email engineer@yourcompany.com
```

The CLI securely stores the issued Personal Access Token directly in the operating system credential store (macOS Keychain, Linux Secret Service, or Windows Credential Vault).

### Daily CLI Usage
```bash
# Review a Git diff
git diff main | review-agent check -

# Retain a team coding guideline
review-agent learn "All API endpoints must validate input schemas."

# Audit review history
review-agent history --limit 10

# Verify identity and team memberships
review-agent whoami
```

---

## 6. Security & Production Checklist

- [x] **Zero Plaintext Secrets**: Secrets (`GROQ_API_KEY`, `HINDSIGHT_API_KEY`, DB credentials) remain exclusively server-side.
- [x] **CORS Enforcement**: Production origin whitelist prevents unauthorized browser cross-origin requests.
- [x] **SQL Injection Immunity**: 100% parameterized SQLAlchemy 2.0 ORM expressions.
- [x] **Prompt Injection Hardening**: Strict boundary instructions isolate user diff code from system review execution.
- [x] **Payload Safeguards**: Diffs exceeding 500KB are safely rejected (HTTP 422).
- [x] **Graceful Degradation**: Hindsight memory outages gracefully fall back to Neon-persisted team rules without breaking reviews.
- [x] **Health Check Endpoint**: `GET /health` returns operational status for load balancers.

