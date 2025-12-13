#!/bin/bash

# cleanup.sh - Clean up old App Engine versions
# Usage: ./cleanup.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}App Engine Cleanup Script${NC}\n"

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: No GCP project set${NC}"
    exit 1
fi

echo -e "${YELLOW}Project: ${PROJECT_ID}${NC}\n"

# List all versions
echo -e "${GREEN}Current App Engine versions:${NC}\n"
gcloud app versions list --format="table(service,version.id,traffic_split,last_deployed_time.date())"

echo -e "\n${YELLOW}What would you like to do?${NC}"
echo "1) Delete all versions with 0% traffic"
echo "2) Keep only the latest 3 versions per service"
echo "3) Stop all versions (keep configs)"
echo "4) List versions only"
read -p "Enter choice [1-4]: " choice

case $choice in
    1)
        echo -e "\n${YELLOW}Deleting versions with 0% traffic...${NC}\n"
        
        SERVICES=$(gcloud app services list --format="value(id)")
        
        for SERVICE in $SERVICES; do
            echo -e "${YELLOW}Checking service: ${SERVICE}${NC}"
            VERSIONS=$(gcloud app versions list --service=$SERVICE --filter="traffic_split=0" --format="value(id)")
            
            if [ ! -z "$VERSIONS" ]; then
                echo "Deleting versions: $VERSIONS"
                gcloud app versions delete $VERSIONS --service=$SERVICE --quiet
            else
                echo "No versions to delete"
            fi
        done
        
        echo -e "\n${GREEN}✓ Cleanup complete!${NC}\n"
        ;;
    2)
        echo -e "\n${YELLOW}Keeping only latest 3 versions per service...${NC}\n"
        
        SERVICES=$(gcloud app services list --format="value(id)")
        
        for SERVICE in $SERVICES; do
            echo -e "${YELLOW}Checking service: ${SERVICE}${NC}"
            
            # Get all versions sorted by creation time, skip first 3
            VERSIONS=$(gcloud app versions list --service=$SERVICE --sort-by="~version.createTime" --format="value(id)" | tail -n +4)
            
            if [ ! -z "$VERSIONS" ]; then
                echo "Deleting old versions: $VERSIONS"
                gcloud app versions delete $VERSIONS --service=$SERVICE --quiet
            else
                echo "No old versions to delete"
            fi
        done
        
        echo -e "\n${GREEN}✓ Cleanup complete!${NC}\n"
        ;;
    3)
        echo -e "\n${YELLOW}Stopping all versions...${NC}\n"
        
        SERVICES=$(gcloud app services list --format="value(id)")
        
        for SERVICE in $SERVICES; do
            echo -e "${YELLOW}Stopping service: ${SERVICE}${NC}"
            VERSIONS=$(gcloud app versions list --service=$SERVICE --format="value(id)")
            
            if [ ! -z "$VERSIONS" ]; then
                gcloud app versions stop $VERSIONS --service=$SERVICE --quiet
            fi
        done
        
        echo -e "\n${GREEN}✓ All versions stopped!${NC}\n"
        ;;
    4)
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac