#!/usr/bin/env python3
"""
BIDSHub CLI - Cross-platform command-line interface
Works on macOS, Linux, and Windows

Usage: ./hub <command> [options]
"""

import os
import sys
import subprocess
import signal
import time
import shutil
import platform
from pathlib import Path


# Configuration
APP_NAME = "BIDSHub"
VENV_DIR = "venv"
LOG_DIR = "logs"
PID_FILE = ".explorer.pid"
PORT_FILE = ".explorer.port"

# Colors (ANSI escape codes work on all platforms with modern terminals)
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color
    
    @staticmethod
    def supports_color():
        """Check if terminal supports color."""
        return (
            hasattr(sys.stdout, 'isatty') and sys.stdout.isatty() and
            (platform.system() != 'Windows' or 'ANSICON' in os.environ or
             'WT_SESSION' in os.environ or 'TERM_PROGRAM' in os.environ)
        )


# Helper functions
def print_header(text):
    """Print formatted header."""
    if Colors.supports_color():
        print(f"{Colors.BLUE}{'=' * 60}{Colors.NC}")
        print(f"{Colors.BLUE}  {text}{Colors.NC}")
        print(f"{Colors.BLUE}{'=' * 60}{Colors.NC}")
    else:
        print("=" * 60)
        print(f"  {text}")
        print("=" * 60)


def print_success(text):
    """Print success message."""
    color = Colors.GREEN if Colors.supports_color() else ""
    nc = Colors.NC if Colors.supports_color() else ""
    print(f"{color}[OK]{nc} {text}")


def print_error(text):
    """Print error message."""
    color = Colors.RED if Colors.supports_color() else ""
    nc = Colors.NC if Colors.supports_color() else ""
    print(f"{color}[ERROR]{nc} {text}")


def print_warning(text):
    """Print warning message."""
    color = Colors.YELLOW if Colors.supports_color() else ""
    nc = Colors.NC if Colors.supports_color() else ""
    print(f"{color}[WARN]{nc} {text}")


def print_info(text):
    """Print info message."""
    color = Colors.CYAN if Colors.supports_color() else ""
    nc = Colors.NC if Colors.supports_color() else ""
    print(f"{color}[INFO]{nc} {text}")


def get_python_executable():
    """Get the appropriate Python executable."""
    return sys.executable


def get_venv_python():
    """Get path to Python in virtual environment."""
    if platform.system() == "Windows":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        return os.path.join(VENV_DIR, "bin", "python")


def get_venv_pip():
    """Get path to pip in virtual environment."""
    if platform.system() == "Windows":
        return os.path.join(VENV_DIR, "Scripts", "pip.exe")
    else:
        return os.path.join(VENV_DIR, "bin", "pip")


def is_process_running(pid):
    """Check if a process is running."""
    try:
        if platform.system() == "Windows":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(1, 0, pid)
            if handle == 0:
                return False
            kernel32.CloseHandle(handle)
            return True
        else:
            os.kill(pid, 0)
            return True
    except (OSError, AttributeError):
        return False


def get_process_info(pid):
    """Get CPU and memory usage of a process."""
    try:
        import psutil
        process = psutil.Process(pid)
        return {
            'cpu': process.cpu_percent(interval=0.1),
            'memory': process.memory_percent()
        }
    except ImportError:
        return {'cpu': 'N/A', 'memory': 'N/A'}
    except:
        return {'cpu': 'N/A', 'memory': 'N/A'}


def find_available_port(start_port=8501):
    """Find an available port in the range 8500-8550."""
    import socket
    
    # Try default port first
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', start_port))
            return start_port
    except OSError:
        pass
    
    # Try other ports in range
    for port in range(8500, 8551):
        if port == start_port:
            continue
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    
    return None


def detect_streamlit_port():
    """Detect port of running Streamlit process."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ['netstat', '-ano', '|', 'findstr', ':850'],
                capture_output=True, text=True, shell=True
            )
        else:
            result = subprocess.run(
                ['lsof', '-i', '-P', '-n'],
                capture_output=True, text=True
            )
            
        # Parse output to find Streamlit port
        for line in result.stdout.split('\n'):
            if 'streamlit' in line.lower() and 'LISTEN' in line:
                parts = line.split()
                for part in parts:
                    if ':' in part and '850' in part:
                        port = part.split(':')[-1]
                        try:
                            return int(port)
                        except:
                            continue
    except:
        pass
    
    return None


# Command: install
def cmd_install():
    """Install dependencies and initialize database."""
    print_header(f"Installing {APP_NAME}")
    print()
    
    # Check Python
    python_exe = get_python_executable()
    print_success(f"Python found: {sys.version.split()[0]}")
    
    # Create virtual environment
    if not os.path.exists(VENV_DIR):
        print_info("Creating virtual environment...")
        subprocess.run([python_exe, "-m", "venv", VENV_DIR], check=True)
        print_success("Virtual environment created")
    else:
        print_warning("Virtual environment already exists")
    
    # Get venv executables
    venv_python = get_venv_python()
    venv_pip = get_venv_pip()
    
    # Upgrade pip
    print_info("Upgrading pip...")
    subprocess.run(
        [venv_python, "-m", "pip", "install", "--upgrade", "pip"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print_success("pip upgraded")
    
    # Install dependencies
    print_info("Installing dependencies...")
    subprocess.run(
        [venv_pip, "install", "-r", "requirements.txt"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print_success("Dependencies installed")
    
    # Initialize database
    print_info("Initializing database...")
    subprocess.run([venv_python, "scripts/init_db.py"], check=True)
    print_success("Database initialized")
    
    # Create logs directory
    os.makedirs(LOG_DIR, exist_ok=True)
    
    print()
    print_success("Installation complete!")
    print_info("Run './explorer start' to launch the application")


# Command: start
def cmd_start():
    """Start the application."""
    print_header(f"Starting {APP_NAME}")
    print()
    
    # Check if already running
    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        if is_process_running(pid):
            port = "unknown"
            if os.path.exists(PORT_FILE):
                with open(PORT_FILE, 'r') as f:
                    port = f.read().strip()
            print_warning(f"Already running (PID: {pid}, Port: {port})")
            print_info(f"URL: http://localhost:{port}")
            return
        else:
            # Stale PID file
            os.remove(PID_FILE)
            if os.path.exists(PORT_FILE):
                os.remove(PORT_FILE)
    
    # Check virtual environment
    if not os.path.exists(VENV_DIR):
        print_error("Virtual environment not found")
        print_info("Run './hub install' first")
        sys.exit(1)
    
    # Start application
    print_info("Launching application...")
    venv_python = get_venv_python()
    
    # Find available port
    port = find_available_port()
    if port is None:
        print_error("No available ports in range 8500-8550")
        sys.exit(1)
    
    # Launch Streamlit directly (not via launch.py wrapper)
    if platform.system() == "Windows":
        # Windows: use subprocess with DETACHED_PROCESS
        process = subprocess.Popen(
            [venv_python, "-m", "streamlit", "run", "app.py",
             "--server.port", str(port),
             "--server.headless", "true"],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    else:
        # Unix: use subprocess with new process group
        process = subprocess.Popen(
            [venv_python, "-m", "streamlit", "run", "app.py",
             "--server.port", str(port),
             "--server.headless", "true"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp
        )
    
    # Save the actual Streamlit PID
    with open(PID_FILE, 'w') as f:
        f.write(str(process.pid))
    
    # Save the port
    with open(PORT_FILE, 'w') as f:
        f.write(str(port))
    
    # Wait a moment for Streamlit to start
    time.sleep(2)
    
    print_success(f"Started on port {port}")
    print_info(f"PID: {process.pid}")
    print_info(f"URL: http://localhost:{port}")
    print_info("Run './hub status' to check status")


# Command: stop
def cmd_stop():
    """Stop the application."""
    print_header(f"Stopping {APP_NAME}")
    print()
    
    stopped = False
    
    # Try PID file first
    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        if is_process_running(pid):
            print_info(f"Stopping process {pid}...")
            try:
                if platform.system() == "Windows":
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], 
                                 stdout=subprocess.DEVNULL, 
                                 stderr=subprocess.DEVNULL)
                else:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(1)
                    if is_process_running(pid):
                        os.kill(pid, signal.SIGKILL)
                stopped = True
                print_success("Stopped")
            except Exception as e:
                print_error(f"Failed to stop: {e}")
        else:
            print_warning("Not running (stale PID file)")
        
        os.remove(PID_FILE)
        if os.path.exists(PORT_FILE):
            os.remove(PORT_FILE)
    
    # Try to find streamlit processes
    if not stopped:
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq python.exe"],
                    capture_output=True,
                    text=True
                )
                if "python.exe" in result.stdout:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq streamlit*"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    print_success("Stopped")
                else:
                    print_warning("Not running")
            else:
                result = subprocess.run(
                    ["pgrep", "-f", "streamlit run app.py"],
                    capture_output=True,
                    text=True
                )
                if result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                        except:
                            pass
                    print_success("Stopped")
                else:
                    print_warning("Not running")
        except Exception as e:
            print_warning("Not running")


# Command: restart
def cmd_restart():
    """Restart the application."""
    print_header(f"Restarting {APP_NAME}")
    print()
    
    cmd_stop()
    print()
    time.sleep(1)
    cmd_start()


# Command: status
def cmd_status():
    """Check application status."""
    print_header(f"{APP_NAME} Status")
    print()
    
    # Check if running
    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        if is_process_running(pid):
            port = "unknown"
            if os.path.exists(PORT_FILE):
                with open(PORT_FILE, 'r') as f:
                    port = f.read().strip()
            else:
                # Try to detect port
                detected_port = detect_streamlit_port()
                if detected_port:
                    port = str(detected_port)
                    # Save for future reference
                    with open(PORT_FILE, 'w') as f:
                        f.write(str(port))
            
            print_success("Running")
            print(f"  PID:  {pid}")
            print(f"  Port: {port}")
            print(f"  URL:  http://localhost:{port}")
            
            # Show resource usage
            info = get_process_info(pid)
            print(f"  CPU:  {info['cpu']}%")
            print(f"  MEM:  {info['memory']}%")
        else:
            print_error("Not running (stale PID file)")
            os.remove(PID_FILE)
            if os.path.exists(PORT_FILE):
                os.remove(PORT_FILE)
    else:
        # No PID file - try to detect running Streamlit anyway
        print_error("Not running")
        
        # Try to find orphaned Streamlit processes
        port = detect_streamlit_port()
        if port:
            print_warning("Found orphaned Streamlit process")
            print_info(f"Port: {port}")
            print_info(f"URL: http://localhost:{port}")
            print_info("Run './explorer stop' to clean up")
    
    print()
    
    # Virtual environment status
    if os.path.exists(VENV_DIR):
        print_success("Virtual environment: installed")
    else:
        print_error("Virtual environment: not found")
    
    # Database status
    db_path = Path("data/bidshub.db")
    if db_path.exists():
        size = db_path.stat().st_size
        size_str = f"{size / 1024:.0f}K" if size < 1024 * 1024 else f"{size / (1024*1024):.1f}M"
        print_success(f"Database: {size_str}")
    else:
        print_warning("Database: not initialized (will auto-create on first launch)")


# Command: logs
def cmd_logs():
    """View application logs."""
    print_header(f"{APP_NAME} Logs")
    print()
    
    # Streamlit logs location
    if platform.system() == "Windows":
        streamlit_log_dir = Path(os.environ.get("USERPROFILE")) / ".streamlit" / "logs"
    else:
        streamlit_log_dir = Path.home() / ".streamlit" / "logs"
    
    if streamlit_log_dir.exists():
        log_files = sorted(streamlit_log_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
        if log_files:
            latest_log = log_files[0]
            print_info(f"Showing logs from: {latest_log.name}")
            print_info("Press Ctrl+C to exit")
            print()
            
            # Tail the file
            try:
                with open(latest_log, 'r') as f:
                    # Show last 50 lines
                    lines = f.readlines()
                    for line in lines[-50:]:
                        print(line, end='')
                    
                    # Follow the file
                    while True:
                        line = f.readline()
                        if line:
                            print(line, end='')
                        else:
                            time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n")
                print_info("Stopped viewing logs")
        else:
            print_warning("No logs found")
    else:
        print_warning("Streamlit logs directory not found")
        print_info("Start the application first")


# Command: update
def cmd_update():
    """Update application."""
    print_header(f"Updating {APP_NAME}")
    print()
    
    # Check if git repo
    if not os.path.exists(".git"):
        print_error("Not a git repository")
        sys.exit(1)
    
    # Pull latest code
    print_info("Pulling latest code...")
    subprocess.run(["git", "pull", "origin", "main"], check=True)
    print_success("Code updated")
    
    # Update dependencies
    if os.path.exists(VENV_DIR):
        venv_pip = get_venv_pip()
        print_info("Updating dependencies...")
        subprocess.run(
            [venv_pip, "install", "--upgrade", "-r", "requirements.txt"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print_success("Dependencies updated")
    else:
        print_warning("Virtual environment not found")
        print_info("Run './hub install' first")
    
    print()
    print_success("Update complete!")
    print_info("Run './explorer restart' to apply changes")


# Command: test
def cmd_test():
    """Run tests."""
    print_header("Running Tests")
    print()
    
    if not os.path.exists(VENV_DIR):
        print_error("Virtual environment not found")
        sys.exit(1)
    
    venv_python = get_venv_python()
    
    # Test database
    print_info("Testing database...")
    result = subprocess.run(
        [venv_python, "scripts/init_db.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    if result.returncode == 0:
        print_success("Database: OK")
    else:
        print_error("Database: FAILED")
    
    # Test imports
    print_info("Testing imports...")
    result = subprocess.run(
        [venv_python, "-c", 
         "import streamlit; import bids; import pennsieve; import pandas; import plotly"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    if result.returncode == 0:
        print_success("Dependencies: OK")
    else:
        print_error("Dependencies: FAILED")
    
    # Test modules
    print_info("Testing modules...")
    result = subprocess.run(
        [venv_python, "-c",
         "from src import database, bids_loader, pennsieve_client, theme, utils"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    if result.returncode == 0:
        print_success("Modules: OK")
    else:
        print_error("Modules: FAILED")
    
    print()
    print_success("All tests passed!")


# Command: clean
def cmd_clean():
    """Clean installation."""
    print_header(f"Cleaning {APP_NAME}")
    print()
    
    print_warning("This will remove:")
    print("  - Virtual environment")
    print("  - Database")
    print("  - Logs")
    print("  - Cache files")
    print()
    
    response = input("Are you sure? (y/N): ")
    if response.lower() != 'y':
        print_info("Cancelled")
        return
    
    # Stop if running
    cmd_stop()
    
    # Remove virtual environment
    if os.path.exists(VENV_DIR):
        print_info("Removing virtual environment...")
        shutil.rmtree(VENV_DIR)
        print_success("Virtual environment removed")
    
    # Remove database
    if os.path.exists("data/bidshub.db"):
        print_info("Removing database...")
        os.remove("data/bidshub.db")
        print_success("Database removed")
    
    # Also remove backup files
    import glob
    for backup in glob.glob("data/bidshub.db.backup_*"):
        os.remove(backup)
        print_info(f"Removed backup: {Path(backup).name}")
    
    # Remove logs
    if os.path.exists(LOG_DIR):
        print_info("Removing logs...")
        shutil.rmtree(LOG_DIR)
        print_success("Logs removed")
    
    # Remove Python cache
    print_info("Removing cache files...")
    for root, dirs, files in os.walk("."):
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d))
        for f in files:
            if f.endswith(".pyc"):
                os.remove(os.path.join(root, f))
    print_success("Cache removed")
    
    # Remove PID files
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    if os.path.exists(PORT_FILE):
        os.remove(PORT_FILE)
    
    print()
    print_success("Cleanup complete!")
    print_info("Run './explorer install' to reinstall")


# Command: config
def cmd_config():
    """Show configuration."""
    print_header(f"{APP_NAME} Configuration")
    print()
    
    if os.path.exists(".env"):
        print_success("Configuration file: .env")
        print()
        with open(".env", 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    print(line)
    else:
        print_warning("No .env file found")
        print_info("Create from template: cp .env.example .env")


# Command: help
def cmd_help():
    """Show help message."""
    print_header(f"{APP_NAME} CLI")
    print()
    print("Usage: ./hub <command>")
    print()
    print("Commands:")
    print("  install   Install dependencies and initialize database")
    print("  start     Start the application")
    print("  stop      Stop the application")
    print("  restart   Restart the application")
    print("  status    Check application status")
    print("  logs      View application logs (live)")
    print("  update    Pull latest code and update dependencies")
    print("  test      Run tests")
    print("  clean     Remove virtual environment and cache")
    print("  config    Show configuration")
    print("  help      Show this help message")
    print()
    print("Examples:")
    print("  ./hub install      # First time setup")
    print("  ./hub start        # Launch the app")
    print("  ./hub status       # Check if running")
    print("  ./hub logs         # View logs")
    print("  ./hub restart      # Restart the app")
    print()
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version.split()[0]}")


# Main
def main():
    """Main entry point."""
    # Change to project root directory (parent of bin/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    
    if len(sys.argv) < 2:
        cmd_help()
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    commands = {
        'install': cmd_install,
        'start': cmd_start,
        'stop': cmd_stop,
        'restart': cmd_restart,
        'status': cmd_status,
        'logs': cmd_logs,
        'update': cmd_update,
        'test': cmd_test,
        'clean': cmd_clean,
        'config': cmd_config,
        'help': cmd_help,
        '--help': cmd_help,
        '-h': cmd_help,
    }
    
    if command in commands:
        try:
            commands[command]()
        except KeyboardInterrupt:
            print("\n")
            print_info("Interrupted")
            sys.exit(0)
        except Exception as e:
            print()
            print_error(f"Command failed: {e}")
            sys.exit(1)
    else:
        print_error(f"Unknown command: {command}")
        print()
        cmd_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
