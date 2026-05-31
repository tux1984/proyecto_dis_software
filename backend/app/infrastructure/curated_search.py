"""Mapa de búsqueda semántica curada (demo determinista, RF-30).

Para la demostración usamos casos "quemados": ciertas consultas conceptuales
devuelven los eventos relacionados aunque NO compartan las palabras exactas
(p. ej. "inteligencia artificial" trae "Deep Learning", "Procesamiento de
Lenguaje Natural" y "Bases de Datos Vectoriales"). Esto evita depender de un
proveedor de embeddings para que la demo se vea como una búsqueda semántica
real. La columna ``vector(384)`` y pgvector siguen en la arquitectura: si se
configura ``EMBEDDING_PROVIDER=openai`` con una API key, la estrategia usa la
búsqueda vectorial real como respaldo (ADR-07).

Cada tema define:
  - ``triggers``: frases que, si aparecen en la consulta, activan el tema.
  - ``titles``: fragmentos de título de los eventos a devolver (en orden de
    relevancia). El match es por ``ILIKE`` sobre el título, así funciona con los
    datos sembrados sin depender de IDs.
"""

from __future__ import annotations

import unicodedata

CURATED_TOPICS: list[dict] = [
    {
        "topic": "inteligencia_artificial",
        "triggers": [
            "inteligencia artificial", "ia", "ai", "machine learning",
            "aprendizaje automatico", "aprendizaje de maquina", "deep learning",
            "aprendizaje profundo", "redes neuronales", "nlp",
            "procesamiento de lenguaje", "datos vectoriales", "embeddings",
        ],
        # No comparten las palabras "inteligencia artificial" → muestra el valor semántico.
        "titles": [
            "Inteligencia Artificial",
            "Deep Learning",
            "Procesamiento de Lenguaje Natural",
            "Bases de Datos Vectoriales",
        ],
    },
    {
        "topic": "ciberseguridad",
        "triggers": [
            "ciberseguridad", "seguridad informatica", "seguridad digital",
            "seguridad", "hacking", "pentesting", "criptografia",
            "proteccion de datos", "privacidad",
        ],
        "titles": [
            "Ciberseguridad",
            "Criptografía",
            "Protección de Datos",
        ],
    },
    {
        "topic": "salud_medicina",
        "triggers": [
            "salud", "medicina", "medico", "clinica", "clinico",
            "epidemiologia", "telemedicina", "bioetica", "hospital",
        ],
        "titles": [
            "Salud Pública",
            "Telemedicina",
            "Bioética",
        ],
    },
]


def _norm(text: str) -> str:
    """Minúsculas + sin acentos para comparar de forma robusta."""
    folded = unicodedata.normalize("NFKD", text.lower().strip())
    return "".join(c for c in folded if not unicodedata.combining(c))


def match_curated_titles(query: str) -> list[str] | None:
    """Devuelve los fragmentos de título del tema que coincide con la consulta.

    Coincide si algún ``trigger`` es subcadena de la consulta o si la consulta
    es exactamente un trigger (para abreviaturas como "IA"). ``None`` si no hay
    tema curado (la estrategia caerá a búsqueda textual).
    """
    q = _norm(query)
    if not q:
        return None
    for topic in CURATED_TOPICS:
        for trigger in topic["triggers"]:
            t = _norm(trigger)
            if t in q or q == t:
                return topic["titles"]
    return None
