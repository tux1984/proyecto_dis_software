"""Adaptadores a sistemas externos (patrón Adapter, ADR-03).

Cada proveedor implementa el ``Protocol`` correspondiente. La selección
mock/real es por configuración vía ``AdapterFactory`` (Factory Method),
sin condicionales en la lógica de negocio (RNF-15, RNF-16).
"""
