#!/usr/bin/env python3
"""
make_certificate.py  -  3D-PAWS rain gauge dynamic calibration certificate (PDF)

Builds the certificate from one dyn_rain_cal.py results folder, following WMO-No. 8 (2024 edition),
Volume I, Chapter 6, Annex 6.A. Layout from the certificate prototype (build_pdf.py, 3 Nov 2026).

Usage (on the Pi, from /home/pi/3d_paws/scripts/sensors/):
  python3 make_certificate.py /home/pi/data/tests/dyn_rain_cal_<GaugeID>_<date_time>
Writes certificate.pdf into that folder.

Operator, reviewer, equipment IDs and measured values that replace assumptions come from
/home/pi/data/tests/certificate_info.json, created with [bracketed] placeholders the first time.
Fill it in once; edit it when equipment changes.

The certificate is marked DRAFT, and not numbered, while anything is assumed, missing or still in
[brackets]; the reasons are listed on page 1. A clean certificate takes the next number from
certificate_info.json, and rebuilding the same folder keeps its number.

Needs matplotlib, numpy and reportlab (on Raspbian Buster: python3-matplotlib, python3-reportlab).
"""
import argparse
import csv
import datetime as dt
import json
import math
import os
import statistics
import sys
from xml.sax.saxutils import escape

DATA_DIR = "/home/pi/data/tests"
LIMIT_PCT = 5.0                   # WMO +/-5 %
U_LIMIT_PCT = 1.0                 # Annex 6.A: uncertainty of the generated intensity under 1 %
MIN_INTENSITIES = 5               # Annex 6.A: at least five reference intensities
MIN_RUNS = 3                      # Annex 6.A: ideally 5 tests per intensity, minimum 3

# Values used until certificate_info.json gives a measured one. Each makes the certificate a DRAFT.
ASSUMED = {
    "mass_step_error_pct": 0.10,      # load cell, differencing (TAL220B not yet characterized)
    "evaporation_g_per_h": 1.0,
    "rim_diameter_uncertainty_mm": 0.1,
}

INFO_TEMPLATE = {
    "operator": "[name]",
    "reviewer": "[name]",
    "certificate_prefix": "3DPAWS-RG-",
    "next_certificate_number": 1,
    "gauge_type": "3D-PAWS 3D-printed tipping bucket, SS451A Hall sensor, 0.2 mm per tip nominal",
    "water": "Tap water, as drawn, room temperature",
    "special_conditions": "[none noted, or describe]",
    "measured": {
        "_note": "Fill these in when measured; null keeps the assumed value and the DRAFT mark.",
        "mass_step_error_pct": None,
        "evaporation_g_per_h": None,
        "rim_diameter_mm": None,
        "rim_diameter_uncertainty_mm": None,
    },
    "equipment": [
        ["Net mass", "SparkFun TAL220B 5 kg load cell with Qwiic Scale (NAU7802)", "[serial, characterization record]"],
        ["Mass reference", "[reference masses: class and certificate number]", "[traceability]"],
        ["Flow generator", "Drip regulator (float valve and flow-control bolt), not a reference", "[ID]"],
        ["Water temperature", "DS18B20", "[check against reference thermometer]"],
        ["Air temperature, humidity, pressure", "SHT45 and BMP581", "[check record]"],
        ["Rim diameter", "Digital calipers, 200 mm or longer", "[serial, check record]"],
    ],
}


def info_path():
    return os.path.join(DATA_DIR, "certificate_info.json")


def load_info():
    """certificate_info.json, created from the template if missing. Returns (info, created)."""
    path = info_path()
    if os.path.exists(path):
        with open(path) as f:
            info = json.load(f)
        merged = json.loads(json.dumps(INFO_TEMPLATE))
        merged.update(info)
        merged["measured"] = dict(INFO_TEMPLATE["measured"], **info.get("measured", {}))
        return merged, False
    try:
        with open(path, "w") as f:
            json.dump(INFO_TEMPLATE, f, indent=2)
    except OSError:
        pass
    return json.loads(json.dumps(INFO_TEMPLATE)), True


def has_placeholder(value):
    if isinstance(value, str):
        return "[" in value
    if isinstance(value, list):
        return any(has_placeholder(v) for v in value)
    if isinstance(value, dict):
        return any(has_placeholder(v) for k, v in value.items() if not k.startswith("_"))
    return False


# ----------------------------------------------------------------- analysis
def tip_times(folder):
    """tip number -> time (s) from tips.csv."""
    times = {}
    with open(os.path.join(folder, "tips.csv")) as f:
        for row in csv.DictReader(f):
            times[int(row["tip"])] = float(row["t_s"])
    return times


def flow_steadiness_pct(times, start, end):
    """Standard uncertainty (%) of a run's mean flow from the spread of its tip intervals. Intervals are
    taken in pairs (one fill of each bucket side), so a gauge with unequal sides doesn't look unsteady."""
    pairs = [times[k] - times[k - 2] for k in range(start + 2, end + 1, 2) if k in times and k - 2 in times]
    if len(pairs) < 3:
        return None
    return statistics.stdev(pairs) / statistics.mean(pairs) / math.sqrt(len(pairs)) * 100


def polyfit(xs, ys, deg):
    """Least-squares polynomial, coefficients highest power first (as numpy.polyfit)."""
    n = deg + 1
    a = [[sum(x ** (i + j) for x in xs) for j in range(n)] for i in range(n)]
    b = [sum(y * x ** i for x, y in zip(xs, ys)) for i in range(n)]
    for col in range(n):                      # Gaussian elimination with partial pivoting
        piv = max(range(col, n), key=lambda r: abs(a[r][col]))
        a[col], a[piv], b[col], b[piv] = a[piv], a[col], b[piv], b[col]
        for r in range(col + 1, n):
            k = a[r][col] / a[col][col]
            a[r] = [v - k * w for v, w in zip(a[r], a[col])]
            b[r] -= k * b[col]
    c = [0.0] * n
    for r in reversed(range(n)):
        c[r] = (b[r] - sum(a[r][j] * c[j] for j in range(r + 1, n))) / a[r][r]
    return list(reversed(c))


def polyval(coef, x):
    v = 0.0
    for c in coef:
        v = v * x + c
    return v


def analyze(folder, info):
    with open(os.path.join(folder, "result.json")) as f:
        res = json.load(f)
    measured = info.get("measured", {})
    draft = []
    n_tips = res["tips_per_run"]
    mm_tip = res["mm_per_tip"]
    times = tip_times(folder)
    loadcell = res.get("method", "load cell") == "load cell"

    # Collector area: the sized (design) rim, or the measured rim once its diameter is entered. V_S is
    # recomputed from the runs' unrounded mass and density (the middle 3 of 5 at the sizing rate), so e
    # is exactly zero there with the design area.
    sizing_rate = res["sizing_rate_mm_h"]
    at_size = sorted([r["net_g"] / r["density_g_ml"] / n_tips for r in res["runs"]
                      if r["rate_mm_h"] == sizing_rate and r.get("kept") and r.get("net_g") is not None])
    v_s = statistics.mean(at_size[1:-1] if len(at_size) >= 5 else at_size)
    a_design = v_s * 1000.0 / mm_tip
    d_meas = measured.get("rim_diameter_mm")
    area = math.pi * (d_meas / 2) ** 2 if d_meas else a_design
    if not d_meas:
        draft.append("rim diameter not measured (design area used)")

    # Every weighed run: Ir from mass, density, area and time; Im from the tips; e = (Im - Ir) / Ir
    runs = []
    for r in res["runs"]:
        r = dict(r)
        if r.get("net_g") is not None:
            t = r["duration_s"]
            r["Im"] = n_tips * mm_tip * 3600.0 / t
            r["Ir"] = r["net_g"] / r["density_g_ml"] * 1000.0 / area * 3600.0 / t
            r["e"] = (r["Im"] - r["Ir"]) / r["Ir"] * 100
            r["flow_pct"] = flow_steadiness_pct(times, r["start_tip"], r["end_tip"]) \
                if "start_tip" in r else None
        r["used"] = "No (discarded)" if r.get("kept") is False else ("No (not weighed)" if r.get("net_g") is None else "")
        runs.append(r)
    _attach_tips(runs, res, folder)

    # Per rate: drop the runs with the lowest and highest e when there are 5 or more, average the rest
    stats = []
    for rate in [s["rate_mm_h"] for s in res["rates"]]:
        kept = sorted([r for r in runs if r["rate_mm_h"] == rate and r.get("kept") and "e" in r], key=lambda r: r["e"])
        if not kept:
            continue
        for j, r in enumerate(kept):
            r["used"] = "Yes"
            if len(kept) >= 5 and j == 0:
                r["used"] = "No (min)"
            elif len(kept) >= 5 and j == len(kept) - 1:
                r["used"] = "No (max)"
        mid = kept[1:-1] if len(kept) >= 5 else kept
        es = [r["e"] for r in kept]
        flows = [r["flow_pct"] for r in kept if r.get("flow_pct") is not None]
        s = {"rate": rate, "n": len(kept),
             "tpm": statistics.mean(r["tips_per_min"] for r in mid),
             "Ir": statistics.mean(r["Ir"] for r in mid), "Im": statistics.mean(r["Im"] for r in mid),
             "ml": statistics.mean(r["ml_per_tip"] for r in mid), "e": statistics.mean(r["e"] for r in mid),
             "lo": min(es), "hi": max(es), "sd": statistics.stdev(es) if len(es) > 1 else 0.0,
             "mass": statistics.mean(r["net_g"] for r in kept), "dur": statistics.mean(r["duration_s"] for r in kept),
             "density": statistics.mean(r["density_g_ml"] for r in kept),
             "flow": statistics.mean(flows) if flows else None, "sized": rate == sizing_rate}
        if len(kept) < MIN_RUNS:
            draft.append(f"{rate:g} mm/h has only {len(kept)} valid runs (Annex 6.A minimum {MIN_RUNS})")
        stats.append(s)
    if len(stats) < MIN_INTENSITIES:
        draft.append(f"{len(stats)} reference intensities tested (Annex 6.A requires at least {MIN_INTENSITIES})")

    # Fit Ir against Im: second-order polynomial (linear with two rates), for interpolation only
    coef, fit_res = None, None
    if len(stats) >= 2:
        deg = 2 if len(stats) >= 3 else 1
        coef = polyfit([s["Im"] for s in stats], [s["Ir"] for s in stats], deg)
        for s in stats:
            s["fit_res"] = (polyval(coef, s["Im"]) / s["Ir"] - 1) * 100
        fit_res = max(abs(s["fit_res"]) for s in stats)

    # Uncertainty of Ir (standard uncertainties in %), combined root sum of squares, expanded k = 2
    conditions = res.get("conditions") or []
    waters = [c["water_c"] for c in conditions if c.get("water_c") is not None]
    step = measured.get("mass_step_error_pct")
    evap = measured.get("evaporation_g_per_h")
    d_unc = measured.get("rim_diameter_uncertainty_mm") or ASSUMED["rim_diameter_uncertainty_mm"]
    if loadcell and step is None:
        draft.append("load cell step error not characterized (0.10 % assumed)")
    if evap is None:
        draft.append("evaporation not measured (1 g/h assumed)")
    if not waters:
        draft.append("water temperature not measured (density fixed at 0.998 g/mL)")
    labels = {}
    for s in stats:
        if loadcell:
            mass = step if step is not None else ASSUMED["mass_step_error_pct"]
            labels["mass"] = "Mass (load cell, differencing)" + ("" if step is not None else ", assumed")
        else:
            mass = math.sqrt(2) * 0.5 / math.sqrt(3) / s["mass"] * 100
            labels["mass"] = "Mass (1 g scale, two readings)"
        loss_g = (evap if evap is not None else ASSUMED["evaporation_g_per_h"]) * s["dur"] / 3600.0
        comp = {
            "mass": mass,
            "time": 0.01,
            "density": 0.005 if waters else 0.06,
            "area": 2 * d_unc / (d_meas or 2 * math.sqrt(area / math.pi)) * 100 / math.sqrt(3),
            "flow": s["flow"] if s["flow"] is not None else 0.0,
            "evaporation": loss_g / s["mass"] * 100 / math.sqrt(3),
            "repeatability": s["sd"] / math.sqrt(s["n"]),
        }
        s["comp"] = comp
        s["uc"] = math.sqrt(sum(v * v for v in comp.values()))
        s["U"] = 2 * s["uc"]
        s["evap_mm"] = loss_g / s["density"] * 1000.0 / area
    labels.update({
        "time": "Time (tip times to 1 ms)",
        "density": "Water density (water temperature ±0.5 °C)" if waters else "Water density (fixed 0.998, 20 to 25 °C)",
        "area": f"Collector area (diameter ±{d_unc:g} mm)" + ("" if d_meas else ", assumed"),
        "flow": "Flow steadiness (tip-interval spread, measured)",
        "evaporation": "Evaporation" + (f" ({evap:g} g/h, measured)" if evap is not None else " (1 g/h, assumed)"),
        "repeatability": "Repeatability (runs at each rate)",
    })

    # Checks for section 6
    weighed = [r for r in runs if "e" in r]
    balance = res.get("balance")
    if not balance:
        draft.append("no bucket balance recorded (run dyn_rain_cal.py --balance before the session)")
    elif not balance["final"]["balanced"]:
        draft.append("bucket balance outside the worksheet limits")
    if has_placeholder({k: v for k, v in info.items() if k not in ("measured",)}):
        draft.append("placeholders in certificate_info.json")
    funnel = res.get("funnel_storage", {})

    # Session: from the first condition reading or run start to the last reading or run end
    stamps = [c["time"][:19] for c in conditions] + [r[k][:19] for r in runs for k in ("start_time", "end_time") if r.get(k)]
    start, end = min(stamps), max(stamps)
    big = max(stats, key=lambda s: abs(s["e"]))
    return {"res": res, "info": info, "runs": runs, "stats": stats, "coef": coef, "fit_res": fit_res,
            "v_s": v_s, "area": area, "a_design": a_design, "d_meas": d_meas,
            "radius": math.sqrt(a_design / math.pi), "sizing_rate": sizing_rate, "labels": labels,
            "start": dt.datetime.fromisoformat(start[:19]), "end": dt.datetime.fromisoformat(end[:19]),
            "conditions": conditions, "balance": balance, "funnel": funnel, "loadcell": loadcell,
            "big": big, "within": all(abs(s["e"]) <= LIMIT_PCT for s in stats),
            "irregular": sum(1 for r in runs if r.get("irregular")),
            "drift": sum(1 for r in weighed if abs(r.get("off_target_pct") or 0) > LIMIT_PCT),
            "discarded": [r for r in runs if r.get("kept") is False],
            "draft": list(dict.fromkeys(draft))}


def _attach_tips(runs, res, folder):
    """Older result.json files lack start_tip/end_tip in runs; take them from runs.csv by rate and run."""
    if all("start_tip" in r for r in runs):
        return
    path = os.path.join(folder, "runs.csv")
    if not os.path.exists(path):
        return
    with open(path) as f:
        rows = {(float(x["rate_mm_h"]), int(x["run"])): x for x in csv.DictReader(f)}
    for r in runs:
        x = rows.get((float(r["rate_mm_h"]), int(r["run"])))
        if x and x.get("start_tip"):
            r["start_tip"], r["end_tip"] = int(x["start_tip"]), int(x["end_tip"])


def condition_range(conditions, key, unit, fmt):
    vals = [c[key] for c in conditions if c.get(key) is not None]
    if not vals:
        return "[not measured]"
    lo, hi = min(vals), max(vals)
    return (fmt % lo if lo == hi else (fmt + " to " + fmt) % (lo, hi)) + " " + unit


# ----------------------------------------------------------------- PDF
def register_fonts():
    """DejaVu Sans from the system or from matplotlib's own copy; Helvetica as the last resort."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import matplotlib
    for d in ("/usr/share/fonts/truetype/dejavu/", os.path.join(matplotlib.get_data_path(), "fonts", "ttf")):
        try:
            pdfmetrics.registerFont(TTFont("DV", os.path.join(d, "DejaVuSans.ttf")))
            pdfmetrics.registerFont(TTFont("DV-B", os.path.join(d, "DejaVuSans-Bold.ttf")))
            pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV", boldItalic="DV-B")
            return "DV", "DV-B"
        except Exception:
            continue
    return "Helvetica", "Helvetica-Bold"


def num(x, n=2, sign=False):
    s = ("%+." + str(n) + "f") % x if sign else ("%." + str(n) + "f") % x
    return s.replace("-", "−")


def error_figure(d, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    stats, runs = d["stats"], [r for r in d["runs"] if "e" in r and r.get("kept")]
    x_max = max(50.0, math.ceil(max(r["Ir"] for r in runs) * 1.1 / 25.0) * 25.0)
    y_max = max(6.5, math.ceil(max(abs(r["e"]) for r in runs) + 1.5))
    fig, ax = plt.subplots(figsize=(7.2, 3.35), dpi=200)
    ax.axhspan(LIMIT_PCT, y_max, color="#f6d6d6", alpha=.55, lw=0)
    ax.axhspan(-y_max, -LIMIT_PCT, color="#f6d6d6", alpha=.55, lw=0)
    ax.axhline(LIMIT_PCT, color="#8a1f1f", ls="--", lw=1)
    ax.axhline(-LIMIT_PCT, color="#8a1f1f", ls="--", lw=1)
    ax.axhline(0, color="#555555", lw=.6)
    ax.scatter([r["Ir"] for r in runs], [r["e"] for r in runs], s=9, color="#9aa5b1", zorder=2,
               label="Individual runs (%d)" % len(runs))
    if d["coef"] is not None:
        grid = np.linspace(min(s["Im"] for s in stats), max(s["Im"] for s in stats), 200)
        fit = np.array([polyval(d["coef"], x) for x in grid])
        ax.plot(fit, (grid / fit - 1) * 100, color="#1f5fa8", lw=1.3, zorder=3,
                label="Fitted curve (%s, Ir vs Im)" % ("2nd-order polynomial" if len(d["coef"]) == 3 else "linear"))
    n_all = max(s["n"] for s in stats)
    ax.errorbar([s["Ir"] for s in stats], [s["e"] for s in stats],
                yerr=[[s["e"] - s["lo"] for s in stats], [s["hi"] - s["e"] for s in stats]],
                fmt="o", color="#0b2f5c", ms=5, capsize=3, lw=1.1, zorder=4,
                label="Mean of middle 3 runs, bar = range of all %d" % n_all if n_all >= 5 else "Mean of runs, bar = range")
    for s in stats:
        ax.annotate("%g" % s["rate"], (s["Ir"], s["e"]), textcoords="offset points", xytext=(0, 8), ha="center",
                    fontsize=7, color="#0b2f5c")
    sized = [s for s in stats if s["sized"]]
    if sized and not d["d_meas"]:
        ax.annotate("sized here: e = 0 by construction", (sized[0]["Ir"], 0), textcoords="offset points",
                    xytext=(14, 16), fontsize=7, color="#333333", arrowprops=dict(arrowstyle="-", color="#777777", lw=.7))
    ax.text(x_max * 0.98, LIMIT_PCT + 0.25, "WMO ±5% limit", ha="right", va="bottom", fontsize=7, color="#8a1f1f")
    ax.set_xlim(0, x_max)
    ax.set_ylim(-y_max, y_max)
    ax.set_xlabel("Reference intensity Ir (mm/h)", fontsize=8)
    ax.set_ylabel("Relative error e (%)", fontsize=8)
    ax.tick_params(labelsize=7.5)
    ax.grid(True, color="#dde2e7", lw=.5)
    ax.set_title("Relative error versus reference intensity (labels = nominal rate, mm/h)", fontsize=8.5, loc="left")
    ax.legend(fontsize=6.8, loc="lower left", frameon=True, framealpha=.95)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def build_pdf(d, out, cert_no):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.pdfgen import canvas
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak

    font, bold = register_fonts()
    res, info, stats, runs = d["res"], d["info"], d["stats"], d["runs"]
    draft = bool(d["draft"])
    INK, GRID, HEAD, BLUE = (colors.HexColor("#1f2933"), colors.HexColor("#b4bcc5"),
                             colors.HexColor("#e6edf4"), colors.HexColor("#1f5fa8"))
    B = ParagraphStyle("B", fontName=font, fontSize=8, leading=10.6, textColor=INK)
    SM = ParagraphStyle("SM", parent=B, fontSize=7.2, leading=9.4)
    CELL = ParagraphStyle("CELL", parent=B, fontSize=7.6, leading=9.6)
    CELLC = ParagraphStyle("CELLC", parent=CELL, alignment=TA_CENTER)
    CELLB = ParagraphStyle("CELLB", parent=CELL, fontName=bold)
    HC = ParagraphStyle("HC", parent=CELLC, fontName=bold, fontSize=7.0, leading=8.4)
    TITLE = ParagraphStyle("T", fontName=bold, fontSize=16, leading=19, textColor=INK)
    SUB = ParagraphStyle("S", fontName=font, fontSize=8.5, leading=11, textColor=colors.HexColor("#52606d"))
    H = ParagraphStyle("H", fontName=bold, fontSize=9.6, leading=12, textColor=BLUE, spaceBefore=7, spaceAfter=3)
    NOTE = ParagraphStyle("N", parent=B, fontSize=7.8, leading=10.2, backColor=colors.HexColor("#fff4d6"),
                          borderColor=colors.HexColor("#d9a400"), borderWidth=.6, borderPadding=4, spaceBefore=4, spaceAfter=6)
    LI = ParagraphStyle("LI", parent=B, leftIndent=12, firstLineIndent=-12, spaceAfter=2.5)

    def P(t, s=CELL):
        return Paragraph(t, s)

    def E(t):
        return escape(str(t))

    def style(extra=()):
        return TableStyle([("GRID", (0, 0), (-1, -1), .4, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
                           ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)] + list(extra))

    def pairs_table(rows, widths):
        t = Table([[P(a, CELLB), P(b), P(c, CELLB), P(e)] for a, b, c, e in rows], colWidths=widths)
        t.setStyle(style([("BACKGROUND", (0, 0), (0, -1), HEAD), ("BACKGROUND", (2, 0), (2, -1), HEAD)]))
        return t

    W = 7.3 * inch
    story = [Paragraph("Dynamic Calibration Certificate", TITLE),
             Paragraph("3D-PAWS tipping bucket rain gauge, multi-rate calibration following WMO-No. 8 (2024 edition), "
                       "Volume I, Chapter 6, Annex 6.A", SUB)]
    if draft:
        story.append(Paragraph("<b>DRAFT, not a valid certificate.</b> To issue it: " +
                               "; ".join(E(x) for x in d["draft"]) + ".", NOTE))

    # 1 Identification
    hours = (d["end"] - d["start"]).total_seconds() / 3600.0
    ident = [
        ["Certificate no.", E(cert_no), "Calibration date", d["start"].strftime("%Y-%m-%d")],
        ["Gauge ID", E(res["gauge_id"]), "Operator", E(info["operator"])],
        ["Gauge type", E(info["gauge_type"]), "Software", E(res.get("software") or "dyn_rain_cal.py [version]")],
        ["Tested range", "Ir %s to %s mm/h (%d reference intensities)" % (num(min(s["Ir"] for s in stats), 1),
                                                                        num(max(s["Ir"] for s in stats), 1), len(stats)),
         "Session", "%s to %s (%d h %d min)" % (d["start"].strftime("%H:%M"), d["end"].strftime("%H:%M"),
                                                 int(hours), int(round((hours % 1) * 60)))],
    ]
    story += [Paragraph("1. Identification", H), pairs_table(ident, [.95 * inch, 2.9 * inch, .95 * inch, 2.5 * inch])]

    # 2 Result summary
    big = d["big"]
    rim = ("<b>%s mm</b> (diameter %s mm), collector area %s mm². " % (num(d["radius"]), num(2 * d["radius"]),
                                                                           "{:,.0f}".format(d["a_design"])))
    rim += ("Measured rim diameter %s mm (area %s mm²) used for Ir." % (num(d["d_meas"]), "{:,.0f}".format(d["area"]))
            if d["d_meas"] else "Design value, not yet measured; diameter uncertainty of ±%g mm assumed."
            % ASSUMED["rim_diameter_uncertainty_mm"])
    summary = [
        ["Rim sized at", "%g mm/h nominal, %s mL per tip (mean of the middle 3 of 5 runs)" % (d["sizing_rate"], num(d["v_s"], 3))],
        ["Rim radius (design)", rim],
        ["Largest error", "%s %% at Ir = %s mm/h" % (num(big["e"], 2, True), num(big["Ir"], 1))],
        ["Within ±5 % at all tested intensities",
         ("<b>Yes.</b> " if d["within"] else "<b>No.</b> ") +
         ("The error at the sizing rate is zero by construction, so the check there is not independent. " if not d["d_meas"] else "") +
         "Judged on the measured error alone; the decision rule including uncertainty is still to be set."],
        ["Corrections applied", "None. The results are uncorrected."],
    ]
    t = Table([[P(a, CELLB), P(b)] for a, b in summary], colWidths=[1.75 * inch, 5.55 * inch])
    t.setStyle(style([("BACKGROUND", (0, 0), (0, -1), HEAD)]))
    story += [Paragraph("2. Result summary", H), t]

    # 3 Results by reference intensity + graph
    hdr = ["Nominal rate (mm/h)", "Tips per min", "Ir (mm/h)", "Im (mm/h)", "mL per tip", "Error e (%)",
           "Error range, all runs (%)", "U(Ir), k=2 (%)"]
    rows = [[P(h, HC) for h in hdr]]
    sized_row = None
    for i, s in enumerate(stats):
        if s["sized"]:
            sized_row = i + 1
        rows.append([P("%g" % s["rate"], CELLC), P(num(s["tpm"]), CELLC), P(num(s["Ir"], 1), CELLC),
                     P(num(s["Im"], 1), CELLC), P(num(s["ml"], 3), CELLC), P(num(s["e"], 2, True), CELLC),
                     P("%s to %s" % (num(s["lo"], 2, True), num(s["hi"], 2, True)), CELLC), P(num(s["U"]), CELLC)])
    t = Table(rows, colWidths=[.95 * inch, .75 * inch, .8 * inch, .8 * inch, .8 * inch, .85 * inch, 1.5 * inch, .85 * inch])
    extra = [("BACKGROUND", (0, 0), (-1, 0), HEAD)]
    if sized_row:
        extra.append(("BACKGROUND", (0, sized_row), (-1, sized_row), colors.HexColor("#f3f7fb")))
    t.setStyle(style(extra))
    fig_path = os.path.join(os.path.dirname(out), "certificate_error_graph.png")
    error_figure(d, fig_path)
    story += [Paragraph("3. Results by reference intensity", H), t, Spacer(1, 3),
              Paragraph("Nominal rate is the setpoint, 12 × tips per minute. Ir is the reference intensity computed from "
                        "mass, time, water density and the rim area, so it differs from nominal when the volume per tip changes "
                        "with rate. Averages use the middle 3 of 5 runs (the runs with the lowest and highest error are "
                        "discarded). Shaded row: sizing rate.", SM),
              Spacer(1, 4), Image(fig_path, width=W, height=W * 3.35 / 7.2)]

    # 4 Environmental conditions
    c = d["conditions"]
    waters = [x["water_c"] for x in c if x.get("water_c") is not None]
    density = ("%s g/mL, computed from %s" % (num(statistics.mean(r["density_g_ml"] for r in runs if r.get("density_g_ml"))
                                                 if waters else 0.998, 5),
                                             condition_range(c, "water_c", "°C", "%.1f"))
               if waters else "0.998 g/mL (fixed; water temperature not measured)")
    sensor = res.get("water_sensor")
    env = [
        ["Air temperature", condition_range(c, "air_c", "°C (SHT45)", "%.1f"),
         "Relative humidity", condition_range(c, "rh_pct", "% (SHT45)", "%.0f")],
        ["Pressure", condition_range(c, "pressure_hpa", "hPa (BMP581)", "%.1f"), "Water", E(info["water"])],
        ["Water temperature", condition_range(c, "water_c", "°C (DS18B20%s)" % (", " + E(sensor) if sensor else ""), "%.1f"),
         "Density used", density],
        ["Special conditions", E(info["special_conditions"]), "Evaporation estimate",
         "≤ %s mm per run (%s)" % (num(max(s["evap_mm"] for s in stats), 3),
                                        "measured loss rate" if info["measured"].get("evaporation_g_per_h") is not None
                                        else "assumed 1 g/h loss")],
    ]
    story += [PageBreak(), Paragraph("4. Environmental conditions (Annex 6.A, 2(k))", H),
              pairs_table(env, [1.15 * inch, 2.4 * inch, 1.15 * inch, 2.6 * inch])]

    # 5 Run log
    hdr = ["Rate (mm/h)", "Run", "Start", "Duration (s)", "Tips per min", "Net mass (g)", "g per tip", "Ir (mm/h)",
           "Im (mm/h)", "e (%)", "Used"]
    rows = [[P(h, HC) for h in hdr]]
    shade, group, last = [], -1, None
    for r in runs:
        if r["rate_mm_h"] != last:
            group, last = group + 1, r["rate_mm_h"]
            shade.append(("LINEABOVE", (0, len(rows)), (-1, len(rows)), .9, GRID))
        if group % 2:
            shade.append(("BACKGROUND", (0, len(rows)), (-1, len(rows)), colors.HexColor("#f6f8fa")))
        w = "e" in r
        rows.append([P("%g" % r["rate_mm_h"], CELLC), P(str(r["run"]), CELLC), P(E((r.get("start_time") or "")[11:19]), CELLC),
                     P(num(r["duration_s"], 1), CELLC), P(num(r["tips_per_min"]), CELLC),
                     P(num(r["net_g"]) if w else "", CELLC), P(num(r["g_per_tip"], 3) if w else "", CELLC),
                     P(num(r["Ir"], 1) if w else "", CELLC), P(num(r["Im"], 1) if w else "", CELLC),
                     P(num(r["e"], 2, True) if w else "", CELLC), P(E(r["used"]), CELLC)])
    t = Table(rows, colWidths=[.62 * inch, .38 * inch, .72 * inch, .72 * inch, .66 * inch, .72 * inch, .62 * inch,
                               .66 * inch, .66 * inch, .6 * inch, .94 * inch], repeatRows=1)
    t.setStyle(style([("BACKGROUND", (0, 0), (-1, 0), HEAD)] + shade))
    story += [Paragraph("5. Run log (all runs, Annex 6.A, 2(l))", H), t]

    # 6 Run quality and checks
    bal = d["balance"]
    if bal:
        f_ = bal["final"]
        bal_text = ("Balanced with the load cell before the session (%s, %s), round %d of %d. Left %s mL, right %s mL; "
                    "sides differ by %s %% (limit %g %%)%s." %
                    (E(bal.get("method", "")), f_["time"][:10], f_["round"], len(bal["rounds"]), num(f_["left_avg_ml"]),
                     num(f_["right_avg_ml"]), num(f_["diff_pct"], 1), bal.get("limit_pct", 5.0),
                     "" if f_["balanced"] else ". NOT BALANCED"))
    else:
        bal_text = "[not recorded: run dyn_rain_cal.py --balance with the same gauge ID before the session]"
    backed = [k for k, v in d["funnel"].items() if v]
    unasked = [("%g" % s["rate"]) for s in stats if ("%g" % s["rate"]) not in d["funnel"]]
    funnel_text = ("Water backed up at %s mm/h; that and higher intensities are affected." % ", ".join(backed) if backed
                   else "Asked at every rate. No water backing up at any tested rate, so none are excluded.")
    if unasked:
        funnel_text += " Not answered at %s mm/h." % ", ".join(unasked)
    disc = d["discarded"]
    disc_text = ("None. " if not disc else "%d: %s. " % (len(disc), "; ".join(
        "%g mm/h run %d (%s)" % (r["rate_mm_h"], r["run"], E(r.get("note") or "flagged")) for r in disc))) + \
        "Only the lowest and highest error per rate are left out of the average."
    sides = [s for s in res["rates"] if s.get("side_heavy_g") is not None]
    checks = [
        ["Bucket balance (Annex 6.A, 2(b))", bal_text],
        ["Bucket sides during the runs", "; ".join("%g mm/h: %s and %s g per tip (%s %%)" % (
            s["rate_mm_h"], num(s["side_heavy_g"]), num(s["side_light_g"]), num(s["side_mass_diff_pct"], 1, True))
            for s in sides) if sides else "Not measured (manual weighing)."],
        ["Irregular tip intervals", "%d runs flagged (possible missed or extra tip)." % d["irregular"]],
        ["Drip drift", "%d runs ended more than 5 %% from the target tips per minute." % d["drift"]],
        ["Funnel storage (Annex 6.A, 3(e))", funnel_text],
        ["Runs discarded", disc_text],
    ]
    t = Table([[P(a, CELLB), P(b)] for a, b in checks], colWidths=[2.0 * inch, 5.3 * inch])
    t.setStyle(style([("BACKGROUND", (0, 0), (0, -1), HEAD)]))
    story += [Spacer(1, 6), Paragraph("6. Run quality and checks", H), t]

    # 7 Uncertainty
    keys = ["mass", "time", "density", "area", "flow", "evaporation", "repeatability"]
    rows = [[P("Standard uncertainty (%)", CELLB)] + [P("%g mm/h" % s["rate"], HC) for s in stats]]
    for k in keys:
        rows.append([P(E(d["labels"][k]))] + [P(num(s["comp"][k], 3), CELLC) for s in stats])
    rows.append([P("Combined standard uncertainty u<sub>c</sub>", CELLB)] + [P(num(s["uc"]), CELLC) for s in stats])
    rows.append([P("Expanded uncertainty U = 2 u<sub>c</sub> (k = 2)", CELLB)] + [P("<b>%s</b>" % num(s["U"]), CELLC) for s in stats])
    col = (W - 2.9 * inch) / max(1, len(stats))
    t = Table(rows, colWidths=[2.9 * inch] + [col] * len(stats))
    t.setStyle(style([("BACKGROUND", (0, 0), (-1, 0), HEAD), ("BACKGROUND", (0, -2), (-1, -1), colors.HexColor("#f3f7fb"))]))
    umax = max(s["U"] for s in stats)
    story += [PageBreak(), Paragraph("7. Uncertainty of the reference intensity (Annex 6.A, section 4)", H), t, Spacer(1, 3),
              Paragraph("Largest expanded uncertainty of Ir: %s %% (k = 2), %s the 1 %% required by Annex 6.A, 2(a). Items marked "
                        "assumed are not yet measured. Flow steadiness is the standard uncertainty of each run's mean flow from "
                        "the spread of its tip intervals, taken in pairs (one fill of each bucket side). Repeatability is the "
                        "standard deviation of the run errors divided by the square root of the number of runs. Flow generator "
                        "and flow measuring contributions are treated as independent, as in the Annex."
                        % (num(umax), "below" if umax < U_LIMIT_PCT else "NOT below"), SM)]

    # 8 Method and statements
    n = res["tips_per_run"]
    mass_src = ("the load cell: the difference of the median readings in the second before the run's first tip and before "
                "the tip after its last" if d["loadcell"] else "the scale: full minus starting bucket weight")
    stm = [
        "<b>Reference intensity.</b> Ir = M / (ρ · A · T). M is the net water mass from %s; T the time of the "
        "run's %d tip intervals, from the tip before its first tip to its %dth tip, the time its %d tips of water took; ρ "
        "the water density from the measured water temperature (Tanaka et al. 2001); A the %s area of the rim." %
        (mass_src, n, n, n, "measured" if d["d_meas"] else "design"),
        "<b>Measured intensity and time averaging.</b> Im = %d tips × %g mm / T, so each Im is the average over one run. "
        "Tip times are logged to 1 ms." % (n, res["mm_per_tip"]),
        "<b>Error.</b> e = (Im − Ir) / Ir × 100 % (Annex 6.A, Equation 6.A.1).",
        "<b>Averaging.</b> Five runs per rate. The runs with the lowest and highest e are discarded and the mean of the remaining "
        "three gives e, Ir and Im. The error bar spans all runs.",
    ]
    cf = d["coef"]
    if cf is not None and len(cf) == 3:
        stm.append("<b>Fitted curve.</b> Ir = c<sub>0</sub> + c<sub>1</sub> Im + c<sub>2</sub> Im<super>2</super> with "
                   "c<sub>0</sub> = %.4f, c<sub>1</sub> = %.5f, c<sub>2</sub> = %.3e, fitted to the %d averaged points. Largest "
                   "residual %s %%. It is for interpolation only, and no correction is applied." %
                   (cf[2], cf[1], cf[0], len(stats), num(d["fit_res"])))
    elif cf is not None:
        stm.append("<b>Fitted curve.</b> Ir = c<sub>0</sub> + c<sub>1</sub> Im with c<sub>0</sub> = %.4f, c<sub>1</sub> = %.5f "
                   "(only two intensities). For interpolation only; no correction is applied." % (cf[1], cf[0]))
    stm += ["<b>Rim sizing.</b> r = √(V × 1000 / 0.2 / π), with V the mean mL per tip at the sizing rate. "
            "Because of this, e is zero at the sizing rate with the design area.",
            "<b>Collector area.</b> " + ("A is the measured rim area." if d["d_meas"] else
                                         "A is the designed rim area. The printed rim is to be measured with calipers and the "
                                         "certificate reissued if it differs from the design."),
            "<b>Step response.</b> Not required for tipping bucket gauges (Annex 6.A, 3(f))."]
    story += [Paragraph("8. Method and statements", H)] + [Paragraph("%d. %s" % (i + 1, s_), LI) for i, s_ in enumerate(stm)]

    # 9 Equipment and traceability
    eq = []
    for q, inst, ident_ in info["equipment"]:
        if q == "Water temperature" and sensor:
            inst = "%s (%s)" % (inst, sensor)
        if q == "Net mass" and not d["loadcell"]:
            inst = "1 g scale (manual weighing)"
        eq.append([P(E(q)), P(E(inst)), P(E(ident_))])
    t = Table([[P("Quantity", CELLB), P("Instrument", CELLB), P("ID and traceability", CELLB)]] + eq,
              colWidths=[1.75 * inch, 3.3 * inch, 2.25 * inch])
    t.setStyle(style([("BACKGROUND", (0, 0), (-1, 0), HEAD)]))
    sign = Table([[P("Calibrated by:  " + E(info["operator"])), P("Reviewed by:  " + E(info["reviewer"]))],
                  [P("Signature / date:  ________________"), P("Signature / date:  ________________")]],
                 colWidths=[3.65 * inch, 3.65 * inch])
    sign.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 6)]))
    story += [Paragraph("9. Equipment and traceability", H), t, Spacer(1, 10), sign]

    footer = "3D-PAWS dynamic rain gauge calibration certificate, %s, gauge %s.%s" % (
        cert_no, res["gauge_id"], " DRAFT, not valid." if draft else "")

    class NumCanvas(canvas.Canvas):
        def __init__(self, *a, **k):
            canvas.Canvas.__init__(self, *a, **k)
            self._saved = []

        def showPage(self):
            self._saved.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            for st in self._saved:
                self.__dict__.update(st)
                self.furniture(len(self._saved))
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)

        def furniture(self, pages):
            w, h = letter
            if draft:
                self.saveState()
                self.setFillColor(colors.HexColor("#1f2933"))
                self.setFillAlpha(0.06)
                self.translate(w / 2, h / 2)
                self.rotate(38)
                self.setFont(bold, 120)
                self.drawCentredString(0, -30, "DRAFT")
                self.restoreState()
            self.setFont(font, 7)
            self.setFillColor(colors.HexColor("#52606d"))
            self.drawString(.6 * inch, .38 * inch, footer)
            self.drawRightString(w - .6 * inch, .38 * inch, "Page %d of %d" % (self._pageNumber, pages))

    doc = SimpleDocTemplate(out, pagesize=letter, leftMargin=.6 * inch, rightMargin=.6 * inch, topMargin=.5 * inch,
                            bottomMargin=.6 * inch, title="3D-PAWS Dynamic Calibration Certificate %s" % cert_no,
                            author="3D-PAWS")
    doc.build(story, canvasmaker=NumCanvas)


# ----------------------------------------------------------------- numbering and main
def certificate_number(folder, info, draft):
    """A clean certificate gets the next number (kept if the folder is rebuilt); a draft is not numbered."""
    if draft:
        return "DRAFT (not numbered)"
    path = os.path.join(folder, "certificate.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)["certificate_no"]
    no = "%s%04d" % (info["certificate_prefix"], int(info["next_certificate_number"]))
    with open(path, "w") as f:
        json.dump({"certificate_no": no, "issued": dt.datetime.now().isoformat(timespec="seconds")}, f, indent=2)
    with open(info_path()) as f:
        stored = json.load(f)
    stored["next_certificate_number"] = int(info["next_certificate_number"]) + 1
    with open(info_path(), "w") as f:
        json.dump(stored, f, indent=2)
    return no


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="a dyn_rain_cal_<GaugeID>_<date_time> results folder")
    a = ap.parse_args()
    folder = os.path.abspath(a.folder)
    if not os.path.exists(os.path.join(folder, "result.json")):
        sys.exit("No result.json in %s. Finish the calibration (choose the sizing rate) first." % folder)
    info, created = load_info()
    if created:
        print("Created %s with [bracketed] placeholders; fill it in and run this again." % info_path())
    d = analyze(folder, info)
    cert_no = certificate_number(folder, info, bool(d["draft"]))
    out = os.path.join(folder, "certificate.pdf")
    build_pdf(d, out, cert_no)
    print("Saved %s (%s)" % (out, cert_no))
    if d["draft"]:
        print("DRAFT until:")
        for x in d["draft"]:
            print("  - " + x)


if __name__ == "__main__":
    main()
