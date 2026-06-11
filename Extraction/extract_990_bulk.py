import json
import os
import re
import time
import urllib.parse

import psycopg2
import requests
from psycopg2.extras import execute_values

SUPABASE_HOST = 'db.bnrmplilxdkfdtlscmnb.supabase.co'
SUPABASE_DATABASE = 'postgres'
SUPABASE_USER = 'postgres'
SUPABASE_PASSWORD = '805Milwaukee541'
SUPABASE_PORT = 5432

PROPUBLICA_SEARCH_URL = 'https://projects.propublica.org/nonprofits/api/v2/search.json'
PROGRESS_FILE = os.path.join(os.path.dirname(__file__), 'extraction_progress.txt')

RAW_SITES_TABLE = 'raw_hrsa_sites'
RAW_990_TABLE = 'raw_990_organizations'
SKIP_SITE_KEYWORDS = ['clinic', 'mobile', 'unit', 'school based']


def connect_db():
    return psycopg2.connect(
        host=SUPABASE_HOST,
        database=SUPABASE_DATABASE,
        user=SUPABASE_USER,
        password=SUPABASE_PASSWORD,
        port=SUPABASE_PORT,
    )


def ensure_connection(conn):
    try:
        if conn is None or getattr(conn, 'closed', 1):
            return connect_db()
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
        return conn
    except psycopg2.Error:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
        return connect_db()


def load_progress():
    if not os.path.exists(PROGRESS_FILE):
        return 0
    try:
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as fh:
            return int(fh.read().strip() or 0)
    except Exception:
        return 0


def save_progress(index):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as fh:
        fh.write(str(index))


def create_target_table(conn):
    with conn.cursor() as cur:
        cur.execute(f'''
            CREATE TABLE IF NOT EXISTS {RAW_990_TABLE} (
                id SERIAL PRIMARY KEY,
                ein TEXT,
                name TEXT,
                asset_amount TEXT,
                income_amount TEXT,
                revenue_amount TEXT,
                ntee_code TEXT,
                raw_json JSONB,
                loaded_at TIMESTAMPTZ DEFAULT NOW()
            )
        ''')
        cur.execute(f'''
            CREATE UNIQUE INDEX IF NOT EXISTS {RAW_990_TABLE}_ein_idx
            ON {RAW_990_TABLE} (ein)
            WHERE ein IS NOT NULL
        ''')
    conn.commit()


def fetch_distinct_sites(conn):
    with conn.cursor() as cur:
        cur.execute(f'''
            select distinct site_name, state
            from {RAW_SITES_TABLE}
            where site_name is not null and site_name <> ''
              and state is not null and state <> ''
        ''')
        return cur.fetchall()


def search_propublica(name, state):
    params = {
        'q': name,
        'state[id]': state,
    }
    response = requests.get(PROPUBLICA_SEARCH_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def normalize_ein(ein):
    if ein is None:
        return None
    return str(ein).strip()


def extract_org_rows(search_response):
    organizations = search_response.get('organizations', [])
    for org in organizations:
        yield {
            'name': org.get('name'),
            'ein': normalize_ein(org.get('ein')),
            'asset_amount': org.get('asset_amount'),
            'income_amount': org.get('income_amount'),
            'revenue_amount': org.get('revenue_amount'),
            'ntee_code': org.get('ntee_code'),
            'raw_json': json.dumps(org),
        }


def insert_rows(conn, rows):
    if not rows:
        return 0

    conn = ensure_connection(conn)
    unique_rows = []
    eins = [normalize_ein(row.get('ein')) for row in rows if row.get('ein') is not None]
    if not eins:
        return 0

    with conn.cursor() as cur:
        cur.execute(f'''
            select ein
            from {RAW_990_TABLE}
            where ein = any(%s)
        ''', (eins,))
        existing_eins = {normalize_ein(row[0]) for row in cur.fetchall()}

    for row in rows:
        ein = normalize_ein(row.get('ein'))
        if not ein or ein in existing_eins:
            continue
        existing_eins.add(ein)
        unique_rows.append(row)

    if not unique_rows:
        return 0

    insert_sql = f'''
        INSERT INTO {RAW_990_TABLE} (name, ein, asset_amount, income_amount, revenue_amount, ntee_code, raw_json)
        VALUES %s
    '''
    execute_values(
        conn.cursor(),
        insert_sql,
        [(
            row['name'],
            row['ein'],
            row['asset_amount'],
            row['income_amount'],
            row['revenue_amount'],
            row['ntee_code'],
            row['raw_json'],
        ) for row in unique_rows],
        template='(%s, %s, %s, %s, %s, %s, %s)',
        page_size=100,
    )
    conn.commit()
    return len(unique_rows)


def normalize_site_name(name):
    return ' '.join(name.strip().split()) if name else ''


def derive_parent_org_name(name):
    if not name:
        return ''
    normalized = normalize_site_name(name)
    lower_name = normalized.lower()
    if any(keyword in lower_name for keyword in SKIP_SITE_KEYWORDS):
        parent = re.sub(r'\b(?:clinic|mobile|unit|school based)\b.*$', '', normalized, flags=re.I).strip()
        parent = re.sub(r'[\-,;:\s]+$', '', parent).strip()
        return parent
    return normalized


def main():
    conn = connect_db()
    conn = ensure_connection(conn)
    create_target_table(conn)
    sites = fetch_distinct_sites(conn)
    start_index = load_progress()

    total_inserted = 0
    processed_sites = 0
    for idx, (site_name, state) in enumerate(sites):
        if idx < start_index:
            continue

        normalized_name = normalize_site_name(site_name)
        search_name = derive_parent_org_name(normalized_name)

        if not search_name:
            print(f'  skipping satellite site: "{normalized_name}"')
            processed_sites += 1
            save_progress(idx + 1)
            if processed_sites % 10 == 0:
                print(f'Progress: {processed_sites} sites processed, {total_inserted} rows inserted')
            continue

        if search_name != normalized_name:
            print(f'  satellite site detected; searching parent org name: "{search_name}" state: {state}')
        else:
            print(f'  searching ProPublica for site: "{search_name}" state: {state}')

        try:
            response = search_propublica(search_name, state)
        except Exception as exc:
            print(f'  request failed for {search_name}, {state}: {exc}')
            save_progress(idx + 1)
            time.sleep(2)
            continue

        rows = list(extract_org_rows(response))
        inserted = insert_rows(conn, rows)
        total_inserted += inserted
        processed_sites += 1

        if total_inserted and total_inserted % 50 == 0:
            conn = ensure_connection(conn)
            print(f'  keepalive ping performed after {total_inserted} inserted rows')

        if processed_sites % 10 == 0:
            print(f'Progress: {processed_sites} sites processed, {total_inserted} rows inserted')

        save_progress(idx + 1)
        print(f'  found {len(rows)} results, inserted {inserted} rows')
        time.sleep(2)

    conn.close()
    print(f'Done. Inserted {total_inserted} candidate 990 records into {RAW_990_TABLE}.')


if __name__ == '__main__':
    main()
