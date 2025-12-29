from datetime import datetime, timedelta
import mysql.connector
import json
from config import DB_CONFIG_HOST, DB_CONFIG_PORT, DB_CONFIG_USER, DB_CONFIG_PASSWORD, DB_CONFIG_CRUNCHBASE_DATABASE

DB_CONFIG = {
    "host": DB_CONFIG_HOST,
    "port": DB_CONFIG_PORT,
    "user": DB_CONFIG_USER,
    "password": DB_CONFIG_PASSWORD,
    "database": DB_CONFIG_CRUNCHBASE_DATABASE,
}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def save_company(data: dict):
    """Insert or update company row."""
    url = data.get("url")
    if not url:
        return

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO companies (url, data, created_at, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
                data = VALUES(data),
                updated_at = CURRENT_TIMESTAMP
        """, (url, json.dumps(data, ensure_ascii=False)))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def already_scraped_urls():
    """Return dict {url: updated_at} from DB."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT url, updated_at FROM companies")
    results = {row[0]: row[1] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return results

def get_company(url: str):
    """Fetch company data from DB by URL. Returns dict or None if not found."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT data FROM companies WHERE url = %s LIMIT 1", (url,))
        row = cur.fetchone()
        if row:
            return json.loads(row[0])
        return None
    finally:
        cur.close()
        conn.close()


def get_all_companies():
    """Fetch all companies from DB. Returns list of dicts."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT data FROM companies")
        rows = cur.fetchall()
        return [json.loads(row[0]) for row in rows]
    finally:
        cur.close()
        conn.close()


def get_companies_by_names(company_names: list):
    """Fetch companies from DB by company names. Returns list of dicts."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        results = []
        for name in company_names:
            # Search in the JSON data field for company name
            cur.execute("""
                SELECT data FROM companies 
                WHERE JSON_UNQUOTE(JSON_EXTRACT(data, '$."Company Name"')) = %s
                LIMIT 1
            """, (name,))
            row = cur.fetchone()
            if row:
                results.append(json.loads(row[0]))
        return results
    finally:
        cur.close()
        conn.close()


def get_companies_summary():
    """Fetch all companies with only URL, About, and created_at timestamp, sorted by freshest."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("""
            SELECT 
                url,
                JSON_UNQUOTE(JSON_EXTRACT(data, '$."Company Name"')) as company_name,
                JSON_UNQUOTE(JSON_EXTRACT(data, '$.About')) as about,
                created_at
            FROM companies
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        return rows
    finally:
        cur.close()
        conn.close()


def delete_all_companies():
    """Delete all companies from the database. Returns number of deleted rows."""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("DELETE FROM companies")
        deleted_count = cur.rowcount
        conn.commit()
        return deleted_count
    finally:
        cur.close()
        conn.close()


def delete_company(identifier: str, by: str = "url"):
    """
    Delete a company from the database by URL or name.
    
    Args:
        identifier: The URL or company name to search for
        by: Either "url" or "name" to specify the search field
    
    Returns:
        Number of deleted rows (0 or 1)
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        if by == "url":
            cur.execute("DELETE FROM companies WHERE url = %s", (identifier,))
        elif by == "name":
            cur.execute("""
                DELETE FROM companies 
                WHERE JSON_UNQUOTE(JSON_EXTRACT(data, '$."Company Name"')) = %s
            """, (identifier,))
        else:
            raise ValueError("Invalid 'by' parameter. Must be 'url' or 'name'")
        
        deleted_count = cur.rowcount
        conn.commit()
        return deleted_count
    finally:
        cur.close()
        conn.close()