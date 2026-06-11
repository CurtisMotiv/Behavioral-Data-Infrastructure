import urllib.request
import json
import psycopg2

ein = '362167743'
data = json.loads(urllib.request.urlopen(f'https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json').read())
org = data.get('organization', {})
conn = psycopg2.connect(host='db.bnrmplilxdkfdtlscmnb.supabase.co', database='postgres', user='postgres', password='805Milwaukee541', port=5432)
cur = conn.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS raw_990_organizations (ein TEXT, name TEXT, asset_amount BIGINT, income_amount BIGINT, revenue_amount BIGINT, ntee_code TEXT, raw_json JSONB)')
cur.execute('INSERT INTO raw_990_organizations VALUES (%s,%s,%s,%s,%s,%s,%s)', (org.get('ein'), org.get('name'), org.get('asset_amount'), org.get('income_amount'), org.get('revenue_amount'), org.get('ntee_code'), json.dumps(org)))
conn.commit()
conn.close()
print('Success! Lawndale data loaded into Supabase.')