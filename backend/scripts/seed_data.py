"""Poblamiento sintético de la BD (datos relacionados al dominio).

Genera usuarios por rol, categorías por facultad, ~40 eventos académicos
diversos con embeddings reales (para demostrar la búsqueda semántica),
inscripciones en varios estados, asistencias, certificados y auditoría.

Ejecutar:  python -m scripts.seed_data   (idempotente: omite si ya hay datos)
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select

from app.infrastructure.adapters.factory import AdapterFactory
from app.infrastructure.db import SessionLocal
from app.infrastructure.curated_search import CURATED_TOPICS
from app.infrastructure.models import (
    AttendanceRecordModel,
    AuditLogModel,
    CategoryModel,
    CertificateModel,
    EnrollmentModel,
    EventModel,
    UserModel,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pgea.seed")
random.seed(42)

# Fragmentos de título de los temas con búsqueda semántica curada.
_CURATED_FRAGMENTS = [t.lower() for topic in CURATED_TOPICS for t in topic["titles"]]


def _is_curated_title(title: str) -> bool:
    low = title.lower()
    return any(frag in low for frag in _CURATED_FRAGMENTS)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


CATEGORIES = [
    ("Inteligencia Artificial", "Ingeniería"),
    ("Ciberseguridad", "Ingeniería"),
    ("Desarrollo de Software", "Ingeniería"),
    ("Salud Pública", "Medicina"),
    ("Bioética", "Medicina"),
    ("Derecho Constitucional", "Derecho"),
    ("Economía Digital", "Economía"),
    ("Música y Cultura", "Artes"),
    ("Física y Astronomía", "Ciencias"),
    ("Sostenibilidad", "Ciencias"),
]

# Eventos curados (título + descripción) ricos en contenido para que la
# búsqueda semántica encuentre relaciones conceptuales (p.ej. "IA" ~ ML/DL).
EVENTS = [
    ("Congreso de Inteligencia Artificial Aplicada",
     "Avances en machine learning, redes neuronales profundas y aprendizaje automático aplicado a la industria.", "Inteligencia Artificial"),
    ("Taller de Deep Learning con PyTorch",
     "Construcción de modelos de aprendizaje profundo, redes convolucionales y transformers para visión y lenguaje.", "Inteligencia Artificial"),
    ("Seminario de Procesamiento de Lenguaje Natural",
     "Modelos de lenguaje grandes, embeddings semánticos y búsqueda vectorial en aplicaciones reales.", "Inteligencia Artificial"),
    ("Jornada de Ética en la Inteligencia Artificial",
     "Sesgos algorítmicos, transparencia y gobernanza responsable de sistemas inteligentes.", "Inteligencia Artificial"),
    ("Conferencia de Ciberseguridad Ofensiva",
     "Pruebas de penetración, análisis de vulnerabilidades y respuesta a incidentes en infraestructura crítica.", "Ciberseguridad"),
    ("Taller de Criptografía Moderna",
     "Cifrado simétrico y asimétrico, firmas digitales y protocolos seguros de comunicación.", "Ciberseguridad"),
    ("Simposio de Arquitectura de Software",
     "Patrones de diseño, microservicios, arquitectura hexagonal y observabilidad en sistemas distribuidos.", "Desarrollo de Software"),
    ("Workshop de DevOps y Observabilidad",
     "Integración continua, contenedores, métricas, trazas distribuidas y monitoreo con Prometheus y Grafana.", "Desarrollo de Software"),
    ("Curso de Bases de Datos Vectoriales",
     "Almacenamiento de embeddings, índices aproximados y búsqueda semántica con pgvector en PostgreSQL.", "Desarrollo de Software"),
    ("Foro de Salud Pública y Epidemiología",
     "Vigilancia epidemiológica, determinantes sociales de la salud y políticas de prevención.", "Salud Pública"),
    ("Congreso de Telemedicina",
     "Atención remota, historia clínica electrónica y tecnologías digitales para la salud.", "Salud Pública"),
    ("Seminario de Bioética Clínica",
     "Consentimiento informado, dilemas éticos en cuidados intensivos y dignidad del paciente.", "Bioética"),
    ("Cátedra de Derecho Constitucional Comparado",
     "Control de constitucionalidad, derechos fundamentales y bloque de constitucionalidad.", "Derecho Constitucional"),
    ("Conversatorio de Protección de Datos Personales",
     "Ley 1581, habeas data, privacidad y tratamiento responsable de información personal.", "Derecho Constitucional"),
    ("Cumbre de Economía Digital",
     "Transformación digital, plataformas, fintech y nuevos modelos de negocio en la era de los datos.", "Economía Digital"),
    ("Panel de Criptoactivos y Blockchain",
     "Cadenas de bloques, contratos inteligentes, tokens y regulación de activos digitales.", "Economía Digital"),
    ("Festival de Música y Cultura Universitaria",
     "Conciertos, composición, producción musical y patrimonio cultural inmaterial.", "Música y Cultura"),
    ("Recital de Música de Cámara",
     "Interpretación de obras clásicas y contemporáneas por ensambles estudiantiles.", "Música y Cultura"),
    ("Coloquio de Física de Partículas",
     "Modelo estándar, aceleradores, materia oscura y fronteras de la física moderna.", "Física y Astronomía"),
    ("Observación Astronómica y Cosmología",
     "Exoplanetas, telescopios, expansión del universo y origen de las galaxias.", "Física y Astronomía"),
    ("Foro de Sostenibilidad y Cambio Climático",
     "Energías renovables, economía circular, huella de carbono y desarrollo sostenible.", "Sostenibilidad"),
    ("Taller de Energías Renovables",
     "Solar fotovoltaica, eólica e hidrógeno verde para la transición energética.", "Sostenibilidad"),
]

MODALITIES = ["presencial", "virtual", "hibrido"]


async def seed() -> None:
    async with SessionLocal() as s:
        existing = await s.scalar(select(func.count()).select_from(UserModel))
        if existing and existing > 0:
            logger.info("La BD ya tiene datos (%s usuarios). Omitiendo seed.", existing)
            return

        embedder = AdapterFactory().create_embedding()
        logger.info("Generando datos sintéticos (embeddings: %s)...", embedder.provider_name)

        # --- Categorías ---
        cat_ids: dict[str, object] = {}
        for name, faculty in CATEGORIES:
            cid = uuid4()
            s.add(CategoryModel(id=cid, name=name, faculty=faculty))
            cat_ids[name] = cid
        await s.flush()

        # --- Usuarios ---
        admin = _mk_user("admin@javeriana.edu.co", "Admin Institucional", "admin")
        organizers = [
            _mk_user(f"organizador{i}@javeriana.edu.co", f"Organizador {i}", "organizer")
            for i in range(1, 4)
        ]
        speakers = [
            _mk_user(f"ponente{i}@javeriana.edu.co", f"Ponente {i}", "speaker")
            for i in range(1, 4)
        ]
        attendees = [
            _mk_user(f"asistente{i}@javeriana.edu.co", f"Asistente {i}", "attendee")
            for i in range(1, 13)
        ]
        reviewer = _mk_user("revisor@javeriana.edu.co", "Revisor Académico", "reviewer")
        all_users = [admin, *organizers, *speakers, *attendees, reviewer]
        for u in all_users:
            s.add(u)
        await s.flush()

        # --- Eventos ---
        events: list[EventModel] = []
        for idx, (title, desc, cat) in enumerate(EVENTS):
            organizer = organizers[idx % len(organizers)]
            starts = _now() + timedelta(days=random.randint(-10, 40), hours=random.randint(8, 16))
            ends = starts + timedelta(hours=random.choice([2, 3, 4, 8]))
            # ~80% publicados; el resto en borrador/pendiente para los paneles.
            roll = random.random()
            status = "publicado" if roll < 0.8 else ("pendiente" if roll < 0.9 else "borrador")
            # Los eventos de temas con búsqueda semántica curada siempre se
            # publican, para que la demo de búsqueda sea reproducible.
            if _is_curated_title(title):
                status = "publicado"
            reg_type = "paga" if idx % 5 == 0 else "gratuita"
            ev = EventModel(
                id=uuid4(),
                title=title,
                description=desc,
                modality=random.choice(MODALITIES),
                starts_at=starts,
                ends_at=ends,
                location="Edificio Central, Aula " + str(random.randint(101, 410)),
                capacity=random.choice([40, 60, 100, 150]),
                status=status,
                registration_type=reg_type,
                organizer_id=organizer.id,
                category_id=cat_ids[cat],
                published_at=_now() if status == "publicado" else None,
            )
            if status == "publicado":
                try:
                    ev.embedding = await embedder.embed(f"{title}. {desc}")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("No se generó embedding para '%s': %s", title, exc)
            s.add(ev)
            events.append(ev)
        await s.flush()

        # --- Inscripciones (fase 1: crear y persistir antes de certificados) ---
        published = [e for e in events if e.status == "publicado"]
        created: list[tuple[EnrollmentModel, EventModel, UserModel, str]] = []
        for ev in published:
            n = random.randint(3, min(10, ev.capacity))
            chosen = random.sample(attendees, min(n, len(attendees)))
            for i, att in enumerate(chosen):
                status = "confirmada"
                if i % 7 == 0:
                    status = "cancelada"
                elif i % 9 == 0 and ev.registration_type == "paga":
                    status = "pendiente_pago"
                enr = EnrollmentModel(
                    id=uuid4(), event_id=ev.id, user_id=att.id, status=status,
                    confirmed_at=_now() if status == "confirmada" else None,
                )
                s.add(enr)
                created.append((enr, ev, att, status))
        await s.flush()  # garantiza que las inscripciones existen (FK de certificados)

        # --- Asistencia y certificados (fase 2) para confirmados de eventos pasados ---
        cert_count = 0
        for enr, ev, att, status in created:
            if status == "confirmada" and ev.starts_at < _now():
                s.add(AttendanceRecordModel(
                    id=uuid4(), event_id=ev.id, user_id=att.id, source="seed"
                ))
                s.add(CertificateModel(
                    id=uuid4(), user_id=att.id, event_id=ev.id, type="asistencia",
                    verification_code=uuid4().hex, enrollment_id=enr.id,
                ))
                cert_count += 1
        await s.flush()

        # --- Auditoría de ejemplo ---
        for ev in published[:5]:
            s.add(AuditLogModel(
                id=uuid4(), actor_user_id=ev.organizer_id, action="event_published",
                entity_type="event", entity_id=ev.id, result="success",
                trace_id=uuid4().hex,
            ))

        await s.commit()
        logger.info(
            "Seed completo: %d usuarios, %d eventos (%d publicados), %d certificados.",
            len(all_users), len(events), len(published), cert_count,
        )


def _mk_user(email: str, name: str, role: str) -> UserModel:
    return UserModel(
        id=uuid4(), email=email, full_name=name, role=role,
        auth_provider="mock", consent_accepted_at=_now(),
    )


if __name__ == "__main__":
    asyncio.run(seed())
