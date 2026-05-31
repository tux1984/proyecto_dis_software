"""Puertos del dominio (Hexagonal Ports & Adapters, ADR-03).

Interfaces ``Protocol`` que el dominio/aplicación consumen y la infraestructura
implementa. Permiten inyectar mocks en pruebas y sustituir proveedores por
configuración sin tocar la lógica de negocio (RNF-15, RNF-16).
"""
