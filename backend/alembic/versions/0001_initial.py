"""Esquema inicial PGEA: extensión pgvector, tablas, índices híbridos y
trigger de inmutabilidad de auditoría (ADR-05, ADR-07, ADR-10).

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-30
"""

from __future__ import annotations

from alembic import op

from app.infrastructure.db import Base

# Importa los modelos para poblar Base.metadata
import app.infrastructure.models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Extensión vectorial ANTES de crear tablas (events.embedding vector(384))
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2) Crear todas las tablas a partir de los modelos ORM (baseline)
    Base.metadata.create_all(bind=bind)

    # 3) Índices especializados de búsqueda híbrida (RF-30, ADR-07)
    #    Full-text en español (GIN sobre tsvector de título + descripción)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_events_fulltext
        ON events
        USING GIN (to_tsvector('spanish', coalesce(title,'') || ' ' || coalesce(description,'')))
        """
    )
    #    Vectorial aproximado (IVFFlat, distancia coseno, lists=100)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_events_embedding
        ON events
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
        """
    )

    # 4) Inmutabilidad de auditoría a nivel de BD (ADR-10, RF-29, RN-07).
    #    Trigger que bloquea UPDATE/DELETE incluso para el dueño de la tabla
    #    (defensa en profundidad superior a un simple REVOKE). Emite SQLSTATE
    #    42501 (insufficient_privilege) para alinear con el criterio del SAD.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION pgea_block_audit_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log es append-only (ADR-10): % no permitido', TG_OP
                USING ERRCODE = '42501';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION pgea_block_audit_mutation();
        """
    )

    # 5) Catálogo de roles RBAC (RF-26)
    op.execute(
        """
        INSERT INTO roles (name, description) VALUES
          ('organizer','Crea y gestiona eventos, inscritos y certificados'),
          ('attendee','Descubre eventos, se inscribe y descarga certificados'),
          ('speaker','Confirma invitaciones, completa perfil y sube material'),
          ('reviewer','Evalúa propuestas académicas (fase futura)'),
          ('admin','Supervisa, aprueba, gestiona usuarios y monitorea')
        ON CONFLICT (name) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS pgea_block_audit_mutation()")
    Base.metadata.drop_all(bind=op.get_bind())
