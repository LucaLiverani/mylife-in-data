#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting My Life in Data Dashboard...${NC}\n"

# Start Next.js frontend
echo -e "${GREEN}Starting Next.js frontend on port 3000 (accessible from network)...${NC}"
# npm run dev # for dev
npm run build && npm start # for production

echo -e "\n${BLUE}Dashboard is running...${NC}"
echo -e "Frontend: ${GREEN}http://localhost:3000${NC}"
echo -e "\nPress Ctrl+C to stop the server\n"
