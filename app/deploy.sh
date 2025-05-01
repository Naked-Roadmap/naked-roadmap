#!/bin/bash

# Deployment script for Naked Roadmap
echo "Starting deployment process..."

# Create data directory with proper permissions
echo "Setting up data directory..."
mkdir -p /data
chmod 777 /data

# Clean up any existing containers
echo "Cleaning up existing containers..."
docker-compose down

# Remove old volume if it exists
echo "Cleaning up old volumes..."
docker volume rm $(docker volume ls -q -f name=app_data) 2>/dev/null || true

# Rebuild the image
echo "Building Docker image..."
docker-compose build

# Run the container
echo "Starting container..."
docker-compose up -d

# Watch logs
echo "Deployment complete! Watching logs..."
docker-compose logs -f