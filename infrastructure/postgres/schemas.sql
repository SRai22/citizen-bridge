SELECT format('CREATE ROLE auth_service LOGIN PASSWORD %L', :'auth_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'auth_service') \gexec
SELECT format('CREATE ROLE authority_service LOGIN PASSWORD %L', :'authority_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authority_service') \gexec
SELECT format('CREATE ROLE case_service LOGIN PASSWORD %L', :'case_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'case_service') \gexec
SELECT format('CREATE ROLE document_service LOGIN PASSWORD %L', :'document_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'document_service') \gexec
SELECT format('CREATE ROLE notification_service LOGIN PASSWORD %L', :'notification_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'notification_service') \gexec
SELECT format('CREATE ROLE catalog_service LOGIN PASSWORD %L', :'catalog_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'catalog_service') \gexec
SELECT format('CREATE ROLE ai_service LOGIN PASSWORD %L', :'ai_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ai_service') \gexec

CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION auth_service;
CREATE SCHEMA IF NOT EXISTS authority AUTHORIZATION authority_service;
CREATE SCHEMA IF NOT EXISTS cases AUTHORIZATION case_service;
CREATE SCHEMA IF NOT EXISTS documents AUTHORIZATION document_service;
CREATE SCHEMA IF NOT EXISTS notifications AUTHORIZATION notification_service;
CREATE SCHEMA IF NOT EXISTS catalog AUTHORIZATION catalog_service;
CREATE SCHEMA IF NOT EXISTS ai AUTHORIZATION ai_service;

ALTER ROLE auth_service SET search_path TO auth, public;
ALTER ROLE authority_service SET search_path TO authority, public;
ALTER ROLE case_service SET search_path TO cases, public;
ALTER ROLE document_service SET search_path TO documents, public;
ALTER ROLE notification_service SET search_path TO notifications, public;
ALTER ROLE catalog_service SET search_path TO catalog, public;
ALTER ROLE ai_service SET search_path TO ai, public;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
