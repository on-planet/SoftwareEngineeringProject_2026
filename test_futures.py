import sys
sys.path.insert(0, 'repo')
from etl.loaders.pg_loader import _get_loader
loader = _get_loader()

result = loader.query_all("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE 'futures%'")
print('Tables:', result)

try:
    result = loader.query_all('SELECT * FROM futures_prices LIMIT 5')
    print('futures_prices data:', result)
except Exception as e:
    print('Error querying futures_prices:', e)
