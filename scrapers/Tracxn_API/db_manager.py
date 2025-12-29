#!/usr/bin/env python3
"""
Database management utility for TracXN scraper
Provides command-line interface for database operations
"""

import argparse
import sys
import json
from datetime import datetime
from database import DatabaseManager, test_database_connection

def check_connection():
    """Test database connection"""
    print("Testing database connection...")
    success = test_database_connection()
    if success:
        print("✅ Database connection test passed!")
        return True
    else:
        print("❌ Database connection test failed!")
        return False

def export_all_data(output_dir="exported_companies"):
    """Export all company data to JSON files"""
    print(f"Exporting all company data to '{output_dir}' directory...")
    
    db = DatabaseManager()
    try:
        if not db.connect():
            print("❌ Failed to connect to database")
            return False
        
        exported_count = db.export_all_to_json(output_dir)
        print(f"✅ Successfully exported {exported_count} companies to '{output_dir}'")
        return True
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False
    finally:
        db.disconnect()

def list_companies():
    """List all companies in database"""
    print("Retrieving all companies from database...")
    
    db = DatabaseManager()
    try:
        if not db.connect():
            print("❌ Failed to connect to database")
            return False
        
        companies = db.get_all_companies()
        
        if not companies:
            print("No companies found in database")
            return True
        
        print(f"\nFound {len(companies)} companies:")
        print("-" * 80)
        
        for i, company in enumerate(companies, 1):
            print(f"{i}. Reference: {company['company_reference']}")
            print(f"   Last Updated: {company['last_updated']}")
            print(f"   Search Query: {company['search_query'] or 'N/A'}")
            print(f"   Data Sections: {len(company['company_data']) if company['company_data'] else 0}")
            print("-" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to list companies: {e}")
        return False
    finally:
        db.disconnect()

def get_company_details(company_reference):
    """Get detailed information about a specific company"""
    print(f"Retrieving details for company: {company_reference}")
    
    db = DatabaseManager()
    try:
        if not db.connect():
            print("❌ Failed to connect to database")
            return False
        
        company_data = db.get_company_data(company_reference)
        
        if not company_data:
            print(f"❌ Company with reference '{company_reference}' not found")
            return False
        
        print(f"\n✅ Company found:")
        print(f"Reference: {company_reference}")
        print(f"Last Updated: {company_data['last_updated']}")
        print(f"Data Sections: {len(company_data['data']) if company_data['data'] else 0}")
        
        if company_data['data']:
            print("\nAvailable sections:")
            for section in company_data['data']:
                if isinstance(section, dict) and 'section' in section:
                    print(f"  - {section['section']}")
        
        # Ask if user wants to see full data
        show_full = input("\nShow full company data? (y/N): ").lower().strip()
        if show_full == 'y':
            print("\nFull Company Data:")
            print(json.dumps(company_data['data'], indent=2, ensure_ascii=False, default=str))
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to get company details: {e}")
        return False
    finally:
        db.disconnect()

def clean_old_data(days=30):
    """Clean old company data (older than specified days)"""
    print(f"This feature would clean data older than {days} days")
    print("⚠️  This feature is not yet implemented for safety reasons")
    print("To manually clean data, use your MySQL client to delete from companies table")
    return True

def main():
    parser = argparse.ArgumentParser(
        description="TracXN Database Management Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python db_manager.py --check              # Test database connection
  python db_manager.py --list               # List all companies
  python db_manager.py --export             # Export all data to JSON files
  python db_manager.py --export --output my_export  # Export to custom directory
  python db_manager.py --company "/company/abc123"  # Get specific company details
        """
    )
    
    parser.add_argument('--check', action='store_true', 
                       help='Test database connection')
    parser.add_argument('--list', action='store_true',
                       help='List all companies in database')
    parser.add_argument('--export', action='store_true',
                       help='Export all company data to JSON files')
    parser.add_argument('--output', type=str, default='exported_companies',
                       help='Output directory for export (default: exported_companies)')
    parser.add_argument('--company', type=str,
                       help='Get details for specific company by reference')
    parser.add_argument('--clean', type=int, metavar='DAYS',
                       help='Clean data older than DAYS (not implemented yet)')
    
    args = parser.parse_args()
    
    # If no arguments provided, show help
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    success = True
    
    try:
        if args.check:
            success = check_connection() and success
        
        if args.list:
            success = list_companies() and success
        
        if args.export:
            success = export_all_data(args.output) and success
        
        if args.company:
            success = get_company_details(args.company) and success
        
        if args.clean:
            success = clean_old_data(args.clean) and success
        
        if success:
            print("\n✅ All operations completed successfully!")
        else:
            print("\n❌ Some operations failed. Check the output above.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()