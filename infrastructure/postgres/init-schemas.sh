#!/bin/sh
set -eu

psql --set=ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=auth_password="$AUTH_DB_PASSWORD" \
  --set=authority_password="$AUTHORITY_DB_PASSWORD" \
  --set=case_password="$CASE_DB_PASSWORD" \
  --set=document_password="$DOCUMENT_DB_PASSWORD" \
  --set=notification_password="$NOTIFICATION_DB_PASSWORD" \
  --set=catalog_password="$CATALOG_DB_PASSWORD" \
  --set=ai_password="$AI_DB_PASSWORD" \
  --file=/opt/citizen-bridge/schemas.sql
