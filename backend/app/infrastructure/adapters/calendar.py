"""Adaptador de calendario iCal (ICalendarAdapter, RF-16).

Genera un archivo .ics conforme a RFC 5545, compatible con Google Calendar y
Outlook. Integración de nivel L1 (referencial): no hay sincronización.
"""

from __future__ import annotations

from datetime import datetime


def _fmt(dt: datetime) -> str:
    # Formato UTC básico: 20260601T140000Z
    return dt.astimezone().strftime("%Y%m%dT%H%M%SZ")


class IcsCalendarAdapter:
    def build_ics(
        self,
        *,
        uid: str,
        title: str,
        description: str,
        starts_at: datetime,
        ends_at: datetime,
        location: str | None,
    ) -> str:
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//PGEA//Eventos Academicos//ES",
            "CALSCALE:GREGORIAN",
            "BEGIN:VEVENT",
            f"UID:{uid}@pgea.javeriana.edu.co",
            f"DTSTAMP:{_fmt(datetime.now())}",
            f"DTSTART:{_fmt(starts_at)}",
            f"DTEND:{_fmt(ends_at)}",
            f"SUMMARY:{_escape(title)}",
            f"DESCRIPTION:{_escape(description)}",
            f"LOCATION:{_escape(location or 'Por definir')}",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
        return "\r\n".join(lines) + "\r\n"


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )
