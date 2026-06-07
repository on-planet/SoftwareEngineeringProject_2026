import sys
sys.path.insert(0, 'repo')
sys.path.insert(0, 'repo/api')

import os
os.environ['XUEQIUTOKEN'] = 'xq_a_token=test-token;u=test-user'
os.environ['SNOWBALL_TOKEN'] = 'xq_a_token=test-token;u=test-user'

from app.core.db import SessionLocal
from app.services.futures_service import list_futures, get_futures_series
from datetime import date

with SessionLocal() as db:
    items, total = list_futures(db, frequency='day', limit=10)
    print(f'Day query: {total} total, {len(items)} items')
    for item in items:
        print(item)
    
    print()
    items, total = list_futures(db, frequency='week', limit=10)
    print(f'Week query: {total} total, {len(items)} items')
    for item in items:
        print(item)
