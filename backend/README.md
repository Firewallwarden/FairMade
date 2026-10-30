# FairMade backend

The first Fair Price Engine slice is a stateless production-economics API.
It calculates true batch and unit costs, fee-aware break-even prices, a price
range based on seller-selected margins, and profit simulations. It does not
save business data, change prices, or contact payment or AI services.

Use Python 3.11 or newer. From this feature's worktree root, create an isolated
environment, install the backend, and start the API:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './backend[dev]'
.\.venv\Scripts\python.exe -m uvicorn fairmade.main:app --reload --host 127.0.0.1
```

Interactive API documentation: <http://127.0.0.1:8000/docs>.
Machine-readable contract: <http://127.0.0.1:8000/openapi.json>.

```powershell
Invoke-RestMethod -Method Post `
  -Uri 'http://127.0.0.1:8000/api/v1/pricing/analyze' `
  -ContentType 'application/json' `
  -Body (Get-Content -Raw backend/examples/pricing-request.json)
```

Run checks from the worktree root:

```powershell
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
```

The API currently has no identity, database, or authentication layer. Run it
locally; access control and deployment hardening belong to the next backend
milestones before it becomes a hosted seller service. No frontend is included.

See [the API contract and formulas](../docs/fair-price-engine.md).
