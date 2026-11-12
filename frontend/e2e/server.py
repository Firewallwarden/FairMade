"""Browser-test process only: migrate an isolated database and bootstrap test accounts.

No production code, fake payment completion, patched provider or retained demo data.
"""
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
run_dir = Path(os.environ['E2E_RUN_DIR']).resolve()
allowed = root / '.e2e'
if not run_dir.is_relative_to(allowed):
    raise SystemExit('E2E_RUN_DIR must be inside frontend/.e2e')
run_dir.mkdir(parents=True, exist_ok=False)
os.environ['FAIRMADE_DATABASE_URL'] = f"sqlite:///{(run_dir / 'browser.sqlite3').as_posix()}"
os.environ['FAIRMADE_ASSISTANTS_ENABLED'] = 'true' if os.environ.get('E2E_PROVIDERS') == '1' else 'false'
os.environ['FAIRMADE_RECEIPTS_ENABLED'] = os.environ['FAIRMADE_ASSISTANTS_ENABLED']
if os.environ.get('E2E_PAYPAL') != '1':
    os.environ['FAIRMADE_PAYPAL_ENABLED'] = 'false'
subprocess.run([sys.executable, '-m', 'alembic', '-c', str(root.parent / 'backend/alembic.ini'), 'upgrade', 'head'], check=True)

from fastapi.testclient import TestClient
from fairmade.main import create_app

app = create_app()
with TestClient(app) as client:
    accounts = {}
    for role in ['admin', 'seller', 'buyer', 'denied']:
        credentials = {'email': f'browser-{role}@example.com', 'password': os.environ['E2E_PASSWORD']}
        response = client.post('/api/v1/auth/register', json=credentials)
        if response.status_code != 201:
            raise SystemExit('Synthetic browser account setup failed')
        accounts[role] = response.json()['id']
        if role in ['seller', 'denied', 'admin']:
            token_response = client.post('/api/v1/auth/login', json=credentials)
            token = token_response.json()['access_token']
            application = client.post('/api/v1/seller-applications', json={}, headers={'Authorization': f'Bearer {token}'})
            if application.status_code not in [200, 201]:
                raise SystemExit('Synthetic application setup failed')
    subprocess.run([sys.executable, '-m', 'fairmade.admin_bootstrap', '--account-id', accounts['admin'], '--reason', 'Isolated automated browser test reviewer'], check=True)

import uvicorn
uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('E2E_API_PORT', '8002')), access_log=False)
