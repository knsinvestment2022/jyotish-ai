"""PDF rendering of a generated reading, using the same reportlab pattern
used for Career_Astrology_Explained.pdf earlier in this project."""
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY

styles = getSampleStyleSheet()
TITLE = ParagraphStyle("TitleCustom", parent=styles["Title"], fontSize=20,
                        textColor=colors.HexColor("#1F4E79"), spaceAfter=4)
SUBTITLE = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=11,
                          textColor=colors.HexColor("#595959"),
                          fontName="Helvetica-Oblique", spaceAfter=14)
H1 = ParagraphStyle("H1Custom", parent=styles["Heading1"], fontSize=14,
                     textColor=colors.HexColor("#1F4E79"), spaceBefore=12, spaceAfter=6)
BODY = ParagraphStyle("BodyCustom", parent=styles["Normal"], fontSize=10.5,
                       leading=15, alignment=TA_JUSTIFY, spaceAfter=10)


def build_reading_pdf(name, sections):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
        topMargin=0.85 * inch, bottomMargin=0.85 * inch,
        title=f"Vedic Astrology Reading - {name}",
    )
    story = [
        Paragraph("VEDIC ASTROLOGY READING", TITLE),
        Paragraph(f"Prepared for {name}", SUBTITLE),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CCCCCC"), spaceAfter=12),
    ]
    for sec in sections:
        story.append(Paragraph(sec["title"], H1))
        story.append(Paragraph(sec["body"], BODY))
    story.append(Spacer(1, 10))
    doc.build(story)
    return buf.getvalue()
