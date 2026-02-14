#!/bin/bash
set -euo pipefail                                                                                        

if [ -z "${1:-}" ]; then
  echo "Usage: $0 <dev|prod> <agency>"
  exit 1
fi

if [ -z "${2:-}" ]; then
  echo "Usage: $0 <dev|prod> <agency>"
  exit 1
fi

ENVIRONMENT="$1"
AGENCY="$2"

case "$ENVIRONMENT" in
  dev)
    DB_CONTAINER="hestia-database-dev"
    ;;
  prod)
    DB_CONTAINER="hestia-database"
    ;;
  *)
    echo "Invalid environment: '$ENVIRONMENT'. Use 'dev' or 'prod'."
    exit 1
    ;;
esac

docker exec "$DB_CONTAINER" psql -U postgres -d hestia -c \
  "UPDATE hestia.subscribers SET filter_agencies = (filter_agencies::jsonb || '[\"$AGENCY\"]'::jsonb)::json;"
