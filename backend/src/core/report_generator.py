"""
Lender-Ready PDF Report Generator (Pure Python)
Generates a single-page A4 financial verification report for Kenyan SACCOs and microfinance lenders.
Zero OS-level binary dependencies. Works 100% offline without external services.
"""
from typing import Dict, Any, List, Optional
import io
from datetime import datetime, timezone
from .models import BiasharaScoreResult

# Check if ReportLab is installed in the environment
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def _escape_pdf_text(text: str) -> str:
    """Escapes special characters in PDF string literals and removes non-ASCII."""
    clean = str(text).replace("—", "-").replace("–", "-").replace("•", "*")
    clean = clean.encode("ascii", "replace").decode("ascii")
    return clean.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class PurePythonPDFBuilder:
    """
    Constructs a valid, standard-compliant PDF 1.4 document in pure Python.
    Creates rich vector graphics, tables, styled text, and branding.
    """
    def __init__(self, width: float = 595.28, height: float = 841.89):
        self.width = width
        self.height = height
        self.commands: List[str] = []

    def rect(self, x: float, y: float, w: float, h: float, fill_rgb: Optional[tuple] = None, stroke_rgb: Optional[tuple] = None, line_width: float = 1.0):
        self.commands.append("q")
        if line_width != 1.0:
            self.commands.append(f"{line_width:.2f} w")
        if fill_rgb:
            self.commands.append(f"{fill_rgb[0]:.3f} {fill_rgb[1]:.3f} {fill_rgb[2]:.3f} rg")
        if stroke_rgb:
            self.commands.append(f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG")
        self.commands.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        if fill_rgb and stroke_rgb:
            self.commands.append("B")
        elif fill_rgb:
            self.commands.append("f")
        elif stroke_rgb:
            self.commands.append("s")
        self.commands.append("Q")

    def line(self, x1: float, y1: float, x2: float, y2: float, stroke_rgb: tuple = (0.7, 0.7, 0.7), line_width: float = 1.0):
        self.commands.append("q")
        self.commands.append(f"{line_width:.2f} w")
        self.commands.append(f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG")
        self.commands.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l s")
        self.commands.append("Q")

    def text(self, x: float, y: float, string: str, font: str = "F1", size: float = 10, fill_rgb: tuple = (0.1, 0.1, 0.1)):
        escaped = _escape_pdf_text(string)
        self.commands.append("BT")
        self.commands.append(f"{fill_rgb[0]:.3f} {fill_rgb[1]:.3f} {fill_rgb[2]:.3f} rg")
        self.commands.append(f"/{font} {size:.1f} Tf")
        self.commands.append(f"{x:.2f} {y:.2f} Td")
        self.commands.append(f"({escaped}) Tj")
        self.commands.append("ET")

    def build(self) -> bytes:
        stream_content = "\n".join(self.commands).encode("ascii")
        stream_len = len(stream_content)

        objects = []
        # Obj 1: Catalog
        objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
        # Obj 2: Pages
        objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
        # Obj 3: Page
        page_dict = (
            f"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.width:.2f} {self.height:.2f}] "
            "/Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R /F3 7 0 R >> >> >>\nendobj\n"
        ).encode("ascii")
        objects.append(page_dict)
        # Obj 4: Content stream
        content_obj = (
            f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode("ascii")
            + stream_content
            + b"\nendstream\nendobj\n"
        )
        objects.append(content_obj)
        # Obj 5: Font F1 (Helvetica Regular)
        objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
        # Obj 6: Font F2 (Helvetica Bold)
        objects.append(b"6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n")
        # Obj 7: Font F3 (Helvetica Oblique)
        objects.append(b"7 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>\nendobj\n")

        # Compute xref offsets
        header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        offsets = []
        cur_offset = len(header)
        for obj in objects:
            offsets.append(cur_offset)
            cur_offset += len(obj)

        xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
        for off in offsets:
            xref += f"{off:010d} 00000 n \n".encode("ascii")

        trailer = (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{cur_offset}\n%%EOF\n"
        ).encode("ascii")

        return header + b"".join(objects) + xref + trailer


def _generate_pure_pdf(
    business_profile: Dict[str, Any],
    score_result: BiasharaScoreResult,
    weekly_summaries: List[Dict[str, Any]],
    debt_summary: Dict[str, Any],
) -> bytes:
    """Generates the A4 Lender Report using the built-in PurePythonPDFBuilder."""
    pdf = PurePythonPDFBuilder(width=595.28, height=841.89)

    # 1. Background & Top Header Banner (Brand Colors: Forest Green & Dark Gold)
    pdf.rect(0, 755, 595.28, 86.89, fill_rgb=(0.0, 0.48, 0.24))  # Kenyan Green: #007A3D
    pdf.rect(0, 747, 595.28, 8, fill_rgb=(0.85, 0.65, 0.13))    # Kenyan Gold accent

    # Header Titles
    pdf.text(36, 805, "BIASHARA SCORE (KENYA)", font="F2", size=20, fill_rgb=(1.0, 1.0, 1.0))
    pdf.text(36, 785, "Lender-Ready Financial Intelligence & Credit Verification Report", font="F1", size=10, fill_rgb=(0.9, 0.95, 0.9))
    pdf.text(36, 765, "Standardized MSME Credit Assessment for Commercial Banks & SACCOs", font="F3", size=8.5, fill_rgb=(0.8, 0.9, 0.8))

    # Verification Badge on Header Right
    pdf.rect(430, 765, 130, 48, fill_rgb=(1.0, 1.0, 1.0), stroke_rgb=(0.85, 0.65, 0.13), line_width=1.5)
    pdf.text(442, 796, "VERIFIED REPORT", font="F2", size=9, fill_rgb=(0.0, 0.48, 0.24))
    pdf.text(442, 782, f"ID: {business_profile.get('business_id', 'BIZ_001')[:14]}", font="F1", size=7.5, fill_rgb=(0.3, 0.3, 0.3))
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pdf.text(442, 770, f"Date: {now_str[:16]}", font="F1", size=7, fill_rgb=(0.4, 0.4, 0.4))

    # 2. Business Profile Card
    pdf.rect(36, 665, 523.28, 70, fill_rgb=(0.97, 0.98, 0.99), stroke_rgb=(0.82, 0.86, 0.9), line_width=1.0)
    pdf.text(48, 718, "BUSINESS IDENTIFICATION & STORE DETAILS", font="F2", size=9.5, fill_rgb=(0.15, 0.25, 0.4))

    shop_name = business_profile.get("shop_name", "Local Duka / Retail Enterprise")
    owner_name = business_profile.get("owner_name", "Business Owner")
    phone = business_profile.get("owner_phone", "N/A")
    till = business_profile.get("till_number") or "N/A"

    pdf.text(48, 698, f"Shop Name: {shop_name}", font="F2", size=10, fill_rgb=(0.1, 0.1, 0.1))
    pdf.text(48, 680, f"Owner / Operator: {owner_name}", font="F1", size=9, fill_rgb=(0.25, 0.25, 0.25))

    pdf.text(320, 698, f"M-Pesa Till / Paybill: {till}", font="F1", size=9, fill_rgb=(0.25, 0.25, 0.25))
    pdf.text(320, 680, f"Registered Phone: {phone}", font="F1", size=9, fill_rgb=(0.25, 0.25, 0.25))

    # 3. Score & Creditworthiness Summary Banner
    tier = score_result.tier or "Bronze"
    total_score = score_result.total_score

    # Tier color logic
    if tier.lower() == "gold":
        tier_bg = (0.98, 0.95, 0.85)
        tier_border = (0.85, 0.65, 0.13)
        tier_text_col = (0.55, 0.4, 0.0)
    elif tier.lower() == "silver":
        tier_bg = (0.93, 0.95, 0.98)
        tier_border = (0.6, 0.7, 0.8)
        tier_text_col = (0.2, 0.35, 0.55)
    else:
        tier_bg = (0.98, 0.94, 0.9)
        tier_border = (0.8, 0.5, 0.3)
        tier_text_col = (0.5, 0.25, 0.1)

    pdf.rect(36, 560, 523.28, 92, fill_rgb=tier_bg, stroke_rgb=tier_border, line_width=1.5)

    # Score Big Badge
    pdf.rect(48, 570, 110, 72, fill_rgb=(1.0, 1.0, 1.0), stroke_rgb=tier_border, line_width=1.0)
    pdf.text(68, 622, f"{total_score}", font="F2", size=28, fill_rgb=tier_text_col)
    pdf.text(105, 626, "/100", font="F1", size=11, fill_rgb=(0.5, 0.5, 0.5))
    pdf.text(66, 598, f"TIER: {tier.upper()}", font="F2", size=9.5, fill_rgb=tier_text_col)
    pdf.text(58, 580, "Credit Rating", font="F3", size=7.5, fill_rgb=(0.5, 0.5, 0.5))

    # 4 Pillar Breakdown Sub-cards
    pdf.text(175, 634, "EVALUATION PILLARS BREAKDOWN", font="F2", size=10, fill_rgb=(0.15, 0.2, 0.3))

    pillars = [
        ("Cashflow Consistency", f"{score_result.consistency_score} / 30", 175, 608),
        ("Revenue Volume", f"{score_result.growth_score} / 25", 175, 584),
        ("Operating Margin", f"{score_result.expense_ratio_score} / 25", 360, 608),
        ("Debt Discipline", f"{score_result.debt_recovery_score} / 20", 360, 584),
    ]
    for label, val, px, py in pillars:
        pdf.text(px, py, f"* {label}:", font="F1", size=9, fill_rgb=(0.2, 0.2, 0.2))
        pdf.text(px + 120, py, val, font="F2", size=9, fill_rgb=(0.05, 0.4, 0.2))

    # 4. Weekly Financial Performance Table
    pdf.rect(36, 420, 523.28, 128, fill_rgb=(1.0, 1.0, 1.0), stroke_rgb=(0.8, 0.8, 0.8), line_width=1.0)
    pdf.rect(36, 523, 523.28, 25, fill_rgb=(0.0, 0.48, 0.24))
    pdf.text(48, 532, "HISTORICAL CASHFLOW PERFORMANCE (TRAILING WEEKS)", font="F2", size=9, fill_rgb=(1.0, 1.0, 1.0))

    # Table Column Headers
    headers = [("Week", 48), ("Gross Sales (KSh)", 135), ("Operating Spend", 255), ("Est. Profit (KSh)", 375), ("Margin", 485)]
    pdf.rect(36, 503, 523.28, 20, fill_rgb=(0.94, 0.95, 0.96))
    for title, col_x in headers:
        pdf.text(col_x, 509, title, font="F2", size=8, fill_rgb=(0.2, 0.2, 0.2))

    # Table Rows
    displayed_weeks = weekly_summaries[-4:] if weekly_summaries else []
    row_y = 485
    for i, w in enumerate(displayed_weeks):
        bg_col = (0.98, 0.98, 0.98) if i % 2 == 1 else (1.0, 1.0, 1.0)
        pdf.rect(36, row_y - 4, 523.28, 18, fill_rgb=bg_col)

        w_label = str(w.get("week_label", f"W0{i+1}"))
        sales_val = float(w.get("gross_sales", 0.0))
        exp_val = float(w.get("operating_expenses", 0.0))
        profit_val = float(w.get("estimated_profit", 0.0))
        margin_val = float(w.get("profit_margin_pct", 0.0))

        pdf.text(48, row_y, w_label, font="F1", size=8, fill_rgb=(0.2, 0.2, 0.2))
        pdf.text(135, row_y, f"{sales_val:,.2f}", font="F1", size=8, fill_rgb=(0.1, 0.1, 0.1))
        pdf.text(255, row_y, f"{exp_val:,.2f}", font="F1", size=8, fill_rgb=(0.3, 0.3, 0.3))
        pdf.text(375, row_y, f"{profit_val:,.2f}", font="F2", size=8, fill_rgb=(0.0, 0.45, 0.15) if profit_val >= 0 else (0.7, 0.1, 0.1))
        pdf.text(485, row_y, f"{margin_val:.1f}%", font="F1", size=8, fill_rgb=(0.2, 0.2, 0.2))

        row_y -= 19

    # 5. Customer Credit Discipline & Kitabu ya Deni Metrics
    pdf.rect(36, 310, 523.28, 98, fill_rgb=(0.98, 0.99, 1.0), stroke_rgb=(0.78, 0.82, 0.88), line_width=1.0)
    pdf.text(48, 390, "CUSTOMER CREDIT PORTFOLIO & DEBT RECOVERY DISCIPLINE", font="F2", size=9.5, fill_rgb=(0.15, 0.25, 0.45))

    tot_out = float(debt_summary.get("total_outstanding_amount", 0.0))
    tot_rec = float(debt_summary.get("total_cleared_amount", 0.0))
    rec_rate = float(debt_summary.get("recovery_rate_pct", 0.0))
    delinq = int(debt_summary.get("delinquent_count", 0))

    pdf.text(48, 368, f"* Total Debt Recovered: KSh {tot_rec:,.2f}", font="F1", size=8.5, fill_rgb=(0.1, 0.4, 0.1))
    pdf.text(48, 350, f"* Outstanding Customer Debt: KSh {tot_out:,.2f}", font="F1", size=8.5, fill_rgb=(0.6, 0.2, 0.1))
    pdf.text(48, 332, f"* Overdue / Delinquent Customers: {delinq}", font="F1", size=8.5, fill_rgb=(0.6, 0.1, 0.1) if delinq > 0 else (0.2, 0.5, 0.2))

    pdf.text(320, 368, f"* Overall Recovery Rate: {rec_rate:.1f}%", font="F2", size=9, fill_rgb=(0.0, 0.4, 0.2))
    pdf.text(320, 350, f"* 4-Wk Average Turnover: KSh {score_result.weekly_turnover_avg:,.2f}", font="F1", size=8.5, fill_rgb=(0.2, 0.2, 0.2))
    pdf.text(320, 332, f"* 4-Wk Average Net Profit: KSh {score_result.weekly_profit_avg:,.2f}", font="F1", size=8.5, fill_rgb=(0.05, 0.4, 0.15))

    # 6. Actionable Improvement Insights
    pdf.rect(36, 175, 523.28, 123, fill_rgb=(1.0, 1.0, 1.0), stroke_rgb=(0.85, 0.85, 0.85), line_width=1.0)
    pdf.rect(36, 278, 523.28, 20, fill_rgb=(0.95, 0.96, 0.97))
    pdf.text(48, 284, "LENDER NOTES & ACTIONABLE INSIGHTS", font="F2", size=9, fill_rgb=(0.2, 0.2, 0.2))

    tip_y = 260
    tips = score_result.actionable_tips or [
        "Maintain consistent daily sales deposits to reinforce working capital liquidity.",
        "Ensure prompt follow-up on debts exceeding 14 days to maximize recovery marks."
    ]
    for tip in tips[:4]:
        # Wrap tip if too long
        if len(tip) > 105:
            part1 = tip[:100]
            part2 = "  " + tip[100:]
            pdf.text(48, tip_y, f"> {part1}", font="F1", size=8, fill_rgb=(0.2, 0.2, 0.2))
            tip_y -= 12
            pdf.text(48, tip_y, part2, font="F1", size=8, fill_rgb=(0.2, 0.2, 0.2))
        else:
            pdf.text(48, tip_y, f"> {tip}", font="F1", size=8, fill_rgb=(0.2, 0.2, 0.2))
        tip_y -= 14

    # 7. Verification Seal & Legal Sign-Off Footer
    pdf.rect(36, 50, 523.28, 115, fill_rgb=(0.98, 0.98, 0.98), stroke_rgb=(0.8, 0.8, 0.8), line_width=1.0)
    pdf.text(48, 148, "LENDER VERIFICATION & SACCO UNDERWRITING SIGN-OFF", font="F2", size=8.5, fill_rgb=(0.1, 0.2, 0.35))
    pdf.text(48, 134, "This score was objectively computed directly from Safaricom M-Pesa verified transaction records.", font="F1", size=7.5, fill_rgb=(0.4, 0.4, 0.4))

    # Signature blocks
    pdf.line(48, 80, 240, 80, stroke_rgb=(0.5, 0.5, 0.5), line_width=0.8)
    pdf.text(48, 68, "Loan Officer Signature / Stamp", font="F1", size=7, fill_rgb=(0.4, 0.4, 0.4))

    pdf.line(320, 80, 510, 80, stroke_rgb=(0.5, 0.5, 0.5), line_width=0.8)
    pdf.text(320, 68, "Micro-Business Applicant Signature", font="F1", size=7, fill_rgb=(0.4, 0.4, 0.4))

    # Bottom disclaimer
    pdf.text(36, 32, "Confidential Document * Biashara Score Kenya * Powered by Pure Python & AWS Serverless * Valid for 30 Days from Issuance", font="F3", size=7, fill_rgb=(0.55, 0.55, 0.55))

    return pdf.build()


def _generate_reportlab_pdf(
    business_profile: Dict[str, Any],
    score_result: BiasharaScoreResult,
    weekly_summaries: List[Dict[str, Any]],
    debt_summary: Dict[str, Any],
) -> bytes:
    """Fallback generator using standard ReportLab canvas if library is present."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, pageCompression=0)
    width, height = A4

    # Header Banner
    c.setFillColor(colors.HexColor("#007A3D"))
    c.rect(0, height - 90, width, 90, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#D4AF37"))
    c.rect(0, height - 95, width, 5, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(36, height - 45, "BIASHARA SCORE (KENYA)")
    c.setFont("Helvetica", 9)
    c.drawString(36, height - 62, "Lender-Ready Financial Intelligence & Credit Verification Report")

    # Business Box
    c.setFillColor(colors.HexColor("#F8F9FA"))
    c.rect(36, height - 165, width - 72, 60, stroke=1, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(48, height - 125, f"Shop: {business_profile.get('shop_name', 'Duka')}")
    c.setFont("Helvetica", 9)
    c.drawString(48, height - 145, f"Owner: {business_profile.get('owner_name', 'Trader')} | Till: {business_profile.get('till_number', 'N/A')}")

    # Score Box
    c.setFillColor(colors.HexColor("#EBF3EE"))
    c.rect(36, height - 250, width - 72, 75, stroke=1, fill=1)
    c.setFillColor(colors.HexColor("#007A3D"))
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 215, f"{score_result.total_score}/100")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, height - 235, f"Tier: {score_result.tier}")

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 8.5)
    c.drawString(170, height - 200, f"Consistency: {score_result.consistency_score}/30 | Revenue: {score_result.growth_score}/25")
    c.drawString(170, height - 220, f"Margin: {score_result.expense_ratio_score}/25 | Debt Recovery: {score_result.debt_recovery_score}/20")

    # Financial Performance
    c.setFont("Helvetica-Bold", 10)
    c.drawString(36, height - 275, "Historical Cashflow Performance")
    y = height - 295
    c.setFont("Helvetica-Bold", 8)
    c.drawString(48, y, "Week")
    c.drawString(120, y, "Gross Sales")
    c.drawString(220, y, "Expenses")
    c.drawString(320, y, "Est. Profit")
    c.drawString(420, y, "Margin")

    y -= 15
    c.setFont("Helvetica", 8)
    for w in weekly_summaries[-4:]:
        c.drawString(48, y, str(w.get("week_label", "")))
        c.drawString(120, y, f"KSh {float(w.get('gross_sales', 0)):,.2f}")
        c.drawString(220, y, f"KSh {float(w.get('operating_expenses', 0)):,.2f}")
        c.drawString(320, y, f"KSh {float(w.get('estimated_profit', 0)):,.2f}")
        c.drawString(420, y, f"{float(w.get('profit_margin_pct', 0)):.1f}%")
        y -= 15

    # Debt Summary
    y -= 10
    c.setFont("Helvetica-Bold", 10)
    c.drawString(36, y, "Customer Debt & Recovery Metrics")
    y -= 20
    c.setFont("Helvetica", 8.5)
    tot_out = float(debt_summary.get("total_outstanding_amount", 0.0))
    tot_rec = float(debt_summary.get("total_cleared_amount", 0.0))
    rec_pct = float(debt_summary.get("recovery_rate_pct", 0.0))
    c.drawString(48, y, f"Total Recovered: KSh {tot_rec:,.2f} | Outstanding: KSh {tot_out:,.2f} | Recovery Rate: {rec_pct:.1f}%")

    # Tips
    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(36, y, "Actionable Recommendations")
    y -= 15
    c.setFont("Helvetica", 8)
    for tip in (score_result.actionable_tips or [])[:3]:
        c.drawString(48, y, f"- {tip[:100]}")
        y -= 14

    # Footer
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.gray)
    c.drawString(36, 40, "Confidential Verification Document * Biashara Score Kenya * Standardized MSME Assessment")

    c.showPage()
    c.save()
    return buf.getvalue()


def generate_lender_pdf(
    business_profile: Dict[str, Any],
    score_result: BiasharaScoreResult,
    weekly_summaries: List[Dict[str, Any]],
    debt_summary: Dict[str, Any],
) -> bytes:
    """
    Generates a single-page A4 PDF financial verification report.
    Returns binary PDF bytes (b'%PDF-...').
    Prefers ReportLab if installed; otherwise uses high-performance PurePythonPDFBuilder.
    """
    if HAS_REPORTLAB:
        return _generate_reportlab_pdf(business_profile, score_result, weekly_summaries, debt_summary)
    return _generate_pure_pdf(business_profile, score_result, weekly_summaries, debt_summary)
