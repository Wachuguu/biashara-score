"""
Lender-Ready PDF Report Generator (Pure Python)
Generates a single-page A4 financial business cashflow summary report for Kenyan SACCOs and microfinance lenders.
Zero OS-level binary dependencies. Works 100% offline without external services.
"""
from typing import Dict, Any, List, Optional
import io
import re
from datetime import datetime, timezone
from .models import BiasharaScoreResult
from .summary import _parse_completion_time

# Check if ReportLab is installed in the environment
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.graphics.shapes import Drawing, String, Rect, Line
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics import renderPDF
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


DISCLAIMER_FOOTER = (
    "Prepared by Biashara Score from an uploaded M-Pesa statement. "
    "Figures are not verified by Safaricom or any financial institution."
)

TIER_THRESHOLDS_LINE = "Gold 80+, Silver 65-79, Bronze 50-64, Needs Improvement below 50"


def _escape_pdf_text(text: str) -> str:
    """Escapes special characters in PDF string literals and removes non-ASCII."""
    clean = str(text).replace("—", "-").replace("–", "-").replace("•", "*")
    clean = clean.encode("ascii", "replace").decode("ascii")
    return clean.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _is_zero_debt(score_result: BiasharaScoreResult, debt_summary: Dict[str, Any]) -> bool:
    """Determines whether the store has zero customer debts recorded."""
    if score_result.debt_recovery_rate is None:
        return True
    tot_out = float(debt_summary.get("total_outstanding_amount", 0.0))
    tot_rec = float(debt_summary.get("total_cleared_amount", 0.0))
    tot_owed = float(debt_summary.get("total_owed", tot_out + tot_rec))
    if tot_owed <= 0.0 and tot_out <= 0.0 and tot_rec <= 0.0:
        return True
    return False


def extract_report_facts(
    score_result: BiasharaScoreResult,
    weekly_summaries: List[Dict[str, Any]],
    transactions: Optional[List[Any]] = None,
    facts_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Extracts summary facts for the facts block:
    - report_date
    - period_covered (first and last transaction date)
    - transaction_count
    - avg_sales_amount
    - active_trading_days
    """
    if facts_override:
        return facts_override

    if score_result.computed_at:
        report_date = score_result.computed_at.split("T")[0]
    else:
        report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if transactions:
        valid_times = []
        sales_amounts = []
        active_dates = set()
        sales_categories = {"SALES", "DEBT_RECOVERY"}

        for t in transactions:
            dt_str = getattr(t, "completion_time", None) or (t.get("completion_time") if isinstance(t, dict) else "")
            direction = getattr(t, "direction", None) or (t.get("direction") if isinstance(t, dict) else "")
            if hasattr(direction, "value"):
                direction = direction.value
            category = getattr(t, "category", None) or (t.get("category") if isinstance(t, dict) else "")
            if hasattr(category, "value"):
                category = category.value
            amount = float(getattr(t, "amount", 0.0) or (t.get("amount", 0.0) if isinstance(t, dict) else 0.0))

            dt = _parse_completion_time(dt_str)
            if dt:
                valid_times.append(dt)

            if str(direction).upper() == "IN" and (str(category).upper() in sales_categories):
                sales_amounts.append(amount)
                if dt:
                    active_dates.add(dt.strftime("%Y-%m-%d"))

        if valid_times:
            min_dt = min(valid_times)
            max_dt = max(valid_times)
            period_covered = f"{min_dt.strftime('%Y-%m-%d')} to {max_dt.strftime('%Y-%m-%d')}"
        else:
            period_covered = "N/A"

        tx_count = len(transactions)
        avg_sales = (sum(sales_amounts) / len(sales_amounts)) if sales_amounts else 0.0
        active_days = len(active_dates) if active_dates else (len(set(d.strftime("%Y-%m-%d") for d in valid_times)) if valid_times else 0)

        return {
            "report_date": report_date,
            "period_covered": period_covered,
            "transaction_count": tx_count,
            "avg_sales_amount": avg_sales,
            "active_trading_days": active_days,
        }

    # Fallback when transactions list is not provided
    if weekly_summaries:
        start_date = weekly_summaries[0].get("start_date", "")
        end_date = weekly_summaries[-1].get("end_date", "")
        period_covered = f"{start_date} to {end_date}" if start_date and end_date else "Last 4 weeks"
        total_tx = sum(int(w.get("transaction_count", 0)) for w in weekly_summaries)
        total_sales = sum(float(w.get("gross_sales", 0.0)) for w in weekly_summaries)
        avg_sales = (total_sales / total_tx) if total_tx > 0 else 0.0
        active_days = sum(int(w.get("active_trading_days", 0)) for w in weekly_summaries)
    else:
        period_covered = "N/A"
        total_tx = 0
        avg_sales = 0.0
        active_days = 0

    return {
        "report_date": report_date,
        "period_covered": period_covered,
        "transaction_count": total_tx,
        "avg_sales_amount": avg_sales,
        "active_trading_days": active_days,
    }


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
    facts: Dict[str, Any],
) -> bytes:
    """Generates the single-page A4 report using the pure Python vector builder."""
    pdf = PurePythonPDFBuilder(width=595.28, height=841.89)

    # 1. Background & Top Header Banner
    pdf.rect(0, 765, 595.28, 76.89, fill_rgb=(0.0, 0.48, 0.24))
    pdf.rect(0, 761, 595.28, 4, fill_rgb=(0.85, 0.65, 0.13))

    pdf.text(36, 808, "BIASHARA SCORE (KENYA)", font="F2", size=18, fill_rgb=(1.0, 1.0, 1.0))
    pdf.text(36, 792, "Lender-Ready Financial Intelligence & Business Cashflow Summary", font="F1", size=9, fill_rgb=(0.9, 0.95, 0.9))
    pdf.text(36, 778, "Standardized MSME Credit Assessment for Commercial Banks & SACCOs", font="F3", size=7.5, fill_rgb=(0.8, 0.9, 0.8))

    # Badge on Header Right
    pdf.rect(440, 770, 120, 42, fill_rgb=(1.0, 1.0, 1.0), stroke_rgb=(0.85, 0.65, 0.13), line_width=1.0)
    pdf.text(450, 798, "CASHFLOW REPORT", font="F2", size=8.5, fill_rgb=(0.0, 0.48, 0.24))
    biz_id = str(business_profile.get("business_id", "BIZ_001"))[:12]
    pdf.text(450, 786, f"ID: {biz_id}", font="F1", size=7, fill_rgb=(0.3, 0.3, 0.3))
    pdf.text(450, 776, f"Date: {facts['report_date']}", font="F1", size=6.5, fill_rgb=(0.4, 0.4, 0.4))

    # 2. Business Profile Card
    pdf.rect(36, 706, 523.28, 48, fill_rgb=(0.97, 0.98, 0.99), stroke_rgb=(0.8, 0.84, 0.88), line_width=1.0)
    pdf.text(46, 740, "BUSINESS IDENTIFICATION & STORE DETAILS", font="F2", size=8.5, fill_rgb=(0.15, 0.25, 0.4))
    shop_name = business_profile.get("shop_name", "Local Duka")
    owner_name = business_profile.get("owner_name", "Trader")
    phone = business_profile.get("owner_phone", "N/A")
    till = business_profile.get("till_number") or "N/A"
    pdf.text(46, 726, f"Shop Name: {shop_name}", font="F2", size=8, fill_rgb=(0.1, 0.1, 0.1))
    pdf.text(300, 726, f"M-Pesa Till / Paybill: {till}", font="F1", size=8, fill_rgb=(0.25, 0.25, 0.25))
    pdf.text(46, 712, f"Owner / Operator: {owner_name}", font="F1", size=8, fill_rgb=(0.25, 0.25, 0.25))
    pdf.text(300, 712, f"Registered Phone: {phone}", font="F1", size=8, fill_rgb=(0.25, 0.25, 0.25))

    # 3. Facts Block (under shop box)
    pdf.rect(36, 658, 523.28, 42, fill_rgb=(0.94, 0.96, 0.98), stroke_rgb=(0.75, 0.8, 0.86), line_width=1.0)
    pdf.text(46, 688, "ACTIVITY & STATEMENT FACTS", font="F2", size=8, fill_rgb=(0.1, 0.2, 0.35))
    pdf.text(46, 674, f"Report Date: {facts['report_date']}", font="F1", size=7.5, fill_rgb=(0.2, 0.2, 0.2))
    pdf.text(190, 674, f"Transactions Analysed: {facts['transaction_count']}", font="F1", size=7.5, fill_rgb=(0.2, 0.2, 0.2))
    pdf.text(360, 674, f"Active Trading Days: {facts['active_trading_days']}", font="F1", size=7.5, fill_rgb=(0.2, 0.2, 0.2))
    pdf.text(46, 662, f"Data Period Covered: {facts['period_covered']}", font="F1", size=7.5, fill_rgb=(0.2, 0.2, 0.2))
    pdf.text(360, 662, f"Avg Sales Transaction: KSh {facts['avg_sales_amount']:,.2f}", font="F1", size=7.5, fill_rgb=(0.2, 0.2, 0.2))

    # 4. Score & Creditworthiness Summary Banner
    tier = score_result.tier or "Bronze"
    total_score = score_result.total_score
    if tier.lower() == "gold":
        tier_bg = (0.99, 0.98, 0.88)
        tier_border = (0.85, 0.65, 0.13)
        tier_text_col = (0.55, 0.4, 0.0)
    elif tier.lower() == "silver":
        tier_bg = (0.94, 0.96, 0.98)
        tier_border = (0.6, 0.7, 0.8)
        tier_text_col = (0.2, 0.35, 0.55)
    else:
        tier_bg = (0.99, 0.95, 0.92)
        tier_border = (0.8, 0.5, 0.3)
        tier_text_col = (0.5, 0.25, 0.1)

    pdf.rect(36, 580, 523.28, 72, fill_rgb=tier_bg, stroke_rgb=tier_border, line_width=1.0)
    pdf.rect(44, 586, 88, 60, fill_rgb=(1.0, 1.0, 1.0), stroke_rgb=tier_border, line_width=1.0)
    pdf.text(54, 624, f"{total_score}/100", font="F2", size=20, fill_rgb=tier_text_col)
    pdf.text(54, 608, f"Tier: {tier}", font="F2", size=8.5, fill_rgb=tier_text_col)
    pdf.text(54, 594, "Credit Rating", font="F3", size=6.5, fill_rgb=(0.5, 0.5, 0.5))

    pdf.text(146, 638, "EVALUATION PILLARS BREAKDOWN", font="F2", size=8.5, fill_rgb=(0.15, 0.2, 0.3))
    pdf.text(146, 622, f"Cashflow Consistency: {score_result.consistency_score}/30", font="F1", size=7.5, fill_rgb=(0.2, 0.2, 0.2))
    pdf.text(340, 622, f"Revenue Volume: {score_result.growth_score}/25", font="F1", size=7.5, fill_rgb=(0.2, 0.2, 0.2))
    pdf.text(146, 608, f"Operating Margin: {score_result.expense_ratio_score}/25", font="F1", size=7.5, fill_rgb=(0.2, 0.2, 0.2))
    pdf.text(340, 608, f"Debt Discipline: {score_result.debt_recovery_score}/20", font="F1", size=7.5, fill_rgb=(0.2, 0.2, 0.2))
    pdf.text(146, 590, f"Tier Thresholds: {TIER_THRESHOLDS_LINE}", font="F3", size=7, fill_rgb=(0.35, 0.35, 0.35))

    # 5. Table: Last 4 weeks
    pdf.text(36, 566, "Last 4 weeks", font="F2", size=9.5, fill_rgb=(0.0, 0.48, 0.24))
    pdf.rect(36, 540, 523.28, 14, fill_rgb=(0.88, 0.91, 0.94))
    headers = [("Week", 46), ("Gross Sales (KSh)", 135), ("Operating Spend (KSh)", 245), ("Est. Profit (KSh)", 360), ("Margin", 475)]
    for title, col_x in headers:
        pdf.text(col_x, 544, title, font="F2", size=7.5, fill_rgb=(0.15, 0.15, 0.15))

    displayed_weeks = weekly_summaries[-4:] if weekly_summaries else []
    row_y = 526
    for i, w in enumerate(displayed_weeks):
        if i % 2 == 1:
            pdf.rect(36, row_y - 3, 523.28, 14, fill_rgb=(0.97, 0.98, 0.99))
        w_label = str(w.get("week_label", f"W0{i+1}"))
        sales_val = float(w.get("gross_sales", 0.0))
        exp_val = float(w.get("operating_expenses", 0.0))
        profit_val = float(w.get("estimated_profit", 0.0))
        margin_val = float(w.get("profit_margin_pct", 0.0))

        pdf.text(46, row_y, w_label, font="F1", size=7.5, fill_rgb=(0.2, 0.2, 0.2))
        pdf.text(135, row_y, f"KSh {sales_val:,.2f}", font="F1", size=7.5, fill_rgb=(0.1, 0.1, 0.1))
        pdf.text(245, row_y, f"KSh {exp_val:,.2f}", font="F1", size=7.5, fill_rgb=(0.3, 0.3, 0.3))
        pdf.text(360, row_y, f"KSh {profit_val:,.2f}", font="F2", size=7.5, fill_rgb=(0.0, 0.45, 0.15) if profit_val >= 0 else (0.7, 0.1, 0.1))
        pdf.text(475, row_y, f"{margin_val:.1f}%", font="F1", size=7.5, fill_rgb=(0.2, 0.2, 0.2))
        row_y -= 14

    pdf.rect(36, 476, 523.28, 78, stroke_rgb=(0.8, 0.84, 0.88), line_width=1.0)

    # 6. Weekly Gross Sales Bar Chart
    pdf.text(36, 464, "Weekly Gross Sales Trend (KSh)", font="F2", size=9, fill_rgb=(0.1, 0.15, 0.2))
    chart_y_base = 372
    chart_h_max = 66
    chart_weeks = [str(w.get("week_label", f"W0{i+1}")) for i, w in enumerate(displayed_weeks)] if displayed_weeks else ["No Data"]
    chart_sales = [float(w.get("gross_sales", 0.0)) for w in displayed_weeks] if displayed_weeks else [0.0]
    max_val = max(chart_sales) if max(chart_sales) > 0 else 10000.0

    pdf.line(90, chart_y_base, 510, chart_y_base, stroke_rgb=(0.7, 0.7, 0.7), line_width=1.0)
    pdf.line(90, chart_y_base, 90, chart_y_base + chart_h_max + 10, stroke_rgb=(0.7, 0.7, 0.7), line_width=1.0)
    pdf.text(40, chart_y_base + chart_h_max, f"KSh {int(max_val):,}", font="F1", size=6.5, fill_rgb=(0.4, 0.4, 0.4))
    pdf.text(40, chart_y_base, "KSh 0", font="F1", size=6.5, fill_rgb=(0.4, 0.4, 0.4))

    bar_w = 42
    n_bars = len(chart_sales)
    avail_w = 410.0
    gap = (avail_w - (n_bars * bar_w)) / (n_bars + 1)
    for idx, (w_lbl, s_val) in enumerate(zip(chart_weeks, chart_sales)):
        bx = 90 + gap + idx * (bar_w + gap)
        bh = (s_val / max_val) * chart_h_max if max_val > 0 else 0
        pdf.rect(bx, chart_y_base, bar_w, bh, fill_rgb=(0.0, 0.48, 0.24))
        pdf.text(bx + 2, chart_y_base - 10, w_lbl, font="F1", size=7, fill_rgb=(0.3, 0.3, 0.3))
        if s_val > 0:
            pdf.text(bx, chart_y_base + bh + 3, f"KSh {int(s_val):,}", font="F1", size=6, fill_rgb=(0.05, 0.4, 0.15))

    # 7. Customer Credit & Debt Recovery Discipline
    pdf.rect(36, 294, 523.28, 54, fill_rgb=(0.97, 0.98, 0.99), stroke_rgb=(0.8, 0.84, 0.88), line_width=1.0)
    pdf.text(46, 334, "CUSTOMER CREDIT & DEBT RECOVERY DISCIPLINE", font="F2", size=8.5, fill_rgb=(0.15, 0.25, 0.45))

    tot_out = float(debt_summary.get("total_outstanding_amount", 0.0))
    tot_rec = float(debt_summary.get("total_cleared_amount", 0.0))
    delinq = int(debt_summary.get("delinquent_count", 0))

    if _is_zero_debt(score_result, debt_summary):
        pdf.text(46, 318, "No customer credit recorded", font="F2", size=8.5, fill_rgb=(0.1, 0.1, 0.1))
        pdf.text(46, 305, "The business currently operates on cash and upfront mobile payments with zero customer credit ledger entries.", font="F1", size=7.5, fill_rgb=(0.35, 0.35, 0.35))
    else:
        rec_pct = float(score_result.debt_recovery_rate if score_result.debt_recovery_rate is not None else debt_summary.get("recovery_rate_pct", 0.0))
        pdf.text(46, 318, f"Total Recovered: KSh {tot_rec:,.2f}  |  Outstanding Debt: KSh {tot_out:,.2f}  |  Recovery Rate: {rec_pct:.1f}%", font="F1", size=8, fill_rgb=(0.1, 0.1, 0.1))
        pdf.text(46, 305, f"Overdue Customers: {delinq}  |  4-Wk Turnover: KSh {score_result.weekly_turnover_avg:,.2f}  |  4-Wk Profit: KSh {score_result.weekly_profit_avg:,.2f}", font="F1", size=7.5, fill_rgb=(0.3, 0.3, 0.3))

    # 8. Actionable Business Improvement Recommendations
    pdf.rect(36, 208, 523.28, 78, fill_rgb=(1.0, 1.0, 1.0), stroke_rgb=(0.88, 0.9, 0.92), line_width=1.0)
    pdf.text(46, 272, "ACTIONABLE BUSINESS RECOMMENDATIONS", font="F2", size=8.5, fill_rgb=(0.15, 0.15, 0.15))
    tips = score_result.actionable_tips or [
        "Maintain consistent daily sales deposits to reinforce working capital liquidity.",
        "Ensure prompt follow-up on debts exceeding 14 days to maximize recovery marks.",
        "Increase inventory turnover during peak trading days."
    ]
    tip_y = 256
    for tip in tips[:3]:
        clean_tip = tip[:110]
        pdf.text(46, tip_y, f"- {clean_tip}", font="F1", size=7.5, fill_rgb=(0.25, 0.25, 0.25))
        tip_y -= 16

    # 9. Sign-off Assessment Box
    pdf.rect(36, 116, 523.28, 84, fill_rgb=(0.97, 0.98, 0.99), stroke_rgb=(0.8, 0.84, 0.88), line_width=1.0)
    pdf.text(46, 186, "LENDER ASSESSMENT & SACCO UNDERWRITING SIGN-OFF", font="F2", size=8.5, fill_rgb=(0.1, 0.2, 0.35))
    pdf.text(46, 172, "This assessment was computed directly from Safaricom M-Pesa statement records.", font="F1", size=7.5, fill_rgb=(0.4, 0.4, 0.4))
    pdf.line(46, 142, 240, 142, stroke_rgb=(0.6, 0.6, 0.6), line_width=0.8)
    pdf.text(46, 130, "Loan Officer Signature / Stamp", font="F1", size=7, fill_rgb=(0.45, 0.45, 0.45))
    pdf.line(320, 142, 514, 142, stroke_rgb=(0.6, 0.6, 0.6), line_width=0.8)
    pdf.text(320, 130, "Micro-Business Applicant Signature", font="F1", size=7, fill_rgb=(0.45, 0.45, 0.45))

    # 10. Footer Disclaimer
    pdf.text(36, 45, DISCLAIMER_FOOTER, font="F3", size=7.5, fill_rgb=(0.4, 0.4, 0.4))

    return pdf.build()


def _generate_reportlab_pdf(
    business_profile: Dict[str, Any],
    score_result: BiasharaScoreResult,
    weekly_summaries: List[Dict[str, Any]],
    debt_summary: Dict[str, Any],
    facts: Dict[str, Any],
) -> bytes:
    """Generates the single-page A4 report using ReportLab canvas and reportlab.graphics."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, pageCompression=0)
    width, height = A4

    # 1. Header Banner
    c.setFillColor(colors.HexColor("#007A3D"))
    c.rect(0, height - 76, width, 76, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#D4AF37"))
    c.rect(0, height - 80, width, 4, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(36, height - 34, "BIASHARA SCORE (KENYA)")
    c.setFont("Helvetica", 9)
    c.drawString(36, height - 50, "Lender-Ready Financial Intelligence & Business Cashflow Summary")
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(36, height - 64, "Standardized MSME Credit Assessment for Commercial Banks & SACCOs")

    # Header Right Badge
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#D4AF37"))
    c.rect(width - 150, height - 68, 114, 42, stroke=1, fill=1)
    c.setFillColor(colors.HexColor("#007A3D"))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(width - 140, height - 40, "CASHFLOW REPORT")
    c.setFillColor(colors.HexColor("#334155"))
    c.setFont("Helvetica", 7)
    biz_id = str(business_profile.get("business_id", "BIZ_001"))[:12]
    c.drawString(width - 140, height - 52, f"ID: {biz_id}")
    c.drawString(width - 140, height - 62, f"Date: {facts['report_date']}")

    # 2. Shop Box (Business Details)
    c.setFillColor(colors.HexColor("#F8FAFC"))
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.rect(36, 706, width - 72, 48, stroke=1, fill=1)
    c.setFillColor(colors.HexColor("#1E293B"))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(46, 740, "BUSINESS IDENTIFICATION & STORE DETAILS")
    c.setFont("Helvetica-Bold", 8)
    c.drawString(46, 726, f"Shop Name: {business_profile.get('shop_name', 'Local Duka')}")
    c.setFont("Helvetica", 8)
    c.drawString(300, 726, f"M-Pesa Till / Paybill: {business_profile.get('till_number') or 'N/A'}")
    c.drawString(46, 712, f"Owner / Operator: {business_profile.get('owner_name', 'Trader')}")
    c.drawString(300, 712, f"Registered Phone: {business_profile.get('owner_phone', 'N/A')}")

    # 3. Facts Block (under shop box)
    c.setFillColor(colors.HexColor("#F1F5F9"))
    c.setStrokeColor(colors.HexColor("#94A3B8"))
    c.rect(36, 658, width - 72, 42, stroke=1, fill=1)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(46, 688, "ACTIVITY & STATEMENT FACTS")
    c.setFont("Helvetica", 7.5)
    c.drawString(46, 674, f"Report Date: {facts['report_date']}")
    c.drawString(190, 674, f"Transactions Analysed: {facts['transaction_count']}")
    c.drawString(360, 674, f"Active Trading Days: {facts['active_trading_days']}")
    c.drawString(46, 662, f"Data Period Covered: {facts['period_covered']}")
    c.drawString(360, 662, f"Avg Sales Transaction: KSh {facts['avg_sales_amount']:,.2f}")

    # 4. Score Box & Tier Thresholds
    tier = score_result.tier or "Bronze"
    if tier.lower() == "gold":
        box_bg = colors.HexColor("#FEFCE8")
        box_border = colors.HexColor("#EAB308")
    elif tier.lower() == "silver":
        box_bg = colors.HexColor("#F1F5F9")
        box_border = colors.HexColor("#94A3B8")
    elif tier.lower() == "bronze":
        box_bg = colors.HexColor("#FFF7ED")
        box_border = colors.HexColor("#F97316")
    else:
        box_bg = colors.HexColor("#FEF2F2")
        box_border = colors.HexColor("#EF4444")

    c.setFillColor(box_bg)
    c.setStrokeColor(box_border)
    c.rect(36, 580, width - 72, 72, stroke=1, fill=1)

    c.setFillColor(colors.white)
    c.setStrokeColor(box_border)
    c.rect(44, 586, 88, 60, stroke=1, fill=1)

    c.setFillColor(colors.HexColor("#007A3D"))
    c.setFont("Helvetica-Bold", 20)
    c.drawString(52, 624, f"{score_result.total_score}/100")
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(52, 608, f"Tier: {score_result.tier}")
    c.setFont("Helvetica", 6.5)
    c.setFillColor(colors.HexColor("#64748B"))
    c.drawString(52, 594, "Credit Rating")

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(146, 638, "EVALUATION PILLARS BREAKDOWN")
    c.setFont("Helvetica", 7.5)
    c.drawString(146, 622, f"Cashflow Consistency: {score_result.consistency_score}/30")
    c.drawString(340, 622, f"Revenue Volume: {score_result.growth_score}/25")
    c.drawString(146, 608, f"Operating Margin: {score_result.expense_ratio_score}/25")
    c.drawString(340, 608, f"Debt Discipline: {score_result.debt_recovery_score}/20")
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawString(146, 590, f"Tier Thresholds: {TIER_THRESHOLDS_LINE}")

    # 5. Table: Last 4 weeks
    c.setFillColor(colors.HexColor("#007A3D"))
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(36, 566, "Last 4 weeks")

    c.setFillColor(colors.HexColor("#E2E8F0"))
    c.rect(36, 540, width - 72, 14, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#1E293B"))
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(46, 544, "Week")
    c.drawString(135, 544, "Gross Sales (KSh)")
    c.drawString(245, 544, "Operating Spend (KSh)")
    c.drawString(360, 544, "Est. Profit (KSh)")
    c.drawString(475, 544, "Margin")

    displayed_weeks = weekly_summaries[-4:] if weekly_summaries else []
    row_y = 526
    c.setFont("Helvetica", 7.5)
    for i, w in enumerate(displayed_weeks):
        if i % 2 == 1:
            c.setFillColor(colors.HexColor("#F8FAFC"))
            c.rect(36, row_y - 3, width - 72, 14, stroke=0, fill=1)
        w_label = str(w.get("week_label", f"W0{i+1}"))
        sales_val = float(w.get("gross_sales", 0.0))
        exp_val = float(w.get("operating_expenses", 0.0))
        profit_val = float(w.get("estimated_profit", 0.0))
        margin_val = float(w.get("profit_margin_pct", 0.0))

        c.setFillColor(colors.HexColor("#1E293B"))
        c.drawString(46, row_y, w_label)
        c.drawString(135, row_y, f"KSh {sales_val:,.2f}")
        c.drawString(245, row_y, f"KSh {exp_val:,.2f}")
        c.drawString(360, row_y, f"KSh {profit_val:,.2f}")
        c.drawString(475, row_y, f"{margin_val:.1f}%")
        row_y -= 14

    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.rect(36, 476, width - 72, 78, stroke=1, fill=0)

    # 6. Weekly Gross Sales Bar Chart (reportlab.graphics)
    c.setFillColor(colors.HexColor("#1E293B"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(36, 464, "Weekly Gross Sales Trend (KSh)")

    chart_weeks = [str(w.get("week_label", f"W0{i+1}")) for i, w in enumerate(displayed_weeks)] if displayed_weeks else ["No Data"]
    chart_sales = [float(w.get("gross_sales", 0.0)) for w in displayed_weeks] if displayed_weeks else [0.0]

    chart_drawing = Drawing(width - 72, 98)
    chart = VerticalBarChart()
    chart.x = 65
    chart.y = 18
    chart.height = 70
    chart.width = width - 72 - 80
    chart.data = [chart_sales]
    chart.categoryAxis.categoryNames = chart_weeks
    chart.categoryAxis.labels.fontSize = 8
    chart.categoryAxis.labels.dy = -10
    chart.valueAxis.valueMin = 0
    if max(chart_sales) == 0:
        chart.valueAxis.valueMax = 10000
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.labels.rightPadding = 5
    chart.valueAxis.labelTextFormat = 'KSh %d'
    chart.bars[0].fillColor = colors.HexColor("#007A3D")

    chart_drawing.add(chart)
    renderPDF.draw(chart_drawing, c, 36, 356)

    # 7. Customer Credit & Debt Recovery Discipline
    c.setFillColor(colors.HexColor("#F8FAFC"))
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.rect(36, 294, width - 72, 54, stroke=1, fill=1)
    c.setFillColor(colors.HexColor("#1E293B"))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(46, 334, "CUSTOMER CREDIT & DEBT RECOVERY DISCIPLINE")

    tot_out = float(debt_summary.get("total_outstanding_amount", 0.0))
    tot_rec = float(debt_summary.get("total_cleared_amount", 0.0))
    delinq = int(debt_summary.get("delinquent_count", 0))

    if _is_zero_debt(score_result, debt_summary):
        c.drawString(46, 318, "No customer credit recorded")
        c.setFont("Helvetica", 7.5)
        c.setFillColor(colors.HexColor("#475569"))
        c.drawString(46, 305, "The business currently operates on cash and upfront mobile payments with zero customer credit ledger entries.")
    else:
        rec_pct = float(score_result.debt_recovery_rate if score_result.debt_recovery_rate is not None else debt_summary.get("recovery_rate_pct", 0.0))
        c.setFont("Helvetica", 8)
        c.drawString(46, 318, f"Total Recovered: KSh {tot_rec:,.2f}  |  Outstanding Debt: KSh {tot_out:,.2f}  |  Recovery Rate: {rec_pct:.1f}%")
        c.drawString(46, 305, f"Overdue Customers: {delinq}  |  4-Wk Turnover: KSh {score_result.weekly_turnover_avg:,.2f}  |  4-Wk Profit: KSh {score_result.weekly_profit_avg:,.2f}")

    # 8. Actionable Business Improvement Recommendations
    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor("#E2E8F0"))
    c.rect(36, 208, width - 72, 78, stroke=1, fill=1)
    c.setFillColor(colors.HexColor("#1E293B"))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(46, 272, "ACTIONABLE BUSINESS RECOMMENDATIONS")
    tips = score_result.actionable_tips or [
        "Maintain consistent daily sales deposits to reinforce working capital liquidity.",
        "Ensure prompt follow-up on debts exceeding 14 days to maximize recovery marks.",
        "Increase inventory turnover during peak trading days."
    ]
    tip_y = 256
    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.HexColor("#334155"))
    for tip in tips[:3]:
        c.drawString(46, tip_y, f"- {tip[:110]}")
        tip_y -= 16

    # 9. Sign-off Assessment Box
    c.setFillColor(colors.HexColor("#F8FAFC"))
    c.setStrokeColor(colors.HexColor("#CBD5E1"))
    c.rect(36, 116, width - 72, 84, stroke=1, fill=1)
    c.setFillColor(colors.HexColor("#1E293B"))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(46, 186, "LENDER ASSESSMENT & SACCO UNDERWRITING SIGN-OFF")
    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawString(46, 172, "This assessment was computed directly from Safaricom M-Pesa statement records.")

    c.setStrokeColor(colors.HexColor("#94A3B8"))
    c.line(46, 142, 240, 142)
    c.line(320, 142, 514, 142)
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#64748B"))
    c.drawString(46, 130, "Loan Officer Signature / Stamp")
    c.drawString(320, 130, "Micro-Business Applicant Signature")

    # 10. Footer Disclaimer
    c.setFont("Helvetica-Oblique", 7.5)
    c.setFillColor(colors.HexColor("#64748B"))
    c.drawCentredString(width / 2.0, 45, DISCLAIMER_FOOTER)

    c.showPage()
    c.save()
    return buf.getvalue()


def generate_lender_pdf(
    business_profile: Dict[str, Any],
    score_result: BiasharaScoreResult,
    weekly_summaries: List[Dict[str, Any]],
    debt_summary: Dict[str, Any],
    facts: Optional[Dict[str, Any]] = None,
    transactions: Optional[List[Any]] = None,
) -> bytes:
    """
    Generates a single-page A4 PDF financial business cashflow summary report.
    Returns binary PDF bytes (b'%PDF-...').
    Prefers ReportLab if installed; otherwise uses high-performance PurePythonPDFBuilder.
    """
    resolved_facts = extract_report_facts(
        score_result=score_result,
        weekly_summaries=weekly_summaries,
        transactions=transactions,
        facts_override=facts,
    )

    if HAS_REPORTLAB:
        return _generate_reportlab_pdf(business_profile, score_result, weekly_summaries, debt_summary, resolved_facts)
    return _generate_pure_pdf(business_profile, score_result, weekly_summaries, debt_summary, resolved_facts)
