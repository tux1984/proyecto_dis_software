"""PGEA — Plataforma de Gestión de Eventos Académicos.

Monolito modular con arquitectura limpia por capas (SAD §6.1):

    interface  → aplicación → dominio ← infraestructura

El dominio no depende de nada externo: expone *puertos* (``Protocol``) que la
capa de infraestructura implementa (Hexagonal Ports & Adapters, ADR-03).
La observabilidad es transversal y se inicializa antes que cualquier lógica
de negocio (RN-10, RI-04).
"""

__version__ = "1.0.0"
