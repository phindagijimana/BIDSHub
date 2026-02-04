#!/bin/bash
#
# Data Explorer Launch Script
# Automatically finds available port between 8500-8550
#

set -e

# Change to project root directory (parent of bin/)
cd "$(dirname "$0")/.."

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Port range
MIN_PORT=8500
MAX_PORT=8550
DEFAULT_PORT=8501

# Function to check if port is available
is_port_available() {
    local port=$1
    # Try to establish a connection to the port
    ! nc -z localhost $port 2>/dev/null
    return $?
}

# Function to find available port
find_available_port() {
    # Try default port first
    if is_port_available $DEFAULT_PORT; then
        echo $DEFAULT_PORT
        return 0
    fi
    
    # Try other ports in range
    for port in $(seq $MIN_PORT $MAX_PORT); do
        # Skip default port (already tried)
        if [ $port -eq $DEFAULT_PORT ]; then
            continue
        fi
        
        if is_port_available $port; then
            echo $port
            return 0
        fi
    done
    return 1
}

# Header
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}           Data Explorer Launch Script${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}⚠  Virtual environment not activated${NC}"
    echo -e "Attempting to activate venv..."
    
    if [[ -d "venv" ]]; then
        source venv/bin/activate
        echo -e "${GREEN}✓ Virtual environment activated${NC}"
    else
        echo -e "${RED}✗ Virtual environment not found${NC}"
        echo -e "${YELLOW}Run: python -m venv venv && source venv/bin/activate${NC}"
        exit 1
    fi
fi

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo -e "${RED}✗ Streamlit not installed${NC}"
    echo -e "${YELLOW}Run: pip install -r requirements.txt${NC}"
    exit 1
fi

# Find available port
echo -e "Searching for available port in range ${MIN_PORT}-${MAX_PORT}..."
PORT=$(find_available_port)

if [[ -z "$PORT" ]]; then
    echo -e "${RED}✗ No available ports in range ${MIN_PORT}-${MAX_PORT}${NC}"
    echo -e "${YELLOW}Please close some applications and try again${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found available port: ${PORT}${NC}"
echo ""

# Launch Streamlit
echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
echo -e "${GREEN}🚀 Launching Data Explorer on port ${PORT}...${NC}"
echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
echo ""
echo -e "  Local URL:   ${GREEN}http://localhost:${PORT}${NC}"
echo -e "  Network URL: ${GREEN}http://$(ipconfig getifaddr en0 2>/dev/null || echo "N/A"):${PORT}${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

# Launch with the found port
streamlit run app.py --server.port $PORT --server.headless false
