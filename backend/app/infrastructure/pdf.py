"""Generación de certificados PDF (RF-13, RF-21).

Usa fpdf2 (CPU-bound) ejecutado en un hilo desde el worker para no bloquear el
event loop. Cada certificado incluye un código único verificable.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

STORAGE_DIR = Path("/app/storage/certificates")


def generate_certificate_pdf(
    *,
    verification_code: str,
    full_name: str,
    event_title: str,
    event_date: str,
    cert_type: str,
) -> str:
    """Renderiza el PDF y devuelve la ruta relativa servible por la API."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_draw_color(30, 60, 120)
    pdf.set_line_width(2)
    pdf.rect(8, 8, 281, 194)

    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(30, 60, 120)
    pdf.ln(30)
    pdf.cell(0, 20, "Certificado de " + cert_type.capitalize(), align="C")
    pdf.ln(28)

    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 10, "Se certifica que", align="C")
    pdf.ln(16)

    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 12, full_name, align="C")
    pdf.ln(18)

    pdf.set_font("Helvetica", "", 14)
    pdf.multi_cell(
        0,
        9,
        f"participo en el evento academico \"{event_title}\"\n"
        f"realizado el {event_date}, organizado por la Pontificia Universidad Javeriana.",
        align="C",
    )
    pdf.ln(18)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 8, f"Codigo de verificacion: {verification_code}", align="C")
    pdf.ln(6)
    pdf.cell(0, 8, "Verificable en: /verify/" + verification_code, align="C")

    out_path = STORAGE_DIR / f"{verification_code}.pdf"
    pdf.output(str(out_path))
    return f"/certificates/file/{verification_code}.pdf"
