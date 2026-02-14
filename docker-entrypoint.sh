#!/bin/bash
set -e

# ----------------------------------------
# YAM Indexing Docker Entrypoint
# ----------------------------------------
# Responsibilities:
# 1. Verify that YAM_INDEXING_DB_PATH is set.
# 2. Ensure the database directory exists.
# 3. Initialize the database if it does not exist.
# 4. Start the main indexing service.
# ----------------------------------------

echo "Starting yam-indexing-indexer container..."

# Move into the application directory (must match WORKDIR in Dockerfile)
cd /app

# 1) Ensure PostgreSQL environment variables are provided
missing=false

for var in POSTGRES_DB POSTGRES_HOST POSTGRES_PORT POSTGRES_WRITER_USER_PASSWORD; do
  if [ -z "${!var}" ]; then
    echo "ERROR: environment variable $var is not set."
    missing=true
  fi
done

if [ "$missing" = true ]; then
  echo "Please define the missing variables in your .env file or GitHub environment variables."
  exit 1
fi

# 2) Start the main indexing loop
echo "Launching main indexing module..."
exec python3 -m main