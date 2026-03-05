#!/usr/bin/env python3
"""Quick test to verify database loads correctly."""
import os
import sys

os.chdir('/Users/pndagiji/Documents/Full-time/SoftwareDev/software_work/general_code/data-explorer')

try:
    print(f"Database file exists: {os.path.exists('data/bidshub.db')}")
    
    from src.database import Database
    print("Database module imported successfully")
    
    db = Database('data/bidshub.db')
    print("Database object created successfully")
    
    setup_status = db.get_metadata('setup_complete')
    print(f"setup_complete value: {setup_status}")
    print(f"setup_complete == 'true': {setup_status == 'true'}")
    
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("All checks passed!")
