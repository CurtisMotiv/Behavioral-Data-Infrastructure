import csv
import io
import json
import os
import sys
import urllib.request
import zipfile
from datetime import datetime

import psycopg2
import requests
from psycopg2.extras import execute_values

DOL_ZIP_URL = 'https://www.dol.gov/sites/dolgov/files/ebsa/researchers/statistics/retirement-bulletins/form5500-2022.zip'
DOL_CSV_FALLBACK_URL = 'https://data.dol.gov/api/views/czt4-ztea/rows.csv?accessType=DOWNLOAD'
FILTER_KEYWORDS = [
    'health',
    'medical',
    'clinic',
    'fqhc',
    'federally qualified',
    'nonprofit',
    'non-profit',
    'charity',
    'health center',
    'community health',
    'plan',
    'sponsor',
]

SUPABASE_HOST = 'db.bnrmplilxdkfdtlscmnb.supabase.co'
SUPABASE_DATABASE = 'postgres'
SUPABASE_USER = 'postgres'
SUPABASE_PORT = 5432
TABLE_NAME = 'raw_form_5500'


def fetch_url(url):
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (compatible; ExtractionScript/1.0; +https://www.dol.gov/)',
            'Accept': '*/*',
        },
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read()


def fetch_csv_fallback(url):
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    return response.content


def matches_nonprofit_healthcare(text):
    normalized = text.lower()
    return any(keyword in normalized for keyword in FILTER_KEYWORDS)


def parse_csv_content(content_bytes):
    text = content_bytes.decode('utf-8', errors='replace')
    reader = csv.DictReader(io.StringIO(text))
    for index, row in enumerate(reader, start=1):
        raw_text = json.dumps(row, ensure_ascii=False)
        if matches_nonprofit_healthcare(raw_text):
            yield index, row


def load_records(conn, rows):
    insert_sql = f'''
        INSERT INTO {TABLE_NAME} (source_url, record_index, raw_json, loaded_at)
        VALUES %s
    '''

    execute_values(
        conn.cursor(),
        insert_sql,
        rows,
        template='(%s, %s, %s, %s)',
        page_size=100,
    )
    conn.commit()


def create_table(conn):
    with conn.cursor() as cur:
        cur.execute(f'''
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id SERIAL PRIMARY KEY,
                source_url TEXT,
                record_index INTEGER,
                raw_json JSONB,
                loaded_at TIMESTAMPTZ DEFAULT NOW()
            )
        ''')
    conn.commit()


def get_supabase_password():
    password = os.environ.get('SUPABASE_PASSWORD')
    if password:
        return password
    if 'SUPABASE_PASSWORD' not in os.environ:
        print('Please provide the Supabase password via the SUPABASE_PASSWORD environment variable.')
    return input('Supabase password: ').strip()


def connect_db(password):
    return psycopg2.connect(
        host=SUPABASE_HOST,
        database=SUPABASE_DATABASE,
        user=SUPABASE_USER,
        password=password,
        port=SUPABASE_PORT,
    )


def process_zip_archive(source_url, archive_bytes, conn):
    rows = []
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for member in archive.namelist():
            if member.endswith('/'):
                continue
            if member.lower().endswith('.csv'):
                content = archive.read(member)
                for record_index, row in parse_csv_content(content):
                    rows.append((source_url, record_index, json.dumps(row), datetime.utcnow()))

    if rows:
        load_records(conn, rows)
    return len(rows)


def process_csv_fallback(source_url, response_bytes, conn):
    rows = []
    for record_index, row in parse_csv_content(response_bytes):
        rows.append((source_url, record_index, json.dumps(row), datetime.utcnow()))

    if rows:
        load_records(conn, rows)
    return len(rows)


def main():
    password = get_supabase_password()
    if not password:
        print('No Supabase password provided; aborting.')
        sys.exit(1)

    conn = connect_db(password)
    create_table(conn)

    print('Attempting to download direct DOL bulk ZIP data...')
    try:
        archive_bytes = fetch_url(DOL_ZIP_URL)
        loaded = process_zip_archive(DOL_ZIP_URL, archive_bytes, conn)
        print(f'Loaded {loaded} records from direct bulk ZIP.')
    except Exception as error:
        print(f'Direct bulk ZIP download failed: {error}')
        print('Falling back to DOL open data CSV portal using requests...')
        response_bytes = fetch_csv_fallback(DOL_CSV_FALLBACK_URL)
        loaded = process_csv_fallback(DOL_CSV_FALLBACK_URL, response_bytes, conn)
        print(f'Loaded {loaded} records from fallback CSV portal.')

    conn.close()
    print(f'Finished. Stored data into {TABLE_NAME}.')


if __name__ == '__main__':
    main()
