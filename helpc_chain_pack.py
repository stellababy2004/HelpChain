# This script generates the requested HelpChain Financial Pack:
# - Two logos (BG and EN) as PNG with transparent background
# - An Excel financial model with two scenarios (Realistic & Aggressive) and a Summary sheet
# - Two PDF reports (BG & EN) in business style with the logo, executive summary, tables & charts
# - Packs everything into a single ZIP archive named HelpChain_Financial_Pack_2025.zip
#
# You can re-run this script to refresh the files if needed.

import os
import zipfile
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image, ImageDraw, ImageFont

# ------------- PARAMETERS (from user) -------------
initial_capital = 500
salary_per_month = 1000
marketing_per_month = 100
volunteer_aggr_per_month = 200  # only for aggressive scenario
include_admin_costs = (
    False  # as per user: hosting already paid; keep other admin costs out
)
glow_hex = "#33E0FF"
dark_blue = "#0047AB"
light_blue = "#00C2FF"

# ------------- OUTPUT PATHS -------------
base_dir = os.path.abspath(".")  # Save in current directory
pack_dir = os.path.join(base_dir, "HelpChain_Financial_Pack_2025")
os.makedirs(pack_dir, exist_ok=True)

logo_bg_path = os.path.join(pack_dir, "helpchain_logo_bg.png")
logo_en_path = os.path.join(pack_dir, "helpchain_logo_en.png")
xlsx_path = os.path.join(pack_dir, "HelpChain_Financial_Model.xlsx")
pdf_bg_path = os.path.join(pack_dir, "HelpChain_Financial_Report_BG.pdf")
pdf_en_path = os.path.join(pack_dir, "HelpChain_Financial_Report_EN.pdf")
zip_path = os.path.join(base_dir, "HelpChain_Financial_Pack_2025.zip")


# ------------- HELPERS -------------
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def create_compact_logo(path, tagline=None):
    """Create a compact square logo (600x600) with chain symbol and glow, transparent background."""
    size = 600
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Colors
    dark_rgb = hex_to_rgb(dark_blue)
    light_rgb = hex_to_rgb(light_blue)
    glow_rgb = hex_to_rgb(glow_hex)

    # Draw subtle glow around central area
    # We'll draw a soft radial glow: multiple concentric circles with decreasing alpha
    center = (size // 2, size // 2 - 40)
    max_glow_radius = 170
    for r in range(max_glow_radius, 0, -10):
        alpha = int(30 * (r / max_glow_radius))  # soft
        glow_color = (*glow_rgb, alpha)
        draw.ellipse(
            [center[0] - r, center[1] - r, center[0] + r, center[1] + r],
            fill=glow_color,
        )

    # Draw chain symbol (two interlocking links)
    # Left link
    link_w, link_h = 220, 140
    left_center = (size // 2 - 70, center[1])
    right_center = (size // 2 + 70, center[1])

    # function to draw rounded rectangle
    def rounded_rectangle(draw, bbox, radius, fill, outline=None, width=6):
        draw.rounded_rectangle(
            bbox, radius=radius, fill=fill, outline=outline, width=width
        )

    # Draw left link (outline only to look like link)
    lw = 14
    rounded_rectangle(
        draw,
        [
            left_center[0] - link_w // 2,
            left_center[1] - link_h // 2,
            left_center[0] + link_w // 2,
            left_center[1] + link_h // 2,
        ],
        radius=40,
        fill=None,
        outline=dark_rgb + (255,),
        width=lw,
    )

    # Draw right link
    rounded_rectangle(
        draw,
        [
            right_center[0] - link_w // 2,
            right_center[1] - link_h // 2,
            right_center[0] + link_w // 2,
            right_center[1] + link_h // 2,
        ],
        radius=40,
        fill=None,
        outline=light_rgb + (255,),
        width=lw,
    )

    # Overlap accent (small filled arc) to imply interlocking
    # Draw a filled small rectangle at the intersection with glow
    inter_w, inter_h = 60, 60
    inter_bbox = [
        size // 2 - inter_w // 2,
        center[1] - inter_h // 2,
        size // 2 + inter_w // 2,
        center[1] + inter_h // 2,
    ]
    draw.ellipse(inter_bbox, fill=(*glow_rgb, 120))

    # Title text
    try:
        # Try common fonts; fall back to default if not found
        font_title = ImageFont.truetype("DejaVuSans.ttf", 54)
        font_tag = ImageFont.truetype("DejaVuSans.ttf", 26)
    except:
        font_title = ImageFont.load_default()
        font_tag = ImageFont.load_default()

    title_text = "HelpChain.live"
    title_w, title_h = draw.textbbox((0, 0), title_text, font=font_title)[2:]
    title_pos = (size // 2 - title_w // 2, center[1] + link_h // 2 + 25)

    # Text glow behind
    for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
        draw.text(
            (title_pos[0] + dx, title_pos[1] + dy),
            title_text,
            font=font_title,
            fill=(*glow_rgb, 130),
        )

    draw.text(title_pos, title_text, font=font_title, fill=dark_rgb + (255,))

    if tagline:
        tag_w, tag_h = draw.textbbox((0, 0), tagline, font=font_tag)[2:]
        tag_pos = (size // 2 - tag_w // 2, title_pos[1] + title_h + 8)
        # subtle glow
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text(
                (tag_pos[0] + dx, tag_pos[1] + dy),
                tagline,
                font=font_tag,
                fill=(*glow_rgb, 140),
            )
        draw.text(tag_pos, tagline, font=font_tag, fill=dark_rgb + (255,))

    img.save(path, "PNG")


def month_labels(start_dt, n=12):
    labels = []
    cur = start_dt
    for _ in range(n):
        labels.append(cur.strftime("%b %Y"))
        cur += relativedelta(months=1)
    return labels


def compute_scenario(realistic=True):
    months = 12
    # Revenues by stream per month (arrays)
    if realistic:
        # Donations: 150 -> 900 (linear)
        donations = np.linspace(150, 900, months)
        # Partnerships: 0 -> 1000 (start low)
        partnerships = np.linspace(0, 1000, months)
        # Courses: start month 5 (index 4): 200 -> 750
        courses = np.zeros(months)
        courses[4:] = np.linspace(200, 750, months - 4)
        # AI Chatbot: start month 5: 200 -> 500
        ai = np.zeros(months)
        ai[4:] = np.linspace(200, 500, months - 4)
        extra_cost = 0
    else:
        # Aggressive
        # Donations: 300 -> 1500
        donations = np.linspace(300, 1500, months)
        # Partnerships: start month 2: 300 -> 2000
        partnerships = np.zeros(months)
        partnerships[1:] = np.linspace(300, 2000, months - 1)
        # Courses: start month 3: 300 -> 1200
        courses = np.zeros(months)
        courses[2:] = np.linspace(300, 1200, months - 2)
        # AI Chatbot: start month 4: 300 -> 1500
        ai = np.zeros(months)
        ai[3:] = np.linspace(300, 1500, months - 3)
        extra_cost = volunteer_aggr_per_month

    revenues = donations + partnerships + courses + ai
    # Expenses: salary + marketing (+ volunteer for aggressive)
    expenses = np.array([salary_per_month + marketing_per_month + extra_cost] * months)
    net = revenues - expenses
    cum_net = np.cumsum(net) + initial_capital

    # Break-even month: first month where cum_net >= 0 AND previous < 0 (if initial negative)
    # Given initial capital 500, we check when cumulative exceeds initial capital baseline (>= initial_capital)
    breakeven = None
    for i in range(months):
        if cum_net[i] >= initial_capital and (
            i == 0 or cum_net[i - 1] < initial_capital
        ):
            breakeven = i + 1  # 1-based month index
            break

    total_rev = float(revenues.sum())
    total_cost = float(expenses.sum())
    total_profit = float((net).sum())
    roi = (total_profit / total_cost) * 100 if total_cost > 0 else np.nan

    df = pd.DataFrame(
        {
            "Revenues (€)": np.round(revenues, 2),
            "Expenses (€)": np.round(expenses, 2),
            "Net Profit (€)": np.round(net, 2),
            "Cumulative Balance (€)": np.round(cum_net, 2),
        }
    )

    # Breakdown columns for transparency
    df_breakdown = pd.DataFrame(
        {
            "Donations (€)": np.round(donations, 2),
            "Partnerships (€)": np.round(partnerships, 2),
            "Courses (€)": np.round(courses, 2),
            "AI Chatbot (€)": np.round(ai, 2),
        }
    )

    return (
        df,
        df_breakdown,
        {
            "total_revenue": round(total_rev, 2),
            "total_expenses": round(total_cost, 2),
            "total_profit": round(total_profit, 2),
            "roi_percent": round(roi, 2),
            "breakeven_month": breakeven,
        },
    )


def add_month_index(df, labels):
    df2 = df.copy()
    df2.insert(0, "Month", labels)
    return df2


def draw_table_page(pdf, title, df, note=None, logo_path=None, footer=None):
    fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4 portrait inches
    ax.axis("off")

    # Title
    ax.text(0.05, 0.95, title, fontsize=16, fontweight="bold", va="top", ha="left")
    # Logo
    if logo_path and os.path.exists(logo_path):
        arr = plt.imread(logo_path)
        ax.imshow(arr, extent=(0.02, 0.3, 0.82, 0.98), aspect="auto")
    # Table
    # Limit rows per page if too many
    tbl = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        loc="upper left",
        cellLoc="left",
        colLoc="left",
        bbox=[0.05, 0.25, 0.9, 0.55],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    for k, cell in tbl.get_celld().items():
        cell.set_linewidth(0.3)

    if note:
        ax.text(0.05, 0.20, note, fontsize=9, va="top", ha="left")

    if footer:
        ax.text(0.5, 0.03, footer, fontsize=9, ha="center", va="bottom")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def draw_chart_page(pdf, title, df, logo_path=None, footer=None):
    # Single chart: Revenues vs Expenses and Net
    fig = plt.figure(figsize=(8.27, 11.69))
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1])
    ax0 = fig.add_subplot(gs[0])
    ax1 = fig.add_subplot(gs[1])

    # Title
    fig.text(0.05, 0.98, title, fontsize=16, fontweight="bold", va="top", ha="left")

    # Logo
    if logo_path and os.path.exists(logo_path):
        arr = plt.imread(logo_path)
        fig.figimage(
            arr, xo=40, yo=850, origin="upper", alpha=0.9
        )  # approximate position

    x = np.arange(len(df))
    ax0.plot(x, df["Revenues (€)"], label="Revenues")
    ax0.plot(x, df["Expenses (€)"], label="Expenses")
    ax0.set_xticks(x)
    ax0.set_xticklabels(df.index, rotation=45, ha="right", fontsize=8)
    ax0.set_ylabel("€")
    ax0.legend()

    ax1.plot(x, df["Net Profit (€)"], label="Net Profit")
    ax1.plot(x, df["Cumulative Balance (€)"], label="Cumulative Balance")
    ax1.set_xticks(x)
    ax1.set_xticklabels(df.index, rotation=45, ha="right", fontsize=8)
    ax1.set_ylabel("€")
    ax1.legend()

    if footer:
        fig.text(0.5, 0.02, footer, ha="center", va="bottom", fontsize=9)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def draw_cover_page(pdf, title, subtitle_lines, logo_path=None, footer=None):
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    # Logo at top-left
    if logo_path and os.path.exists(logo_path):
        arr = plt.imread(logo_path)
        ax.imshow(arr, extent=(0.05, 0.55, 0.7, 0.98), aspect="auto")

    ax.text(0.05, 0.65, title, fontsize=20, fontweight="bold", ha="left", va="top")
    y = 0.60
    for line in subtitle_lines:
        ax.text(0.05, y, line, fontsize=11, ha="left", va="top")
        y -= 0.035

    if footer:
        ax.text(0.5, 0.03, footer, fontsize=9, ha="center", va="bottom")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ------------- 1) CREATE LOGOS -------------
create_compact_logo(logo_bg_path, tagline=None)
create_compact_logo(logo_en_path, tagline="Connecting help, hope and people")

# ------------- 2) BUILD FINANCIAL MODEL -------------
# Month labels from next month (to be forward-looking)
today = datetime(2025, 10, 15)
start = (today + relativedelta(months=1)).replace(day=1)
labels = month_labels(start, 12)

df_real, df_real_break, meta_real = compute_scenario(realistic=True)
df_aggr, df_aggr_break, meta_aggr = compute_scenario(realistic=False)

df_real = add_month_index(df_real, labels)
df_aggr = add_month_index(df_aggr, labels)
df_real_break = add_month_index(df_real_break, labels)
df_aggr_break = add_month_index(df_aggr_break, labels)

# Set Month as index for charts
df_real_idx = df_real.set_index("Month")
df_aggr_idx = df_aggr.set_index("Month")

# Summary sheet
summary_rows = [
    [
        "Scenario",
        "Total Revenue (€)",
        "Total Expenses (€)",
        "Total Profit (€)",
        "ROI (%)",
        "Break-even (month)",
    ],
    [
        "Realistic",
        meta_real["total_revenue"],
        meta_real["total_expenses"],
        meta_real["total_profit"],
        meta_real["roi_percent"],
        meta_real["breakeven_month"],
    ],
    [
        "Aggressive",
        meta_aggr["total_revenue"],
        meta_aggr["total_expenses"],
        meta_aggr["total_profit"],
        meta_aggr["roi_percent"],
        meta_aggr["breakeven_month"],
    ],
]
df_summary = pd.DataFrame(summary_rows[1:], columns=summary_rows[0])

# ------------- 3) WRITE EXCEL -------------
with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
    df_summary.to_excel(writer, sheet_name="Summary", index=False)
    df_real.to_excel(writer, sheet_name="Realistic_Totals", index=False)
    df_real_break.to_excel(writer, sheet_name="Realistic_Breakdown", index=False)
    df_aggr.to_excel(writer, sheet_name="Aggressive_Totals", index=False)
    df_aggr_break.to_excel(writer, sheet_name="Aggressive_Breakdown", index=False)

# ------------- 4) CREATE PDF REPORTS -------------
footer_text = "© 2025–2026 HelpChain.live — Created by Stella Barbarella"

# BG PDF
with PdfPages(pdf_bg_path) as pdf:
    # Cover / Executive Summary (BG)
    bg_sub = [
        "Мисия: HelpChain.live свързва хора в нужда с доброволци и специалисти (България + Франция).",
        "Обхват: Реални приходи – дарения, обучения, партньорства, AI chatbot. Без грантове.",
        f"Сценарии: Реалистичен и Агресивен (доброволец +{volunteer_aggr_per_month} €/мес в агресивния).",
        f"Заплата: {salary_per_month} €/мес | Маркетинг: {marketing_per_month} €/мес | Начален капитал: {initial_capital} €.",
        "Стил: бизнес, бял фон, сини акценти, компактно лого с аква glow.",
    ]
    draw_cover_page(
        pdf,
        "HelpChain Financial Report (BG)",
        bg_sub,
        logo_path=logo_bg_path,
        footer=footer_text,
    )

    # Realistic tables
    draw_table_page(
        pdf,
        "Реалистичен сценарий – Обобщение",
        df_real,
        note="Приходи, разходи, печалба и баланс по месеци.",
        logo_path=logo_bg_path,
        footer=footer_text,
    )
    draw_table_page(
        pdf,
        "Реалистичен сценарий – Детайлен приход (Breakdown)",
        df_real_break,
        note="Дарения, партньорства, обучения, AI chatbot по месеци.",
        logo_path=logo_bg_path,
        footer=footer_text,
    )
    draw_chart_page(
        pdf,
        "Графики – Реалистичен сценарий",
        df_real_idx,
        logo_path=logo_bg_path,
        footer=footer_text,
    )

    # Aggressive tables
    draw_table_page(
        pdf,
        "Агресивен сценарий – Обобщение",
        df_aggr,
        note="Включва разход за доброволец +200 €/месец.",
        logo_path=logo_bg_path,
        footer=footer_text,
    )
    draw_table_page(
        pdf,
        "Агресивен сценарий – Детайлен приход (Breakdown)",
        df_aggr_break,
        note="Дарения, партньорства, обучения, AI chatbot по месеци.",
        logo_path=logo_bg_path,
        footer=footer_text,
    )
    draw_chart_page(
        pdf,
        "Графики – Агресивен сценарий",
        df_aggr_idx,
        logo_path=logo_bg_path,
        footer=footer_text,
    )

    # Scaling France & Social Impact (BG) – text page
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    ax.text(
        0.05,
        0.95,
        "Мащабиране във Франция – Препоръки",
        fontsize=14,
        fontweight="bold",
        ha="left",
        va="top",
    )
    ax.text(
        0.05,
        0.89,
        "• Партньори: Secours Populaire, Emmaüs, Croix-Rouge, APF France Handicap",
        fontsize=10,
    )
    ax.text(
        0.05,
        0.86,
        "• Донори/фондации: France Active, BPI France, Fondation de France",
        fontsize=10,
    )
    ax.text(
        0.05,
        0.83,
        "• Комуникация: LinkedIn кампании, локални медии, университети, общини",
        fontsize=10,
    )
    ax.text(
        0.05,
        0.80,
        "• 3-месечен план: 1) PR и партньори 2) демонстрации 3) pilot кампании",
        fontsize=10,
    )
    ax.text(
        0.05,
        0.74,
        "Social Impact Metrics (примерни цели за 12 месеца):",
        fontsize=12,
        fontweight="bold",
    )
    ax.text(
        0.05,
        0.71,
        "• Подкрепени хора: 1 000+  • Активни доброволци: 500+  • Кампании: 20+",
        fontsize=10,
    )
    ax.text(
        0.05,
        0.68,
        "• Индекс на удовлетвореност ≥ 4.7/5  • Спестено време/ресурси (символично): 5 000+ ч.",
        fontsize=10,
    )
    ax.text(0.5, 0.03, footer_text, ha="center", va="bottom", fontsize=9)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

# EN PDF
with PdfPages(pdf_en_path) as pdf:
    # Cover / Executive Summary (EN)
    en_sub = [
        "Mission: HelpChain.live connects people in need with volunteers and professionals (Bulgaria + France).",
        "Scope: Real revenues only – donations, courses, partnerships, AI chatbot. No grants assumed.",
        f"Scenarios: Realistic and Aggressive (volunteer cost +{volunteer_aggr_per_month} €/mo in aggressive).",
        f"Salary: {salary_per_month} €/mo | Marketing: {marketing_per_month} €/mo | Initial capital: {initial_capital} €.",
        "Style: business, white with blue accents, compact logo with aqua glow.",
    ]
    draw_cover_page(
        pdf,
        "HelpChain Financial Report (EN)",
        en_sub,
        logo_path=logo_en_path,
        footer=footer_text,
    )

    # Realistic
    draw_table_page(
        pdf,
        "Realistic Scenario – Totals",
        df_real,
        note="Monthly revenues, expenses, profit and cumulative balance.",
        logo_path=logo_en_path,
        footer=footer_text,
    )
    draw_table_page(
        pdf,
        "Realistic Scenario – Revenue Breakdown",
        df_real_break,
        note="Donations, partnerships, courses, AI chatbot by month.",
        logo_path=logo_en_path,
        footer=footer_text,
    )
    draw_chart_page(
        pdf,
        "Charts – Realistic Scenario",
        df_real_idx,
        logo_path=logo_en_path,
        footer=footer_text,
    )

    # Aggressive
    draw_table_page(
        pdf,
        "Aggressive Scenario – Totals",
        df_aggr,
        note="Includes volunteer cost +200 €/month.",
        logo_path=logo_en_path,
        footer=footer_text,
    )
    draw_table_page(
        pdf,
        "Aggressive Scenario – Revenue Breakdown",
        df_aggr_break,
        note="Donations, partnerships, courses, AI chatbot by month.",
        logo_path=logo_en_path,
        footer=footer_text,
    )
    draw_chart_page(
        pdf,
        "Charts – Aggressive Scenario",
        df_aggr_idx,
        logo_path=logo_en_path,
        footer=footer_text,
    )

    # Scaling France & Social Impact (EN) – text page
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    ax.text(
        0.05,
        0.95,
        "Scaling in France – Recommendations",
        fontsize=14,
        fontweight="bold",
        ha="left",
        va="top",
    )
    ax.text(
        0.05,
        0.89,
        "• Partners: Secours Populaire, Emmaüs, Croix-Rouge, APF France Handicap",
        fontsize=10,
    )
    ax.text(
        0.05,
        0.86,
        "• Donors/Funders: France Active, BPI France, Fondation de France",
        fontsize=10,
    )
    ax.text(
        0.05,
        0.83,
        "• Comms: LinkedIn campaigns, local media, universities, municipalities",
        fontsize=10,
    )
    ax.text(
        0.05,
        0.80,
        "• 3-month plan: 1) PR & partnerships 2) demos 3) pilot campaigns",
        fontsize=10,
    )
    ax.text(
        0.05,
        0.74,
        "Social Impact Metrics (12-month targets):",
        fontsize=12,
        fontweight="bold",
    )
    ax.text(
        0.05,
        0.71,
        "• People supported: 1,000+  • Active volunteers: 500+  • Campaigns: 20+",
        fontsize=10,
    )
    ax.text(
        0.05,
        0.68,
        "• Satisfaction index ≥ 4.7/5  • Time/resources saved (symbolic): 5,000+ hrs",
        fontsize=10,
    )
    ax.text(0.5, 0.03, footer_text, ha="center", va="bottom", fontsize=9)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

# ------------- 5) ZIP EVERYTHING -------------
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write(logo_bg_path, os.path.basename(logo_bg_path))
    zf.write(logo_en_path, os.path.basename(logo_en_path))
    zf.write(xlsx_path, os.path.basename(xlsx_path))
    zf.write(pdf_bg_path, os.path.basename(pdf_bg_path))
    zf.write(pdf_en_path, os.path.basename(pdf_en_path))

# Present a quick summary DataFrame to the user (optional)
summary_df = df_summary.copy()
print(summary_df)
print(f"ZIP archive created at: {zip_path}")
