-- Inicialización de extensiones para RAG Multimodal
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Base de datos dedicada para observabilidad con Langfuse
SELECT 'CREATE DATABASE langfuse' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec


