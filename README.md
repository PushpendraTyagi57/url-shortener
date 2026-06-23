#  URL Shortener

A production-ready URL shortener REST API built with **FastAPI**, **PostgreSQL**, and **Redis** — designed for performance, scalability, and simplicity.

🔗 **Live API:** https://url-shortener-production-5390.up.railway.app/docs

---

##  Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI (Python) |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Deployment | Railway |
| Containerization | Docker & Docker Compose |

---

##  Features

- **Base62 Encoding** — Auto-incremented IDs converted to short codes (e.g. `100` → `1C`). Zero collision risk by design, supports 56 billion unique URLs before reaching 6 characters
- **Redis Caching** — Hot URLs served from memory. Repeat redirects never touch the database
- **Click Analytics** — Every redirect increments a click counter, queryable via `/stats`
- **Rate Limiting** — 10 requests/min on shortening, 60 requests/min on redirects per IP
- **Auto Table Creation** — SQLAlchemy creates the database schema on startup, no manual migration needed

---

##  API Endpoints

### `POST /shorten`
Shorten a long URL.

**Request:**
```json
{
  "long_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response:**
```json
{
  "short_url": "https://url-shortener-production-5390.up.railway.app/1C",
  "short_code": "1C",
  "long_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

---

### `GET /{short_code}`
Redirects to the original URL (301).

```
GET /1C  →  301 Redirect  →  https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

---

### `GET /stats/{short_code}`
Returns analytics for a short URL.

**Response:**
```json
{
  "short_code": "1C",
  "long_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "click_count": 42,
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

##  How It Works

### Shortening Flow
```
POST /shorten
    │
    ├── Insert long_url into PostgreSQL
    │       └── Get auto-incremented ID (e.g. 100)
    │
    ├── Encode ID to Base62 (100 → "1C")
    │       └── Update short_code in same transaction
    │
    ├── Cache in Redis (TTL: 7 days)
    │
    └── Return short_url
```

### Redirect Flow
```
GET /1C
    │
    ├── Check Redis → HIT?
    │       └── Increment click_count → 301 Redirect ⚡
    │
    └── Cache MISS → Query PostgreSQL (indexed lookup)
            └── Populate Redis → Increment click_count → 301 Redirect
```

---

##  Performance

Load tested with [Locust](https://locust.io) — 50 concurrent users against the live Railway deployment:

| Metric | Result |
|---|---|
| Throughput | ~21 RPS |
| Avg Latency | ~310ms (India → US) |
| Median Latency | ~300ms |
| 99th Percentile | ~370ms |
| Error Rate | ~14% (rate limiter, expected) |

> **Note:** Latency is network-bound (India → US). On a server co-located with users, expected latency would be 50–80ms.

---

##  Project Structure

```
url-shortener/
├── main.py              # All routes + Base62 logic + rate limiting
├── database.py          # PostgreSQL engine + session management
├── models.py            # URLs table schema
├── locustfile.py        # Load testing script
├── Dockerfile           # Container definition
├── docker-compose.yml   # Full stack local setup
├── requirements.txt     # Python dependencies
└── pyproject.toml       # uv project config
```

---

##  Run Locally

### Option 1 — Docker Compose (recommended)
```bash
git clone https://github.com/PushpendraTyagi57/url-shortener.git
cd url-shortener
docker compose up --build
```
API live at `http://localhost:8000/docs`

### Option 2 — Manual
```bash
git clone https://github.com/PushpendraTyagi57/url-shortener.git
cd url-shortener

# Start PostgreSQL and Redis
docker run --name postgres-url -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=urlshortener -p 5432:5432 -d postgres:16-alpine
docker run --name redis-url -p 6379:6379 -d redis:7-alpine

# Install dependencies and run
uv venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv add fastapi uvicorn sqlalchemy psycopg2-binary redis slowapi python-dotenv
uvicorn main:app --reload
```

---

##  Scalability Design

This project is intentionally designed to scale horizontally:

- **Stateless API** — No state stored in the application layer. Run N instances behind a load balancer with zero code changes
- **Redis caching** — Repeat redirects for popular URLs skip the database entirely, meaning DB load stays flat as traffic grows
- **Indexed lookups** — `short_code` column is indexed in PostgreSQL, guaranteeing O(log n) lookups regardless of table size
- **Base62 from auto-increment** — No random generation, no collision checks, no retry logic needed. Guaranteed unique by design

---

##  Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/urlshortener` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `BASE_URL` | Base URL for short links | `http://localhost:8000` |