#!/usr/bin/env python3
"""
Data Explorer Launch Script
Automatically finds available port between 8500-8550 and launches Streamlit
"""

import socket
import sys
import subprocess
import os


# Configuration
MIN_PORT = 8500
MAX_PORT = 8550
DEFAULT_PORT = 8501


def is_port_available(port: int) -> bool:
    """Check if a port is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', port))
            return True
    except OSError:
        return False


def find_available_port(start_port: int = DEFAULT_PORT) -> int:
    """Find an available port in the specified range."""
    # Try default port first
    if is_port_available(start_port):
        return start_port
    
    # Try other ports in range
    for port in range(MIN_PORT, MAX_PORT + 1):
        if port == start_port:
            continue  # Already tried
        if is_port_available(port):
            return port
    
    return None


def main():
    """Main launcher function."""
    print("=" * 60)
    print("           Data Explorer Launch Script")
    print("=" * 60)
    print()
    
    # Check if streamlit is available
    try:
        import streamlit
        print(f"✓ Streamlit {streamlit.__version__} found")
    except ImportError:
        print("✗ Streamlit not installed")
        print("  Run: pip install -r requirements.txt")
        sys.exit(1)
    
    # Find available port
    print(f"\nSearching for available port in range {MIN_PORT}-{MAX_PORT}...")
    port = find_available_port()
    
    if port is None:
        print(f"\n✗ No available ports in range {MIN_PORT}-{MAX_PORT}")
        print("  Please close some applications and try again")
        sys.exit(1)
    
    print(f"✓ Found available port: {port}")
    print()
    
    # Launch Streamlit
    print("-" * 60)
    print(f"🚀 Launching Data Explorer on port {port}...")
    print("-" * 60)
    print()
    print(f"  Local URL:   http://localhost:{port}")
    print()
    print("Press Ctrl+C to stop the server")
    print()
    print("=" * 60)
    print()
    
    # Build command
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.port",
        str(port),
        "--server.headless",
        "false"
    ]
    
    # Launch
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n\n✓ Data Explorer stopped")
        print("Thank you for using Data Explorer!")


if __name__ == "__main__":
    main()
