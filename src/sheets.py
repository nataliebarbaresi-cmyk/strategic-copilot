import os
import json
import base64
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly',
]

RESULTS_TAB    = '3 - Opportunities CRM'
SCORED_TAB     = 'Scored URLs'
COMPANIES_TAB  = 'Config - Companies'
PROFILE_TAB    = 'Config - Profile'

RESULTS_HEADERS = [
    'Job Title', 'Company', 'Job URL', 'Source Lane', 'Date Posted', 'Days Since Posted',
    'Fit Score', 'Abstract Fit Flag', 'Scope Flag', 'Comp Signal',
    'Corporate Bottleneck', 'Strategic Thesis', 'Status',
]

_PROFILE_PLACEHOLDER = [
    ['Background',         'Replace with 2-3 sentences: your level, background, and what you do'],
    ['Anchors',            'Replace with anchors separated by | e.g. Built GTM motion from 0→1 | Launched product into new market'],
    ['Keywords',           'Replace with keywords separated by commas e.g. GTM, revenue operations, go-to-market'],
    ['Negative Signals',   'Replace with signals separated by | e.g. Pure sales quota role | Individual contributor only'],
    ['Comp Target',        ''],
    ['Score Threshold',    '6'],
    ['Location',           'US only'],
    ['Seniority Keywords', 'head of, vp, vice president, director, chief, principal, managing director, general manager'],
    ['Target Functions',   'gtm, go-to-market, sales, revenue, commercial, product ops, product operations, product strategy, business ops, business operations, strategy, transformation, enablement, customer success, partnerships, alliances, ai strategy, enterprise, growth, chief of staff, value engineering'],
    ['Exclude Functions',  'engineer, legal, counsel, compliance, finance, accounting, recruiter, recruiting, cybersecurity, data science, machine learning'],
]

_COMPANIES_PLACEHOLDER = [
    ['Example Company', 'ashby',      'example-handle', 'N', ''],
    ['Another Company', 'greenhouse', 'another-handle', 'N', ''],
]

_TAB_SETUP = [
    (COMPANIES_TAB, ['Company Name', 'ATS Type', 'ATS Handle', 'Active', 'Seniority Override'], _COMPANIES_PLACEHOLDER),
    (PROFILE_TAB,   ['Field', 'Value'],                                   _PROFILE_PLACEHOLDER),
    (SCORED_TAB,    ['Job URL'],                                          []),
    (RESULTS_TAB,   RESULTS_HEADERS,                                      []),
]


def get_client():
    raw = os.environ.get('GOOGLE_CREDENTIALS', '')
    if not raw:
        raise ValueError('GOOGLE_CREDENTIALS environment variable not set')
    try:
        creds_data = json.loads(base64.b64decode(raw).decode())
    except Exception:
        creds_data = json.loads(raw)
    creds = Credentials.from_service_account_info(creds_data, scopes=SCOPES)
    return gspread.authorize(creds)


def ensure_setup(client, spreadsheet_id: str):
    sheet = client.open_by_key(spreadsheet_id)
    existing = {ws.title for ws in sheet.worksheets()}
    created = []
    for tab_name, headers, placeholders in _TAB_SETUP:
        if tab_name not in existing:
            ws = sheet.add_worksheet(title=tab_name, rows=1000, cols=max(len(headers) + 2, 4))
            rows = [headers] + placeholders
            ws.update(rows, value_input_option='RAW')
            created.append(tab_name)
    if created:
        print(f'  Created tabs: {", ".join(created)}')
    return created


def _ws(client, spreadsheet_id: str, tab: str):
    return client.open_by_key(spreadsheet_id).worksheet(tab)


def read_seen_urls(client, spreadsheet_id: str) -> set:
    ws = _ws(client, spreadsheet_id, SCORED_TAB)
    values = ws.col_values(1)
    return set(v.strip() for v in values[1:] if v.strip())


def append_scored_urls(client, spreadsheet_id: str, urls: list):
    if not urls:
        return
    ws = _ws(client, spreadsheet_id, SCORED_TAB)
    ws.append_rows([[url] for url in urls], value_input_option='RAW')


def append_results(client, spreadsheet_id: str, jobs: list):
    if not jobs:
        return
    ws = _ws(client, spreadsheet_id, RESULTS_TAB)
    rows = [[str(job.get(h, '')) for h in RESULTS_HEADERS] for job in jobs]
    ws.append_rows(rows, value_input_option='USER_ENTERED')


def load_companies(client, spreadsheet_id: str) -> list:
    ws = _ws(client, spreadsheet_id, COMPANIES_TAB)
    records = ws.get_all_records()
    return [r for r in records if str(r.get('Active', '')).strip().upper() == 'Y']


def load_profile(client, spreadsheet_id: str) -> dict:
    ws = _ws(client, spreadsheet_id, PROFILE_TAB)
    records = ws.get_all_records()
    profile = {}
    for row in records:
        field = str(row.get('Field', '')).strip().lower().replace(' ', '_')
        value = str(row.get('Value', '')).strip()
        if field and value:
            profile[field] = value
    return profile
