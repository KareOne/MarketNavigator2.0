#!/usr/bin/env python3
"""
Database utility module for TracXN scraper
Handles MySQL database connections and operations
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG

logger = logging.getLogger(__name__)

def ensure_json_parsed(data):
    """Ensure data is properly parsed as JSON if it's a string"""
    if isinstance(data, str):
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Failed to parse JSON data: {data[:100]}...")
            return data
    return data

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self._connection_params = None
        
    def connect(self) -> bool:
        """Establish connection to MySQL database"""
        try:
            # Store connection parameters for reconnection
            self._connection_params = {
                'host': DB_CONFIG['host'],
                'port': DB_CONFIG['port'],
                'user': DB_CONFIG['user'],
                'password': DB_CONFIG['password'],
                'database': DB_CONFIG['database'],
                'charset': 'utf8mb4',
                'use_unicode': True,
                'autocommit': False,
                'connect_timeout': 10
            }
            
            self.connection = mysql.connector.connect(**self._connection_params)
            if self.connection.is_connected():
                logger.info("Successfully connected to MySQL database")
                return True
        except Error as e:
            logger.error(f"Error connecting to MySQL database: {e}")
            return False
    
    def ensure_connection(self) -> bool:
        """Ensure database connection is alive, reconnect if necessary"""
        try:
            if self.connection is None or not self.connection.is_connected():
                logger.warning("Database connection lost, attempting to reconnect...")
                if self._connection_params:
                    self.connection = mysql.connector.connect(**self._connection_params)
                    if self.connection.is_connected():
                        logger.info("Successfully reconnected to MySQL database")
                        return True
                else:
                    return self.connect()
            else:
                # Ping the connection to ensure it's alive
                try:
                    self.connection.ping(reconnect=True, attempts=3, delay=1)
                    return True
                except Error as e:
                    logger.warning(f"Connection ping failed: {e}, attempting reconnect...")
                    self.connection = mysql.connector.connect(**self._connection_params)
                    return self.connection.is_connected()
        except Error as e:
            logger.error(f"Failed to ensure database connection: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("MySQL connection closed")
    
    def create_tables(self):
        """Create necessary tables if they don't exist"""
        if not self.ensure_connection():
            logger.error("MySQL Connection not available")
            raise Exception("Database connection not available")
            
        cursor = None
        try:
            cursor = self.connection.cursor()
            
            # Create companies table
            create_companies_table = """
            CREATE TABLE IF NOT EXISTS companies (
                company_reference VARCHAR(500) PRIMARY KEY,
                company_data JSON NOT NULL,
                last_updated DATETIME NOT NULL,
                search_query VARCHAR(255),
                INDEX idx_last_updated (last_updated),
                INDEX idx_search_query (search_query)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            cursor.execute(create_companies_table)
            self.connection.commit()
            logger.info("Database tables created/verified successfully")
            
        except Error as e:
            logger.error(f"Error creating tables: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
    
    def is_company_fresh(self, company_reference: str, freshness_days: int = 180) -> bool:
        """Check if company data is fresh (within specified days)"""
        if not self.ensure_connection():
            logger.error("MySQL Connection not available")
            return False
            
        cursor = None
        try:
            cursor = self.connection.cursor()
            
            query = """
            SELECT last_updated FROM companies 
            WHERE company_reference = %s 
            AND last_updated >= %s
            """
            
            freshness_date = datetime.now() - timedelta(days=freshness_days)
            cursor.execute(query, (company_reference, freshness_date))
            result = cursor.fetchone()
            
            return result is not None
            
        except Error as e:
            logger.error(f"Error checking company freshness: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
    
    def get_company_data(self, company_reference: str) -> Optional[Dict[str, Any]]:
        """Retrieve company data from database"""
        if not self.ensure_connection():
            logger.error("MySQL Connection not available")
            return None
            
        cursor = None
        try:
            cursor = self.connection.cursor()
            
            query = """
            SELECT company_data, last_updated FROM companies 
            WHERE company_reference = %s
            """
            
            cursor.execute(query, (company_reference,))
            result = cursor.fetchone()
            
            if result:
                # Ensure data is properly parsed as JSON if it comes as string
                data = ensure_json_parsed(result[0])
                
                return {
                    'data': data,
                    'last_updated': result[1]
                }
            return None
            
        except Error as e:
            logger.error(f"Error retrieving company data: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def save_company_data(self, company_reference: str, data: List[Dict], search_query: str = None):
        """Save or update company data in database"""
        if not self.ensure_connection():
            logger.error("MySQL Connection not available")
            raise Exception("Database connection not available")
        
        # Validate data before saving
        if not data or not isinstance(data, list):
            logger.warning(f"Empty or invalid data provided for company {company_reference}, not saving")
            return
            
        # Check if data has meaningful content
        has_valid_content = False
        for section in data:
            if not isinstance(section, dict):
                continue
            section_data = section.get('data', {})
            if section_data and isinstance(section_data, dict):
                for key, value in section_data.items():
                    if value and str(value).strip() and str(value).strip().lower() not in ['', 'null', 'none', 'not found', 'n/a']:
                        has_valid_content = True
                        break
                if has_valid_content:
                    break
        
        if not has_valid_content:
            logger.warning(f"Company data for {company_reference} appears to be empty or contains no meaningful content, not saving")
            return
            
        cursor = None
        try:
            cursor = self.connection.cursor()
            
            query = """
            INSERT INTO companies (company_reference, company_data, last_updated, search_query)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            company_data = VALUES(company_data),
            last_updated = VALUES(last_updated),
            search_query = VALUES(search_query)
            """
            
            json_data = json.dumps(data, ensure_ascii=False, default=str)
            current_time = datetime.now()
            
            cursor.execute(query, (company_reference, json_data, current_time, search_query))
            self.connection.commit()
            logger.info(f"Company data saved for reference: {company_reference}")
            
        except Error as e:
            logger.error(f"Error saving company data: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
    
    def get_fresh_companies(self, company_references: List[str], freshness_days: int = 180) -> Dict[str, Any]:
        """Get fresh companies from database and return which ones need scraping"""
        fresh_data = {}
        need_scraping = []
        
        for ref in company_references:
            if self.is_company_fresh(ref, freshness_days):
                data = self.get_company_data(ref)
                if data:
                    fresh_data[ref] = data['data']
            else:
                need_scraping.append(ref)
        
        return {
            'fresh_data': fresh_data,
            'need_scraping': need_scraping
        }
    
    def get_all_companies(self) -> List[Dict[str, Any]]:
        """Retrieve all companies from database"""
        if not self.ensure_connection():
            logger.error("MySQL Connection not available")
            return []
            
        cursor = None
        try:
            cursor = self.connection.cursor()
            
            query = """
            SELECT company_reference, company_data, last_updated, search_query
            FROM companies
            ORDER BY last_updated DESC
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            
            companies = []
            for row in results:
                # Ensure data is properly parsed as JSON if it comes as string
                data = ensure_json_parsed(row[1])
                
                companies.append({
                    'company_reference': row[0],
                    'company_data': data,
                    'last_updated': row[2],
                    'search_query': row[3]
                })
            
            return companies
            
        except Error as e:
            logger.error(f"Error retrieving all companies: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
    
    def export_all_to_json(self, output_dir: str = "exported_companies"):
        """Export all company data to JSON files"""
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            companies = self.get_all_companies()
            
            for company in companies:
                # Clean company reference for filename (remove invalid characters)
                safe_filename = "".join(c for c in company['company_reference'] if c.isalnum() or c in ('-', '_', '.')).rstrip()
                if not safe_filename:
                    safe_filename = f"company_{hash(company['company_reference'])}"
                
                filename = f"{safe_filename}.json"
                filepath = os.path.join(output_dir, filename)
                
                export_data = {
                    'company_reference': company['company_reference'],
                    'last_updated': company['last_updated'].isoformat() if company['last_updated'] else None,
                    'search_query': company['search_query'],
                    'data': company['company_data']
                }
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"Exported {len(companies)} companies to {output_dir}")
            return len(companies)
            
        except Exception as e:
            logger.error(f"Error exporting companies to JSON: {e}")
            raise

def test_database_connection():
    """Test database connection and create tables"""
    db = DatabaseManager()
    try:
        if db.connect():
            print("✅ Database connection successful!")
            db.create_tables()
            print("✅ Tables created/verified successfully!")
            return True
        else:
            print("❌ Database connection failed!")
            return False
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False
    finally:
        db.disconnect()

if __name__ == "__main__":
    # Test the database connection
    test_database_connection()