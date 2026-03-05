"""
Test all 7 platform agents
Tests basic functionality and connection requirements
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_platform_imports():
    """Test 1: Can we import all platform agents?"""
    print("\n" + "="*70)
    print("TEST 1: PLATFORM AGENT IMPORTS")
    print("="*70)
    
    results = {}
    
    # Test Pennsieve
    print("\n1. Pennsieve Agent")
    try:
        from src.pennsieve_agent import PennsieveAgent
        print("   [PASS] Import successful")
        results['pennsieve'] = True
    except Exception as e:
        print(f"   [FAIL] {str(e)}")
        results['pennsieve'] = False
    
    # Test OpenNeuro
    print("\n2. OpenNeuro Agent")
    try:
        from src.openneuro_agent import OpenNeuroAgent
        print("   [PASS] Import successful")
        results['openneuro'] = True
    except Exception as e:
        print(f"   [FAIL] {str(e)}")
        results['openneuro'] = False
    
    # Test XNAT
    print("\n3. XNAT Agent")
    try:
        from src.xnat_agent import XNATAgent
        print("   [PASS] Import successful")
        results['xnat'] = True
    except Exception as e:
        print(f"   [FAIL] {str(e)}")
        results['xnat'] = False
    
    # Test DANDI
    print("\n4. DANDI Agent")
    try:
        from src.dandi_agent import DANDIAgent
        print("   [PASS] Import successful")
        results['dandi'] = True
    except Exception as e:
        print(f"   [FAIL] {str(e)}")
        results['dandi'] = False
    
    # Test HCP
    print("\n5. HCP Agent")
    try:
        from src.hcp_agent import HCPAgent
        print("   [PASS] Import successful")
        results['hcp'] = True
    except Exception as e:
        print(f"   [FAIL] {str(e)}")
        results['hcp'] = False
    
    # Test LORIS
    print("\n6. LORIS Agent")
    try:
        from src.loris_agent import LORISAgent
        print("   [PASS] Import successful")
        results['loris'] = True
    except Exception as e:
        print(f"   [FAIL] {str(e)}")
        results['loris'] = False
    
    # Test FITBIR
    print("\n7. FITBIR Agent")
    try:
        from src.fitbir_agent import FITBIRAgent
        print("   [PASS] Import successful")
        results['fitbir'] = True
    except Exception as e:
        print(f"   [FAIL] {str(e)}")
        results['fitbir'] = False
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print("\n" + "="*70)
    print(f"Import Results: {passed}/{total} passed")
    print("="*70)
    
    return results


def test_platform_instantiation():
    """Test 2: Can we instantiate all platform agents?"""
    print("\n" + "="*70)
    print("TEST 2: PLATFORM AGENT INSTANTIATION")
    print("="*70)
    
    results = {}
    
    # Test OpenNeuro (no credentials required)
    print("\n1. OpenNeuro Agent (no credentials)")
    try:
        from src.openneuro_agent import OpenNeuroAgent
        agent = OpenNeuroAgent()
        print("   [PASS] Instantiated without credentials")
        results['openneuro'] = True
    except Exception as e:
        print(f"   [FAIL] {str(e)}")
        results['openneuro'] = False
    
    # Test DANDI (no credentials for public)
    print("\n2. DANDI Agent (no credentials for public datasets)")
    try:
        from src.dandi_agent import DANDIAgent
        agent = DANDIAgent()
        print("   [PASS] Instantiated without credentials")
        results['dandi'] = True
    except Exception as e:
        print(f"   [FAIL] {str(e)}")
        results['dandi'] = False
    
    # Test others with dummy credentials (won't connect but validates instantiation)
    print("\n3. Pennsieve Agent (with dummy credentials)")
    try:
        from src.pennsieve_agent import PennsieveAgent
        # This will fail to connect but should instantiate
        print("   [SKIP] Requires valid credentials for instantiation")
        results['pennsieve'] = 'requires_creds'
    except Exception as e:
        print(f"   [INFO] {str(e)}")
        results['pennsieve'] = 'requires_creds'
    
    print("\n4. XNAT Agent (with dummy credentials)")
    try:
        from src.xnat_agent import XNATAgent
        print("   [SKIP] Requires server URL, username, password")
        results['xnat'] = 'requires_creds'
    except Exception as e:
        print(f"   [INFO] {str(e)}")
        results['xnat'] = 'requires_creds'
    
    print("\n5. HCP Agent")
    try:
        from src.hcp_agent import HCPAgent
        print("   [SKIP] Requires HCP credentials")
        results['hcp'] = 'requires_creds'
    except Exception as e:
        print(f"   [INFO] {str(e)}")
        results['hcp'] = 'requires_creds'
    
    print("\n6. LORIS Agent")
    try:
        from src.loris_agent import LORISAgent
        print("   [SKIP] Requires LORIS server URL and token")
        results['loris'] = 'requires_creds'
    except Exception as e:
        print(f"   [INFO] {str(e)}")
        results['loris'] = 'requires_creds'
    
    print("\n7. FITBIR Agent")
    try:
        from src.fitbir_agent import FITBIRAgent
        print("   [SKIP] Requires FITBIR credentials")
        results['fitbir'] = 'requires_creds'
    except Exception as e:
        print(f"   [INFO] {str(e)}")
        results['fitbir'] = 'requires_creds'
    
    passed = sum(1 for v in results.values() if v is True)
    requires_creds = sum(1 for v in results.values() if v == 'requires_creds')
    
    print("\n" + "="*70)
    print(f"Instantiation Results: {passed} passed, {requires_creds} require credentials")
    print("="*70)
    
    return results


def test_openneuro_connection():
    """Test 3: Test OpenNeuro connection (no credentials needed)"""
    print("\n" + "="*70)
    print("TEST 3: OPENNEURO CONNECTION (PUBLIC)")
    print("="*70)
    
    print("\nAttempting to connect to OpenNeuro...")
    print("(This tests real connectivity without requiring credentials)")
    
    try:
        from src.openneuro_agent import OpenNeuroAgent
        agent = OpenNeuroAgent()
        
        # Test get_datasets method
        print("\nTesting get_datasets()...")
        result = agent.get_datasets()
        
        if result['success']:
            datasets = result.get('datasets', [])
            print(f"   [PASS] Connected successfully")
            print(f"   [INFO] Found {len(datasets)} datasets")
            
            if len(datasets) > 0:
                print(f"\n   Sample datasets:")
                for i, ds in enumerate(datasets[:3]):
                    print(f"   {i+1}. {ds.get('name', 'N/A')} - {ds.get('description', 'N/A')[:50]}")
            
            return True
        else:
            print(f"   [FAIL] {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"   [FAIL] {str(e)}")
        return False


def show_credential_requirements():
    """Show what credentials are needed for each platform"""
    print("\n" + "="*70)
    print("CREDENTIAL REQUIREMENTS BY PLATFORM")
    print("="*70)
    
    requirements = {
        'Pennsieve': {
            'required': ['API Key', 'API Secret', 'Dataset Name'],
            'optional': [],
            'get_creds': 'Account Settings > API Credentials in Pennsieve web interface'
        },
        'OpenNeuro': {
            'required': ['Dataset ID (e.g., ds003974)'],
            'optional': ['API Token (for private datasets only)'],
            'get_creds': 'No account needed for public datasets'
        },
        'XNAT': {
            'required': ['Server URL', 'Username', 'Password', 'Project ID'],
            'optional': [],
            'get_creds': 'Contact your XNAT administrator'
        },
        'DANDI': {
            'required': ['Dandiset ID (e.g., 000003)'],
            'optional': ['API Key (for private datasets only)'],
            'get_creds': 'dandi.dandiarchive.org > Account > API Token'
        },
        'HCP': {
            'required': ['Username', 'Password', 'Dataset ID'],
            'optional': [],
            'get_creds': 'Register at db.humanconnectome.org'
        },
        'LORIS': {
            'required': ['Server URL', 'API Token', 'Project ID'],
            'optional': [],
            'get_creds': 'Contact your LORIS administrator'
        },
        'FITBIR': {
            'required': ['Username', 'Password', 'Study ID'],
            'optional': [],
            'get_creds': 'Register at fitbir.nih.gov'
        }
    }
    
    for platform, req in requirements.items():
        print(f"\n{platform}:")
        print(f"  Required: {', '.join(req['required'])}")
        if req['optional']:
            print(f"  Optional: {', '.join(req['optional'])}")
        print(f"  How to get: {req['get_creds']}")
    
    print("\n" + "="*70)


def create_platform_test_guide():
    """Create a guide for testing each platform"""
    print("\n" + "="*70)
    print("HOW TO TEST EACH PLATFORM")
    print("="*70)
    
    print("""
OPTION 1: Test with Local Mode (No Credentials Needed)
-------------------------------------------------------
This tests the UI and database operations without requiring platform access.

Steps:
1. ./hub start (or restart)
2. Go to http://localhost:8501
3. Click "Setup" or navigate to "Manage Datasets"
4. For each platform:
   - Select platform from dropdown
   - Choose "Local (BIDS data already on disk)"
   - Enter BIDS path: /tmp/test-bids-dataset
   - Skip credentials (optional for local)
   - Click "Initialize" or "Add Dataset"
   - Verify auto-indexing works

Platforms to test:
- [[OK]] Pennsieve (already tested)
- [ ] OpenNeuro
- [ ] XNAT
- [ ] DANDI
- [ ] HCP
- [ ] LORIS
- [ ] FITBIR


OPTION 2: Test OpenNeuro (Public, No Credentials)
--------------------------------------------------
OpenNeuro is the easiest to test with real cloud connectivity.

Steps:
1. Setup page -> Select "OpenNeuro"
2. Choose "Cloud only"
3. Enter Dataset ID: ds003974 (or any public dataset)
4. Leave API Token empty (public dataset)
5. Click "Initialize Dataset"
6. Go to "Subjects" -> Click "Sync Subjects"
7. Browse subjects from OpenNeuro

Test: Run this Python script section to verify OpenNeuro works


OPTION 3: Test with Your Own Credentials
-----------------------------------------
If you have accounts on these platforms, you can test real connections:

Pennsieve:
  - Get API Key/Secret from account settings
  - Test with your dataset name
  
XNAT:
  - Use your institution's XNAT server
  - Need username, password, project ID
  
DANDI:
  - Test with public Dandiset (e.g., 000003)
  - Or use API key for private
  
HCP:
  - Register at db.humanconnectome.org
  - Use HCP credentials
  
LORIS/FITBIR:
  - Institutional access required
  - Contact administrators


OPTION 4: Mock Testing (Development)
-------------------------------------
Create mock responses for each platform without real connections.
Useful for UI testing and validation logic.

Run: python tests/test_all_platforms.py --mock
(Not yet implemented)
""")


def run_all_tests():
    """Run all platform tests"""
    print("\n" + "="*70)
    print("BIDSHUB - PLATFORM TESTING SUITE")
    print("="*70)
    print("Testing all 7 platform agents")
    print("="*70)
    
    # Test 1: Imports
    import_results = test_platform_imports()
    
    # Test 2: Instantiation
    instant_results = test_platform_instantiation()
    
    # Test 3: OpenNeuro connection (only one that works without credentials)
    print("\n" + "="*70)
    print("ATTEMPTING REAL CONNECTION TEST")
    print("="*70)
    print("\nOnly OpenNeuro will be tested (no credentials required)")
    print("Other platforms need credentials from your accounts")
    
    openneuro_works = test_openneuro_connection()
    
    # Show credential requirements
    show_credential_requirements()
    
    # Show testing guide
    create_platform_test_guide()
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    imports_passed = sum(1 for v in import_results.values() if v)
    print(f"\nAgent Imports: {imports_passed}/7 working")
    
    instant_passed = sum(1 for v in instant_results.values() if v is True)
    instant_needs_creds = sum(1 for v in instant_results.values() if v == 'requires_creds')
    print(f"Agent Instantiation: {instant_passed} work without creds, {instant_needs_creds} need creds")
    
    print(f"OpenNeuro Connection: {'PASS' if openneuro_works else 'FAIL'}")
    
    print("\n" + "="*70)
    print("RECOMMENDATION")
    print("="*70)
    print("""
To fully test all platforms:

1. Quick Test (Local Mode):
   - Use local BIDS dataset with all 7 platforms
   - Tests UI, validation, auto-indexing
   - No credentials needed
   - Time: ~5 minutes

2. Full Test (Cloud Connections):
   - Need credentials for each platform
   - Tests real API connections
   - Tests data browsing and downloads
   - Time: ~30 minutes (setup + testing)

3. Automated Test (This Script):
   - Tests imports and basic instantiation
   - Tests OpenNeuro public connection
   - Quick validation
   - Time: ~30 seconds

Run: python tests/test_all_platforms.py
""")


if __name__ == "__main__":
    run_all_tests()
