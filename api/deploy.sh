#!/bin/bash

# deploy.sh - Google App Engine Deployment Script
# Usage: ./deploy.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Google App Engine Deployment Script${NC}"
echo -e "${GREEN}========================================${NC}\n"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

# Get current project
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: No GCP project set${NC}"
    echo "Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo -e "${YELLOW}Current Project: ${PROJECT_ID}${NC}\n"

# Function to create or update secret
create_or_update_secret() {
    local SECRET_NAME=$1
    local SECRET_VALUE=$2
    
    if gcloud secrets describe "$SECRET_NAME" &>/dev/null; then
        echo -e "${YELLOW}Updating existing secret: ${SECRET_NAME}${NC}"
        echo -n "$SECRET_VALUE" | gcloud secrets versions add "$SECRET_NAME" --data-file=-
    else
        echo -e "${GREEN}Creating new secret: ${SECRET_NAME}${NC}"
        echo -n "$SECRET_VALUE" | gcloud secrets create "$SECRET_NAME" --data-file=-
    fi
}

# Function to grant access to secret
grant_secret_access() {
    local SECRET_NAME=$1
    echo "Granting access to: ${SECRET_NAME}"
    gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
        --member="serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet 2>/dev/null || true
}

# Ask user what to do
echo -e "${YELLOW}What would you like to do?${NC}"
echo "1) Create/Update secrets only"
echo "2) Deploy to App Engine only"
echo "3) Create/Update secrets AND deploy (full deployment)"
echo "4) Stop all App Engine versions"
read -p "Enter choice [1-4]: " choice

case $choice in
    1|3)
        echo -e "\n${GREEN}Step 1: Creating/Updating secrets from .env file...${NC}\n"
        
        # Read .env and create secrets
        while IFS='=' read -r key value; do
            # Skip empty lines and comments
            if [[ -z "$key" || "$key" =~ ^#.* ]]; then
                continue
            fi
            
            # Remove any trailing whitespace or comments
            value=$(echo "$value" | sed 's/#.*//' | xargs)
            
            if [[ ! -z "$value" ]]; then
                create_or_update_secret "$key" "$value"
            fi
        done < .env
        
        # Create aliases for Pydantic compatibility
        echo -e "\n${GREEN}Creating Pydantic compatibility aliases...${NC}"
        
        # Extract values from .env for aliases
        CLIENT_ID=$(grep "^ZAKYA_CLIENT_ID=" .env | cut -d '=' -f2)
        CLIENT_SECRET=$(grep "^ZAKYA_CLIENT_SECRET=" .env | cut -d '=' -f2)
        REDIRECT_URI=$(grep "^ZAKYA_REDIRECT_URI=" .env | cut -d '=' -f2)
        POSTGRES_URI=$(grep "^POSTGRES_SESSION_POOL_URI=" .env | cut -d '=' -f2)
        
        if [ ! -z "$CLIENT_ID" ]; then
            create_or_update_secret "CLIENT_ID" "$CLIENT_ID"
        fi
        if [ ! -z "$CLIENT_SECRET" ]; then
            create_or_update_secret "CLIENT_SECRET" "$CLIENT_SECRET"
        fi
        if [ ! -z "$REDIRECT_URI" ]; then
            create_or_update_secret "REDIRECT_URI" "$REDIRECT_URI"
        fi
        if [ ! -z "$POSTGRES_URI" ]; then
            create_or_update_secret "POSTGRES_URI" "$POSTGRES_URI"
        fi
        
        echo -e "\n${GREEN}Step 2: Granting App Engine access to secrets...${NC}\n"
        
        # Get all secret names
        SECRETS=$(gcloud secrets list --format="value(name)")
        
        for SECRET in $SECRETS; do
            grant_secret_access "$SECRET"
        done
        
        echo -e "\n${GREEN}✓ Secrets created/updated successfully!${NC}\n"
        
        if [ "$choice" == "1" ]; then
            exit 0
        fi
        ;;
    4)
        echo -e "\n${YELLOW}Stopping all App Engine versions...${NC}\n"
        
        SERVICES=$(gcloud app services list --format="value(id)" 2>/dev/null)
        
        if [ -z "$SERVICES" ]; then
            echo -e "${YELLOW}No App Engine services found${NC}"
            exit 0
        fi
        
        for SERVICE in $SERVICES; do
            echo -e "${YELLOW}Stopping versions in service: ${SERVICE}${NC}"
            VERSIONS=$(gcloud app versions list --service=$SERVICE --format="value(id)" 2>/dev/null)
            if [ ! -z "$VERSIONS" ]; then
                gcloud app versions stop $VERSIONS --service=$SERVICE --quiet
            fi
        done
        
        echo -e "\n${GREEN}✓ All App Engine versions stopped!${NC}\n"
        exit 0
        ;;
esac

# Deploy to App Engine
if [ "$choice" == "2" ] || [ "$choice" == "3" ]; then
    echo -e "\n${GREEN}Step 3: Deploying to App Engine...${NC}\n"
    
    # Check if app.yaml exists
    if [ ! -f app.yaml ]; then
        echo -e "${RED}Error: app.yaml not found${NC}"
        exit 1
    fi
    
    # Deploy
    gcloud app deploy app.yaml --quiet
    
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ Deployment completed successfully!${NC}"
    echo -e "${GREEN}========================================${NC}\n"
    
    # Show the app URL
    APP_URL=$(gcloud app browse --no-launch-browser 2>&1 | grep -o 'https://[^[:space:]]*')
    if [ ! -z "$APP_URL" ]; then
        echo -e "Your app is deployed at: ${GREEN}${APP_URL}${NC}\n"
    fi
    
    # Show logs command
    echo -e "${YELLOW}To view logs, run:${NC}"
    echo "gcloud app logs tail -s default"
    echo ""
fi