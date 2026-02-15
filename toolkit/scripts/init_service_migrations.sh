#!/bin/bash
set -e

# Usage: ./toolkit/scripts/init_service_migrations.sh <service_name>
# Example: ./toolkit/scripts/init_service_migrations.sh planning_agent

SERVICE=$1
if [ -z "$SERVICE" ]; then
    echo "Usage: $0 <service_name>"
    echo "Example: $0 planning_agent"
    exit 1
fi

SERVICE_DIR="microservices/$SERVICE"
if [ ! -d "$SERVICE_DIR" ]; then
    echo "Error: Directory $SERVICE_DIR does not exist."
    exit 1
fi

echo "Initializing migrations for $SERVICE..."

# Create directory structure
mkdir -p "$SERVICE_DIR/migrations/versions"

# Copy templates
cp toolkit/migrations/alembic.ini.template "$SERVICE_DIR/alembic.ini"
cp toolkit/migrations/env.py.template "$SERVICE_DIR/migrations/env.py"

# Copy mako script if it exists in root, otherwise use default
if [ -f "migrations/script.py.mako" ]; then
    cp migrations/script.py.mako "$SERVICE_DIR/migrations/script.py.mako"
fi

# Inject model imports into env.py
sed -i "s/# REPLACE_WITH_SERVICE_IMPORT/from microservices.$SERVICE.models import */g" "$SERVICE_DIR/migrations/env.py"

echo "✅ Migrations initialized for $SERVICE at $SERVICE_DIR/migrations"
echo "👉 CHECK: Verify imports in $SERVICE_DIR/migrations/env.py"
echo "👉 RUN: cd $SERVICE_DIR && alembic revision --autogenerate -m 'Initial migration'"
