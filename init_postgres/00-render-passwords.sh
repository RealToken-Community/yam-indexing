#!/bin/sh
set -eu

: "${POSTGRES_WRITER_USER_PASSWORD:?Missing POSTGRES_WRITER_USER_PASSWORD}"
: "${POSTGRES_READER_USER_PASSWORD:?Missing POSTGRES_READER_USER_PASSWORD}"
: "${POSTGRES_EVENT_QUEUE_USER_PASSWORD:?Missing POSTGRES_EVENT_QUEUE_USER_PASSWORD}"

# Render and execute immediately (no file creation needed)
envsubst < /docker-entrypoint-initdb.d/01-passwords.sql.template \
  | psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"
