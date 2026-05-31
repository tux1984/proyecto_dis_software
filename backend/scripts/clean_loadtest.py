"""Limpia datos generados por las pruebas de carga (Locust).

Las pruebas de carga crean usuarios sintéticos (correos ``load_*``, ``stress_*``,
``conc_*``) que se inscriben a eventos reales y ensucian las listas de inscritos
de la demo. Este script borra sus inscripciones, asistencias, certificados,
entregas y pagos, **liberando cupos**. No borra los usuarios ni el ``audit_log``
(append-only, ADR-10): esos registros quedan, pero ya no aparecen como inscritos.

    python -m scripts.clean_loadtest        # o:  make clean-loadtest
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from app.infrastructure.db import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pgea.clean")

# Subconsulta de usuarios sintéticos de carga (patrones fijos, sin entrada externa).
_MATCH = (
    "(SELECT id FROM users WHERE email LIKE 'load%' "
    "OR email LIKE 'stress%' OR email LIKE 'conc%')"
)


async def clean() -> None:
    async with SessionLocal() as s:
        n = (await s.execute(text(f"SELECT count(*) FROM users WHERE id IN {_MATCH}"))).scalar_one()
        if not n:
            logger.info("No hay usuarios de carga que limpiar.")
            return

        # Orden seguro respecto a llaves foráneas (hijos antes que padres).
        statements = [
            f"DELETE FROM certificates WHERE user_id IN {_MATCH}",
            f"DELETE FROM attendance_records WHERE user_id IN {_MATCH}",
            f"DELETE FROM notification_deliveries WHERE recipient_user_id IN {_MATCH}",
            f"DELETE FROM evaluations WHERE user_id IN {_MATCH}",
            f"DELETE FROM webhook_events WHERE related_enrollment_id IN "
            f"(SELECT id FROM enrollments WHERE user_id IN {_MATCH})",
            f"DELETE FROM payments WHERE enrollment_id IN "
            f"(SELECT id FROM enrollments WHERE user_id IN {_MATCH})",
            f"DELETE FROM enrollments WHERE user_id IN {_MATCH}",
        ]
        for sql in statements:
            res = await s.execute(text(sql))
            logger.info("%-45s -> %s filas", sql.split(" WHERE")[0], res.rowcount)
        await s.commit()
        logger.info("Limpieza completa: %d usuarios de carga depurados (cupos liberados).", n)


if __name__ == "__main__":
    asyncio.run(clean())
