# HDFC Mutual Fund FAQ Assistant

**Facts-only. No investment advice.**

RAG-based FAQ assistant for 5 HDFC mutual fund schemes on Groww. Offline corpus ingestion powers online classify → retrieve → generate → validate.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set GROQ_API_KEY

python scripts/ingest.py --scheme all
uvicorn src.api.main:app --reload --port 8000
cd frontend && npm install && npm run dev
```

## Daily ingestion scheduler

The corpus (Groww scheme pages) is refreshed automatically via GitHub Actions.

| Item | Detail |
|------|--------|
| Workflow | [`.github/workflows/daily-ingest.yml`](.github/workflows/daily-ingest.yml) |
| Schedule | **Every day at 10:00 AM IST** (04:30 UTC) |
| Pipeline | Fetch → parse → chunk → embed (BGE-small) → Chroma upsert |
| Command | `python scripts/ingest.py --scheme all --refresh` |

### Manual trigger

```bash
gh workflow run daily-ingest.yml
```

Or: **Actions → Daily corpus ingest → Run workflow**

### What gets persisted

After a successful run, the workflow commits updated `data/processed/` and `data/index/` so deployed instances serve fresh facts. Inspect the latest commit message: `chore(ingest): daily corpus refresh YYYY-MM-DD`.

### Verification

```bash
python scripts/verify_ingest.py
```

Fails if any scheme has empty processed text, chunk count is too low, or Chroma has fewer than 31 vectors.

### Failure alerts

If the workflow fails, a GitHub issue labeled `ingest-failure` is opened (or commented on if one already exists).

## Schemes

See [`src/config/schemes.yaml`](src/config/schemes.yaml) for the 5 HDFC schemes and Groww source URLs.

## Documentation

- [Problem statement](docs/problemStatement.md)
- [Architecture](docs/Architecture.md)
- [Implementation plan](docs/implementation-plan.md)

## Tests

```bash
pytest tests/ -v
```
