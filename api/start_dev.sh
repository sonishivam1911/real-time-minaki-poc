#!/bin/bash

# Local Development Startup Script
# This script checks for virtual environment, creates one if needed, installs dependencies, and starts the FastAPI app

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Local Development Environment${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 is not installed. Please install Python3 first.${NC}"
    exit 1
fi

# Define virtual environment directory
VENV_DIR="venv"

# Check if virtual environment exists
if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}✅ Virtual environment found at ./$VENV_DIR${NC}"
else
    echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
    python3 -m venv $VENV_DIR
    echo -e "${GREEN}✅ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}🔄 Activating virtual environment...${NC}"
source $VENV_DIR/bin/activate

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}❌ requirements.txt not found. Please create requirements.txt file.${NC}"
    exit 1
fi

# Install/upgrade packages
echo -e "${YELLOW}📦 Installing/updating packages from requirements.txt...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Warning: .env file not found. Make sure to create it with required environment variables.${NC}"
fi

# Check if main.py exists
if [ ! -f "main.py" ]; then
    echo -e "${RED}❌ main.py not found. Please ensure main.py is in the current directory.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All dependencies installed successfully${NC}"

# Start the FastAPI application
echo -e "${GREEN}🌟 Starting FastAPI application...${NC}"
echo -e "${YELLOW}📍 Server will be available at: http://localhost:8000${NC}"
echo -e "${YELLOW}📍 API docs will be available at: http://localhost:8000/docs${NC}"
echo -e "${YELLOW}🔄 Press Ctrl+C to stop the server${NC}"

# Start uvicorn with reload for development
uvicorn main:app --host 0.0.0.0 --port 8000 --reload