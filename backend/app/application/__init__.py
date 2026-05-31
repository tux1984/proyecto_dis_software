"""Capa de aplicación — servicios que orquestan casos de uso (SAD §6.1.3).

Coordinan dominio, repositorios y adaptadores; no contienen reglas invariantes
(esas viven en el dominio) ni detalles técnicos (esos viven en infraestructura).
``EnrollmentService`` actúa como Facade del flujo de inscripción.
"""
