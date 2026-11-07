# Code Review Agent 🚀

> **AI-Powered Code Review Agent with Long-Term Memory Guidance, GitHub Integration, and Multi-Tenant Team Intelligence.**

Built on a unified modern stack:
**Python CLI + Next.js Frontend → FastAPI Backend → Neon PostgreSQL + Hindsight Cloud + Groq LPUs.**

---

## Architecture

```
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│     Next.js Web Dashboard       │       │       Python Terminal CLI       │
│  (React 19 / App Router / UI)   │       │   (Local Workstations / CI-CD)  │
└────────────────┬────────────────┘       └────────────────┬────────────────┘
                 │                                         │
                 │   HTTPS / Bearer Auth (PAT / JWT)       │
                 ▼                                         ▼
         ┌─────────────────────────────────────────────────────────┐
         │             FastAPI Backend Application                 │
         │          (Async SQLAlchemy 2.0 / Pydantic v2)           │
         └─────────────┬───────────────────┬─────────────────┬─────┘
                       │                   │                 │
      SQLAlchemy Async │      Vector Recall│      LPU Review │
                       ▼                   ▼                 ▼
             ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐
             │ Neon PostgreSQL │ │ Hindsight Cloud │ │  Groq Cloud   │
             │(Source of Truth)│ │ (Memory Banks)  │ │ (LLM Engine)  │
             └─────────────────┘ └─────────────────┘ └───────────────┘
```

- **Neon PostgreSQL (Lakebase)**: Permanent single source of truth for users, teams, reviews, findings, memory provenance, and tokens.
- **Hindsight Cloud**: Semantic vector memory layer for continuous learning and dynamic context recall.
- **Groq Cloud (LPU)**: Frontier ultra-fast LLM inference (`llama-3.3-70b-versatile`, `qwen-2.5-32b`).
- **FastAPI**: Asynchronous high-performance REST backend with strict RBAC.
- **Next.js 16**: Modern Web workspace built on the 21st.dev / Efferd Dashboard 3 design system.
- **Python CLI**: Developer-first terminal utility with native OS Keyring token storage.

---

## Key Features

1. **Intelligent Code Reviews**: Automated identification of bugs, security vulnerabilities (SQLi, XSS, CSRF), edge cases, and performance regressions with file/line references and concrete recommendations.
2. **Long-Term Memory Transparency (Hindsight Inspector)**: Audit active memory banks, inspect recalled memories, conduct real-time vector semantic searches, and trace exact memories injected into specific reviews.
3. **GitHub Repository & PR Intelligence**: Connect GitHub accounts, explore repositories, inspect branch trees, and automatically rank Pull Requests by complexity, test coverage, and tech stack alignment.
4. **Permanent Review History**: Query, search, filter (by source, status, severity, repository), sort, and paginate historical reviews stored permanently in Neon.
5. **Team Workspaces & RBAC**: Multi-tenant authorization (`Owner`, `Admin`, `Member`). Server-enforced permissions for inviting members, altering roles, managing rules, and configuring banks.
6. **Cross-Interface Synchronization**: Actions performed via terminal CLI instantly appear in the web dashboard, and team rules configured on the web immediately steer terminal reviews.
7. **Production Hardening**: Immune to SQL injection, prompt injection hardened, max diff payload safeguards, zero secret leakage, and graceful degradation during external provider downtime.

---

## Quickstart Guide

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ & npm
- A [Neon PostgreSQL](https://neon.tech) database
- A [Groq Cloud](https://console.groq.com) API key
- A [Vectorize Hindsight](https://cloud.vectorize.io) API key

### 2. Environment Setup
Clone the repository and copy the example environment configuration:
```bash
git clone https://github.com/your-username/code_review_agent.git
cd code_review_agent
cp .env.example .env
```
Edit `.env` and fill in your credentials (`DATABASE_URL`, `GROQ_API_KEY`, `HINDSIGHT_API_KEY`).

### 3. Backend Setup & Migrations
```bash
# Create and activate Python virtual environment
python -m venv .venv
source .venv/bin/activate

# Install backend package and dependencies
pip install -e .

# Apply Neon database schema migrations
alembic upgrade head

# Start FastAPI development server
uvicorn backend.main:app --reload --port 8000
```
Backend API interactive docs will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) to access the Code Review Agent Dashboard.

---

## Python CLI Usage

The CLI communicates with the centralized FastAPI server and stores authentication tokens securely in the host OS Keyring (macOS Keychain, Linux Secret Service, or Windows Credential Vault).

```bash
# 1. Authenticate with your shared corporate account
review-agent login --email engineer@company.com

# 2. Verify active user identity and team role
review-agent whoami

# 3. Submit a patch file for automated review
review-agent check path/to/feature.diff

# 4. Review a Git diff from stdin
git diff main | review-agent check -

# 5. Codify a new team guideline into memory
review-agent learn "All SQL operations must use parameterized queries."

# 6. Retrieve recent team code reviews
review-agent history --limit 10

# 7. Log out and purge stored token from OS keychain
review-agent logout
```

---

## Web Dashboard Pages

- **Overview (`/`)**: High-level KPIs (Total Reviews, Critical Issues, Retained Memories, Active Rules), recent activity stream, severity analytics, and Hindsight bank status.
- **Code Review (`/review`)**: Multi-tab workspace for direct diff submission, GitHub repository exploration, branch tree inspection, and Pull Request Intelligence ranking.
- **Hindsight Inspector (`/inspector`)**: Transparent audit of active memory bank ID, retained facts ledger with tags and dates, live vector search, and review provenance tracing.
- **Review History (`/history`)**: Searchable, filterable, sortable, and paginated permanent ledger of past reviews with severity breakdown badges and full diff/findings modals.
- **Team Rules (`/rules`)**: Codified engineering principles shared across CLI and Web reviews with keyword search and tag filtering.
- **Team Settings (`/settings`)**: Member invitations, role changes (Owner/Admin/Member), rule management, active bank configuration, model settings, and terminal setup guides.

---

## Automated Test Suites

The codebase includes comprehensive automated tests covering unit, integration, cross-interface synchronization, and security resilience:

```bash
# Run all 81 automated tests
PYTHONPATH=. ./.venv/bin/pytest backend/tests/ -v

# Run specific test suites
PYTHONPATH=. ./.venv/bin/pytest backend/tests/test_e2e_integration.py -v
PYTHONPATH=. ./.venv/bin/pytest backend/tests/test_security_resilience.py -v
PYTHONPATH=. ./.venv/bin/pytest backend/tests/test_history_and_teams.py -v
PYTHONPATH=. ./.venv/bin/pytest backend/tests/test_github.py -v
PYTHONPATH=. ./.venv/bin/pytest backend/tests/test_auth.py -v

# Run frontend build verification
cd frontend && npm run build
```

---

## Production Deployment

Detailed production deployment instructions for Railway, Render, Docker, Vercel, and Neon PostgreSQL are provided in [DEPLOYMENT.md](DEPLOYMENT.md).

```bash
# Run full production stack locally with Docker Compose
docker compose up --build
```

---

## License

MIT License. Designed and built with Google Antigravity & the DeepMind Agentic Coding team.

