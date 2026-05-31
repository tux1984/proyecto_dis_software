"""Capa de infraestructura — implementaciones concretas de los puertos.

Persistencia (SQLAlchemy async + asyncpg), adaptadores a sistemas externos,
cola interna y caché. Es la única capa que conoce detalles técnicos (BD,
proveedores, protocolos). Sustituible sin tocar dominio ni aplicación.
"""
