#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting My Life in Data Dashboard...${NC}\n"

# Start FastAPI backend
echo -e "${GREEN}Starting FastAPI backend on port 8000...${NC}"
cd api 
source venv/bin/activate
python3 main.py &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 2

# Start Next.js frontend
echo -e "${GREEN}Starting Next.js frontend on port 3000 (accessible from network)...${NC}"
# npm run dev & # for dev
npm run build && npm start & # for production
FRONTEND_PID=$!

echo -e "\n${BLUE}Dashboard is starting...${NC}"
echo -e "Frontend: ${GREEN}http://localhost:3000${NC}"
echo -e "Backend API: ${GREEN}http://localhost:8000${NC}"
echo -e "\nPress Ctrl+C to stop both servers\n"

# Trap Ctrl+C and kill both processes
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT

# Wait for both processes
wait
