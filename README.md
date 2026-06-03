# Backend API Smoke Test

Run this after starting FastAPI locally (`http://localhost:8000` by default).

## Script

- [`scripts/api_smoke_test.sh`](/home/kalyan/Desktop/Lms_Video_Analysis/backend/scripts/api_smoke_test.sh)

## What it verifies

1. Admin register/login
2. Form create
3. Assignment create
4. Candidate assignment add
5. Candidate login
6. Exam save progress
7. Exam submit
8. Admin review update
9. Candidate result fetch

## Usage

```bash
cd backend
chmod +x scripts/api_smoke_test.sh
./scripts/api_smoke_test.sh
```

Optional environment overrides:

```bash
BASE_URL=http://localhost:8000 \
ADMIN_EMAIL=admin@example.com \
ADMIN_PASSWORD=admin123 \
CANDIDATE_EMAIL=candidate@example.com \
./scripts/api_smoke_test.sh
```

## Seed test logins

Use this to generate reusable admin/candidate credentials for manual UI testing.

```bash
cd backend
python3 scripts/seed_test_logins.py --local
```

If you want to seed your real DB instead:

```bash
cd backend
DATABASE_URL='postgresql://user:pass@host:port/dbname?sslmode=require' python3 scripts/seed_test_logins.py
```
