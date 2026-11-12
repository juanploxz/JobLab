#!/bin/sh
# Database per service: Django keeps POSTGRES_DB; plan-service gets its own database.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<EOSQL
SELECT 'CREATE DATABASE ${PLAN_DB_NAME:-plan_service}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${PLAN_DB_NAME:-plan_service}')\gexec
EOSQL
