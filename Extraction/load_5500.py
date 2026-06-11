import csv
import os
from datetime import datetime

import psycopg2
from psycopg2.extras import execute_values

SUPABASE_HOST = 'db.bnrmplilxdkfdtlscmnb.supabase.co'
SUPABASE_DATABASE = 'postgres'
SUPABASE_USER = 'postgres'
SUPABASE_PASSWORD = '805Milwaukee541'
SUPABASE_PORT = 5432
TABLE_NAME = 'raw_form_5500'
CSV_FILE_PATH = 'f_5500_2025_latest.csv'

HEALTHCARE_NAICS = {
    '621111', '621112', '621210', '621310', '621320', '621330', '621340',
    '621391', '621399', '621491', '621492', '621493', '621498', '621511',
    '621512', '621610', '621910', '621991', '621999', '622110', '622210',
    '622310', '623110',
}

COLUMNS = [
    'ACK_ID',
    'PLAN_NAME',
    'SPONSOR_DFE_NAME',
    'SPONS_DFE_EIN',
    'SPONS_DFE_MAIL_US_STATE',
    'BUSINESS_CODE',
    'TYPE_PENSION_BNFT_CODE',
    'TOT_ACTIVE_PARTCP_CNT',
    'TOT_PARTCP_BOY_CNT',
    'FORM_PLAN_YEAR_BEGIN_DATE',
    'FILING_STATUS',
]


def connect_db():
    return psycopg2.connect(
        host=SUPABASE_HOST,
        database=SUPABASE_DATABASE,
        user=SUPABASE_USER,
        password=SUPABASE_PASSWORD,
        port=SUPABASE_PORT,
    )


def create_table(conn):
    with conn.cursor() as cur:
        cur.execute(f'''
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id SERIAL PRIMARY KEY,
                ACK_ID TEXT,
                PLAN_NAME TEXT,
                SPONSOR_DFE_NAME TEXT,
                SPONS_DFE_EIN TEXT,
                SPONS_DFE_MAIL_US_STATE TEXT,
                BUSINESS_CODE TEXT,
                TYPE_PENSION_BNFT_CODE TEXT,
                TOT_ACTIVE_PARTCP_CNT TEXT,
                TOT_PARTCP_BOY_CNT TEXT,
                FORM_PLAN_YEAR_BEGIN_DATE TEXT,
                FILING_STATUS TEXT,
                loaded_at TIMESTAMPTZ DEFAULT NOW()
            )
        ''')
    conn.commit()


def load_rows(conn, rows):
    if not rows:
        return 0

    insert_sql = f'''
        INSERT INTO {TABLE_NAME} (
            {', '.join(COLUMNS)}, loaded_at
        ) VALUES %s
    '''
    values = [tuple(row[col] for col in COLUMNS) + (datetime.utcnow(),) for row in rows]
    execute_values(conn.cursor(), insert_sql, values, template='(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)')
    conn.commit()
    return len(rows)


def load_csv():
    if not os.path.exists(CSV_FILE_PATH):
        raise FileNotFoundError(f'CSV file not found: {CSV_FILE_PATH}')

    filtered_rows = []
    with open(CSV_FILE_PATH, newline='', encoding='utf-8', errors='replace') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            business_code = row.get('BUSINESS_CODE', '').strip()
            if business_code in HEALTHCARE_NAICS:
                filtered_rows.append({col: row.get(col, '').strip() for col in COLUMNS})
    return filtered_rows


def main():
    rows = load_csv()
    print(f'Found {len(rows)} healthcare-related Form 5500 rows in {CSV_FILE_PATH}.')

    conn = connect_db()
    create_table(conn)
    loaded = load_rows(conn, rows)
    conn.close()

    print(f'Loaded {loaded} rows into {TABLE_NAME}.')


if __name__ == '__main__':
    main()
