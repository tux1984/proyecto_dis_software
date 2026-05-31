"""Capa de interfaz — routers HTTP (Controllers), schemas (DTOs) y DI.

Traduce HTTP a llamadas de servicios de aplicación. Valida entrada/salida con
Pydantic v2 (Builder), inyecta dependencias con ``Depends`` y aplica RBAC.
"""
