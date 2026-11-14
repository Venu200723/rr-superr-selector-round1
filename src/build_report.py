#!/usr/bin/env python3
"""Build the SupeRR Selector Round 1 methodology PDF."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image, KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = Path("/workspace/rr_auction")
OUT = ROOT / "output"
CHARTS = ROOT / "charts"
PDF = OUT / "RR_SupeRR_Selector_Round1_Report.pdf"

RR_PURPLE = colors.HexColor("#2541B2")
RR_PINK = colors.HexColor("#E11D48")
RR_GOLD = colors.HexColor("#F59E0B")
RR_DARK = colors.HexColor("#0F172A")
RR_MUTED = colors.HexColor("#475569")
RR_LIGHT = colors.HexColor("#F1F5F9")
RR_TEAL = colors.HexColor("#0D9488")


def styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle(
        name="CoverTitle", fontName="Helvetica-Bold", fontSize=22,
        leading=28, textColor=colors.white, alignment=TA_CENTER, spaceAfter=8,
    ))
    ss.add(ParagraphStyle(
        name="CoverSub", fontName="Helvetica", fontSize=12,
        leading=16, textColor=colors.white, alignment=TA_CENTER, spaceAfter=4,
    ))
    ss.add(ParagraphStyle(
        name="H1", fontName="Helvetica-Bold", fontSize=16,
        leading=20, textColor=RR_PURPLE, spaceBefore=14, spaceAfter=8,
    ))
    ss.add(ParagraphStyle(
        name="H2", fontName="Helvetica-Bold", fontSize=12.5,
        leading=16, textColor=RR_DARK, spaceBefore=10, spaceAfter=5,
    ))
    ss.add(ParagraphStyle(
        name="Body", fontName="Helvetica", fontSize=9.5,
        leading=13, textColor=RR_DARK, alignment=TA_JUSTIFY, spaceAfter=6,
    ))
    ss.add(ParagraphStyle(
        name="BodyBullet", fontName="Helvetica", fontSize=9.5,
        leading=13, textColor=RR_DARK, leftIndent=8, spaceAfter=3,
    ))
    ss.add(ParagraphStyle(
        name="Caption", fontName="Helvetica-Oblique", fontSize=8,
        leading=10, textColor=RR_MUTED, alignment=TA_CENTER, spaceBefore=2, spaceAfter=8,
    ))
    ss.add(ParagraphStyle(
        name="TableCell", fontName="Helvetica", fontSize=7.5,
        leading=9.5, textColor=RR_DARK,
    ))
    ss.add(ParagraphStyle(
        name="TableHeader", fontName="Helvetica-Bold", fontSize=7.5,
        leading=9.5, textColor=colors.white, alignment=TA_CENTER,
    ))
    ss.add(ParagraphStyle(
        name="Footer", fontName="Helvetica", fontSize=8,
        leading=10, textColor=RR_MUTED, alignment=TA_CENTER,
    ))
    ss.add(ParagraphStyle(
        name="Formula", fontName="Courier", fontSize=8,
        leading=11, textColor=RR_DARK, backColor=RR_LIGHT,
        leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=6,
    ))
    return ss


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(RR_PURPLE)
    canvas.rect(0, A4[1] - 12 * mm, A4[0], 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(15 * mm, A4[1] - 7.5 * mm, "Rajasthan Royals  |  SupeRR Selector Season 2  |  Round 1")
    canvas.drawRightString(A4[0] - 15 * mm, A4[1] - 7.5 * mm, "Most Reliable Players Under Pressure")
    canvas.setFillColor(RR_LIGHT)
    canvas.rect(0, 0, A4[0], 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(RR_MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(15 * mm, 4 * mm, "Confidential — competition submission")
    canvas.drawRightString(A4[0] - 15 * mm, 4 * mm, f"Page {doc.page}")
    canvas.restoreState()


def cover_page(ss, meta):
    # Custom cover via a full-bleed table
    data = [[
        Paragraph("RAJASTHAN ROYALS", ss["CoverSub"]),
    ], [
        Paragraph("SupeRR Selector Season 2", ss["CoverSub"]),
    ], [
        Paragraph("ROUND 1 METHODOLOGY REPORT", ss["CoverTitle"]),
    ], [
        Paragraph("Identify the Most Reliable Players Under Pressure", ss["CoverSub"]),
    ], [
        Paragraph(
            f"Data: IPL &amp; T20I 2022–2026  ·  {meta['n_eligible_batters']} eligible batters  ·  "
            f"{meta['n_eligible_bowlers']} eligible bowlers  ·  High-pressure threshold Q75 = {meta['hp_threshold']:.3f}",
            ss["CoverSub"],
        ),
    ]]
    t = Table(data, colWidths=[180 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), RR_PURPLE),
        ("TOPPADDING", (0, 0), (-1, 0), 28),
        ("TOPPADDING", (0, 2), (-1, 2), 18),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 24),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -2), 4),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0, RR_PURPLE),
    ]))
    return [Spacer(1, 25 * mm), t, Spacer(1, 10 * mm)]


def p(text, style):
    return Paragraph(text, style)


def bullet_list(items, ss):
    return ListFlowable(
        [ListItem(Paragraph(i, ss["BodyBullet"]), leftIndent=10, bulletColor=RR_PINK) for i in items],
        bulletType="bullet", start="•", leftIndent=12, bulletFontSize=9,
    )


def styled_table(headers, rows, col_widths, ss):
    head = [Paragraph(h, ss["TableHeader"]) for h in headers]
    body = []
    for row in rows:
        body.append([Paragraph(str(c), ss["TableCell"]) for c in row])
    t = Table([head] + body, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), RR_PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in range(1, len(body) + 1):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), RR_LIGHT))
    t.setStyle(TableStyle(style_cmds))
    return t


def team_label(r):
    t = r.get("latest_ipl_team")
    if isinstance(t, str) and t:
        return f"{t} (IPL {int(r['latest_ipl_season'])})"
    n = r.get("national_teams")
    return str(n) if isinstance(n, str) else str(r.get("team_display", ""))


def avail_table(df, ss):
    rows = [[int(r["rank"]), r["player_name"], r["availability_status"],
             r["availability_note"] if isinstance(r["availability_note"], str) else "",
             r["source"] if isinstance(r["source"], str) else ""] for _, r in df.iterrows()]
    return styled_table(["Rk", "Player", "Status", "Note", "Source"], rows,
                        [9*mm, 28*mm, 28*mm, 72*mm, 45*mm], ss)


def img(path, width=170 * mm):
    im = Image(str(path))
    aspect = im.imageHeight / float(im.imageWidth)
    im.drawWidth = width
    im.drawHeight = width * aspect
    return im


def _f(v, nd=1):
    return f"{v:.{nd}f}"


def dashboard(ss, meta, topb, topw):
    ov = pd.read_csv(OUT / "validation_hp_vs_normal.csv", index_col=0)
    hp, nm = ov["High pressure"], ov["Normal"]
    out = [p("Round 1 at a Glance", ss["H1"])]
    out.append(p(
        "<b>Pressure, in one line:</b> a 0-1 index per ball from chase difficulty (RRR vs par, wickets and "
        "balls left), death overs, collapses and knockouts; the top 25% of balls "
        f"(index &ge; {meta['hp_threshold']:.3f}) are high-pressure. Players are scored on lift vs their own "
        "baseline, phase-adjusted output vs peers, survival / wickets, and match-to-match consistency. "
        "Pakistan and Bangladesh players are excluded (not available in the IPL).",
        ss["Body"]))
    out.append(p(
        f"<b>Validated:</b> high-pressure balls have a wicket every {hp['balls_per_wicket']:.1f} legal balls "
        f"vs {nm['balls_per_wicket']:.1f} normally ({hp['wicket_pct']:.2f}% vs {nm['wicket_pct']:.2f}%), and chasing "
        "sides that spend the most of a chase under pressure win far less often (Section 2.3).",
        ss["Body"]))

    small = ParagraphStyle("dash", parent=ss["TableCell"], fontSize=7.2, leading=8.8)
    hs = ParagraphStyle("dashh", parent=ss["TableHeader"], fontSize=7.2, leading=8.8)

    def mini(df, kind):
        head = ["#", "Batter" if kind == "bat" else "Bowler", "Headline (HP)", "Score"]
        rows = [[Paragraph(h, hs) for h in head]]
        for _, r in df.iterrows():
            if kind == "bat":
                stat = f"SR {r['hp_sr']:.1f} vs {r['base_sr']:.1f}; {100*r['consist_pos_share']:.0f}% +inns"
            else:
                stat = f"Econ {r['hp_econ']:.2f} vs {r['base_econ']:.2f}; {int(r['hp_wkts'])} wkts"
            rows.append([Paragraph(str(int(r["rank"])), small), Paragraph(r["player_name"], small),
                         Paragraph(stat, small), Paragraph(f"{r['composite']:.3f}", small)])
        t = Table(rows, colWidths=[6*mm, 27*mm, 43*mm, 12*mm])
        cmds = [("BACKGROUND", (0, 0), (-1, 0), RR_PURPLE if kind == "bat" else RR_PINK),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]
        for k in range(2, len(rows), 2):
            cmds.append(("BACKGROUND", (0, k), (-1, k), RR_LIGHT))
        t.setStyle(TableStyle(cmds))
        return t

    pair = Table([[mini(topb, "bat"), mini(topw, "bowl")]], colWidths=[91*mm, 91*mm])
    pair.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    out.append(pair)
    out.append(Spacer(1, 3*mm))
    charts = Table([[img(CHARTS / "09_validation_deciles.png", 89*mm), img(CHARTS / "10_validation_outcome.png", 80*mm)],
                    [img(CHARTS / "03_top10_batters_sr.png", 89*mm), img(CHARTS / "04_top10_bowlers_econ.png", 89*mm)]],
                   colWidths=[91*mm, 91*mm])
    charts.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    out.append(charts)
    out.append(p("HP = high-pressure balls. Baselines are the player's own non-pressure balls. Score = composite "
                 "(Section 4.3). Full tables in Sections 6-7; availability in Section 8.1.", ss["Caption"]))
    return out


def validation_section(ss, meta):
    ov = pd.read_csv(OUT / "validation_hp_vs_normal.csv", index_col=0)
    ph = pd.read_csv(OUT / "validation_by_phase.csv")
    dec = pd.read_csv(OUT / "validation_deciles.csv")
    oc = pd.read_csv(OUT / "validation_outcome.csv")
    c = meta["charts"]
    hp, nm, gap = ov["High pressure"], ov["Normal"], ov["Gap (HP - Normal)"]
    out = [p("2.3 Validation: does the index capture real pressure?", ss["H2"])]
    out.append(p(
        "The index was built from match state only (score, target, wickets, balls, over, stage); ball outcomes "
        "were never used to set it. We therefore test it against outcomes it did not see.", ss["Body"]))
    labels = [("run_rate", "Run rate (runs per 6 legal balls)", 2), ("dot_pct", "Dot-ball %", 2),
              ("boundary_pct", "Boundary % (of balls faced)", 2), ("wicket_pct", "Wickets per 100 legal balls", 2),
              ("bowler_wkt_pct", "Bowler wickets per 100 legal balls", 2), ("balls_per_wicket", "Balls per wicket", 2),
              ("batting_sr", "Batting strike rate", 1)]
    rows = [[lab, _f(hp[k], d), _f(nm[k], d), f"{gap[k]:+.{d}f}"] for k, lab, d in labels]
    rows.insert(0, ["Balls", f"{int(hp['balls']):,}", f"{int(nm['balls']):,}", ""])
    out.append(styled_table(["Metric (all 200,999 balls)", "High pressure", "Normal", "Gap"], rows,
                            [70*mm, 32*mm, 32*mm, 26*mm], ss))
    out.append(p("Table V1. High-pressure (top quartile) vs normal balls, whole dataset "
                 "(output/validation_hp_vs_normal.csv).", ss["Caption"]))
    out.append(p(
        f"<b>Dismissal risk is clearly higher:</b> {hp['wicket_pct']:.2f} vs {nm['wicket_pct']:.2f} wickets per 100 "
        f"legal balls, i.e. a wicket every {hp['balls_per_wicket']:.1f} balls instead of {nm['balls_per_wicket']:.1f} "
        f"(about {100*(hp['wicket_pct']/nm['wicket_pct']-1):.0f}% more often). "
        f"<b>Scoring is not lower overall</b>: the pooled run rate is {hp['run_rate']:.2f} vs {nm['run_rate']:.2f}, "
        "because high-pressure balls are concentrated in the death overs, where everyone scores faster. "
        "Batters under pressure are forced to attack <i>and</i> get out more. That is the risk-reward "
        "squeeze the brief asks us to measure.", ss["Body"]))
    # phase-controlled
    prow = []
    for band in ["Overs 1-6", "Overs 7-15", "Overs 16-20"]:
        a = ph[(ph.band == band) & (ph.hp == "High pressure")].iloc[0]
        b = ph[(ph.band == band) & (ph.hp == "Normal")].iloc[0]
        prow.append([band, f"{int(a.balls):,} / {int(b.balls):,}", f"{a.run_rate:.2f} / {b.run_rate:.2f}",
                     f"{a.batting_sr:.1f} / {b.batting_sr:.1f}", f"{a.wicket_pct:.2f} / {b.wicket_pct:.2f}",
                     f"{a.dot_pct:.1f} / {b.dot_pct:.1f}"])
    out.append(styled_table(["Phase", "Balls HP / N", "Run rate HP / N", "SR HP / N", "Wkt% HP / N", "Dot% HP / N"],
                            prow, [24*mm, 30*mm, 28*mm, 28*mm, 26*mm, 26*mm], ss))
    out.append(p("Table V2. Same comparison within each phase (output/validation_by_phase.csv).", ss["Caption"]))
    d = ph[(ph.band == "Overs 16-20")]
    dh, dn = d[d.hp == "High pressure"].iloc[0], d[d.hp == "Normal"].iloc[0]
    out.append(p(
        f"<b>Like-for-like, within the same phase,</b> the wicket rate is higher under pressure in every band. "
        f"In the death overs, where the comparison matters most, pressure also suppresses scoring: run rate "
        f"{dh.run_rate:.2f} vs {dn.run_rate:.2f}, strike rate {dh.batting_sr:.1f} vs {dn.batting_sr:.1f}, dots "
        f"{dh.dot_pct:.1f}% vs {dn.dot_pct:.1f}%. In the powerplay and middle overs, high-pressure balls are "
        "scored slightly faster than normal ones, because chasing sides that are behind the rate have to attack. "
        "So the honest summary is that pressure reliably raises dismissal risk, and lowers scoring at the death.",
        ss["Body"]))
    out.append(img(CHARTS / "09_validation_deciles.png", 150*mm))
    out.append(p("Figure V1. Wicket rate, dot % and boundary % by Pressure Index decile "
                 "(output/validation_deciles.csv).", ss["Caption"]))
    w1, w10 = dec.iloc[0], dec.iloc[-1]
    low5 = dec.iloc[:5]["wicket_pct"].mean(); hi5 = dec.iloc[5:]["wicket_pct"].mean()
    out.append(p(
        f"<b>Monotonicity.</b> The wicket rate rises with pressure: from {w1.wicket_pct:.2f} per 100 balls in "
        f"decile 1 to {w10.wicket_pct:.2f} in decile 10 (mean {low5:.2f} in deciles 1-5 vs {hi5:.2f} in "
        f"deciles 6-10; Spearman rank correlation between decile and wicket rate = "
        f"{c['val_spearman_wicket']:.2f}). The trend is strong but <i>not strictly</i> monotonic: decile 8 dips "
        "back to the normal level, and decile 3 sits below decile 1. Run rate shows "
        f"no consistent trend (Spearman {c['val_spearman_runrate']:.2f}), for the same phase-mix reason as "
        "above. We report this openly. It is why the batting score uses phase-adjusted runs above expected "
        "rather than raw strike rate alone.", ss["Body"]))
    out.append(img(CHARTS / "10_validation_outcome.png", 120*mm))
    out.append(p("Figure V2. Chasing-side win % by how much of the chase was spent under high pressure "
                 "(output/validation_outcome.csv).", ss["Caption"]))
    q1, q4 = oc.iloc[0], oc.iloc[-1]
    out.append(p(
        f"<b>Outcome check.</b> Splitting completed chases into quartiles by the share of balls spent under high "
        f"pressure, the chasing side won {q1.chase_win_pct:.1f}% of the calmest quartile ({int(q1.matches)} matches) "
        f"and only {q4.chase_win_pct:.1f}% of the most-pressured quartile ({int(q4.matches)} matches). At ball level, "
        f"the side batting on a high-pressure ball went on to win {c['val_chase_win_hp_ball']:.1f}% of the time, "
        f"against {c['val_chase_win_normal_ball']:.1f}% on normal balls. <i>Caveat:</i> this check is partly built in, "
        "because a chase that falls behind the rate both scores higher on the index and tends to lose. "
        "It confirms the index tracks genuine jeopardy, but it is supporting evidence, not independent proof.",
        ss["Body"]))
    out.append(p(
        "<b>Conclusion:</b> high-pressure balls are measurably different: about 30% more wickets, tighter death "
        "overs, and strongly linked to losing a chase. The index captures real pressure. The weak point is "
        "raw scoring rate outside the death overs, and the phase adjustment in Section 4 addresses it.",
        ss["Body"]))
    return out


def rr_fit_section(ss, topb, topw):
    ps = pd.read_csv(OUT / "rr_fit_phase_stats.csv")

    def g(name, phase):
        return ps[(ps.player_name == name) & (ps.phase == phase)].iloc[0]

    bosch, mohit = g("Corbin Bosch", "Overs 16-20"), g("Mohit Sharma", "Overs 16-20")
    sant = g("Mitchell Santner", "Overs 7-11")
    dub, rink = g("Shubham Dubey", "Overs 16-20"), g("Rinku Singh", "Overs 16-20")
    jacks = g("William Jacks", "Overs 16-20")
    out = [p("8. How the Top Picks Strengthen the RR Squad", ss["H1"])]
    out.append(p("8.0 RR context: what the 2026 season exposed", ss["H2"]))
    out.append(bullet_list([
        "<b>Squad (IPL 2026):</b> captain Riyan Parag; batting led by Yashasvi Jaiswal, Vaibhav Sooryavanshi and "
        "Dhruv Jurel, with Shimron Hetmyer, Donovan Ferreira and Shubham Dubey in the lower middle; attack led by "
        "Jofra Archer with Nandre Burger, Sandeep Sharma, Tushar Deshpande, Ravi Bishnoi, Ravindra Jadeja and "
        "Adam Milne (The Hindu squad list; RR official site).",
        "<b>Bowling control was the problem:</b> RR conceded 9.92 runs per over overall, with the second-worst "
        "economy in overs 7-11 (9.71), even though they took a wicket every 18.57 balls. Sandeep Sharma went at "
        "11.39 (Hindustan Times, 12 Nov 2026). After a strong first half they had the league's worst economy, "
        "and were the first side to concede 220+ in four straight games (Cricbuzz, May 2026). Spin was flagged as "
        "a concern with Jadeja and Bishnoi in and out (The Hindu, 25 May 2026).",
        "<b>Finishing was the other gap:</b> RR's death-overs scoring rate of 10.62 ranked 7th (Hindustan Times, "
        "12 Nov 2026). Hetmyer and Shanaka 'failed to offer the reliability RR needed at the death', and the "
        "report card called for 'one more Indian death-overs option' and an overseas all-rounder who can "
        "'finish games and ideally bowl at the death' (Sports Yaari report card, 31 May 2026).",
    ], ss))
    out.append(p("Need-to-pick mapping (numbers from rr_fit_phase_stats.csv)", ss["H2"]))
    rows = [
        ["Indian death-overs bowler", "Mohit Sharma (bowler #6)",
         f"HP death overs: {int(mohit.hp_balls)} balls, econ {mohit.hp_econ:.2f}, {int(mohit.hp_wkts)} wkts; "
         "27 HP wickets, all in the IPL"],
        ["Overseas all-rounder who bowls at the death", "Corbin Bosch (bowler #1)",
         f"HP death overs: {int(bosch.hp_balls)} balls, econ {bosch.hp_econ:.2f}, {int(bosch.hp_wkts)} wkts; "
         "positive in 100% of pressure spells"],
        ["Middle-overs (7-11) control and spin", "Mitchell Santner (bowler #2)",
         f"HP overs 7-11: {int(sant.hp_balls)} balls, econ {sant.hp_econ:.2f}, {int(sant.hp_wkts)} wkts "
         "(RR's overs 7-11 economy was 9.71)"],
        ["Reliable death-overs finisher", "Shubham Dubey (batter #4, already RR)",
         f"HP death overs: {int(dub.hp_balls)} balls at SR {dub.hp_sr:.1f}; pressure SR 182.6 vs 102.0 baseline"],
        ["Finisher (auction / trade target)", "Rinku Singh (batter #9)",
         f"HP death overs: {int(rink.hp_balls)} balls at SR {rink.hp_sr:.1f}, only {int(rink.hp_wkts)} dismissals"],
        ["Overseas finisher if Hetmyer's slot frees", "William Jacks (batter #3)",
         f"HP death overs: SR {jacks.hp_sr:.1f} on {int(jacks.hp_balls)} balls (small sample); also bowls off-spin"],
    ]
    out.append(styled_table(["RR need (sourced)", "Pick", "Pressure evidence (our data)"], rows,
                            [48*mm, 42*mm, 92*mm], ss))
    out.append(p("Table 3. RR needs mapped to top picks. HP = high-pressure balls. Availability caveats are in "
                 "Section 8.1: Mohit's 2026 status is unreported, Bosch is at MI and Santner is a likely MI retention.",
                 ss["Caption"]))
    out.append(p("Other picks, in brief", ss["H2"]))
    out.append(bullet_list([
        "<b>Reeza Hendricks</b>: overseas top order; pressure SR 188.4 vs 129.6 baseline over 241 HP balls (T20I only).",
        "<b>Shreyas Iyer</b>: largest HP sample in the top 10 (452 balls); SR 186.4, 70% positive innings.",
        "<b>Jos Buttler / Sai Sudharsan</b>: high-volume top-order reliability (393 and 366 HP balls, SR 177.3 and 176.2).",
        "<b>Naman Dhir / Sameer Rizvi / Shashank Singh</b>: young Indian middle order; pressure SR 196.8 / 170.2 / 175.1.",
        "<b>McCarthy (right-arm medium) / Humphreys (left-arm spin)</b>: beat expected HP economy by ~0.30 runs per ball.",
        "<b>Narine / Mujeeb / Motie</b>: spin with 83% / 82% / 69% positive pressure spells. "
        "<b>Eshan Malinga</b>: right-arm seam, 24 HP wickets. <b>Harpreet Brar</b> (No. 10): Indian left-arm "
        "spinner; HP economy 7.57 vs 8.51 baseline, best in overs 12-15 (5.62 on 48 HP balls), a second Indian "
        "spin option alongside Bishnoi and Jadeja.",
    ], ss))
    return out


def build():
    ss = styles()
    meta = json.load(open(OUT / "meta.json"))
    bat = pd.read_csv(OUT / "batter_rankings.csv")
    bowl = pd.read_csv(OUT / "bowler_rankings.csv")
    topb = pd.read_csv(OUT / "top10_batters.csv").sort_values("rank")
    topw = pd.read_csv(OUT / "top10_bowlers.csv").sort_values("rank")
    verify = meta["verify"]

    story = []
    story += cover_page(ss, meta)
    story.append(PageBreak())
    story += dashboard(ss, meta, topb, topw)
    story.append(PageBreak())

    # Executive summary
    story.append(p("1. Executive Summary", ss["H1"]))
    story.append(p(
        "This report delivers a fully data-driven ranking of the batters and bowlers who are most "
        "<b>reliable under pressure</b> in IPL and Full-Member T20I cricket from 2022 through 2026. "
        "We define pressure as a continuous, ball-level index combining chase difficulty (required run "
        "rate, wickets in hand, balls remaining), death-over intensity, collapse signals, and knockout "
        "context. Balls in the top quartile of that index are labelled high-pressure.",
        ss["Body"],
    ))
    story.append(p(
        "Players are scored on four pillars: (1) how their pressure output compares with their own "
        "baseline (the “rise to the occasion” lift), (2) absolute pressure performance versus peers, "
        "adjusted for the difficulty of the overs they faced, (3) survival / wicket-taking under "
        "pressure, and (4) match-to-match consistency. Small samples are shrunk toward the population "
        "mean (empirical Bayes), and eligibility requires both volume and auction-relevant exposure "
        "(meaningful IPL sample or Full-Member T20I sample).",
        ss["Body"],
    ))
    story.append(p(
        "<b>Headline picks.</b> Among batters, <b>Reeza Hendricks</b> and <b>Shreyas Iyer</b> lead "
        "a group of finishers and middle-order accelerators who raise their strike rate sharply when "
        "the chase tightens, including RR's own <b>Shubham Dubey</b> and former Royal <b>Jos Buttler</b>. "
        "Among bowlers, <b>Corbin Bosch</b> is a clear No. 1 (positive contribution in 100% of his pressure "
        "spells), followed by the high-floor left-arm spin of <b>Mitchell Santner</b> and two Irish "
        "options (seamer Barry McCarthy, left-arm spinner Matthew Humphreys) who beat the expected "
        "economy for the overs they bowled. Section 2.3 validates the index against the data itself. Because Pakistan and Bangladesh players are not "
        "available in the IPL, they are excluded from the eligible pool (Section 5).",
        ss["Body"],
    ))

    # Pressure definition
    story.append(p("2. Pressure Definition &amp; Rationale", ss["H1"]))
    story.append(p("2.1 Continuous Pressure Index", ss["H2"]))
    story.append(p(
        "Every delivery receives a Pressure Index in [0, 1] built from transparent, match-state signals:",
        ss["Body"],
    ))
    story.append(bullet_list([
        "<b>Chase difficulty (weight 0.50).</b> In the 2nd innings we combine a sigmoid of (RRR − 8.5) "
        "with a resource-scarcity term from wickets in hand and balls remaining. Live chases "
        "(RRR ≤ 16) receive full weight; desperate chases are dampened so hopeless pursuits do not "
        "dominate the label.",
        "<b>Death-over intensity (0.25).</b> Overs 16–20 are inherently high-leverage; over 15 and 14 "
        "receive partial credit. Death pressure is slightly stronger in chases than in the 1st innings.",
        "<b>Collapse pressure (0.15).</b> Wickets in the previous 12 balls plus few wickets in hand, "
        "emphasised in overs 6–15 when a side is folding.",
        "<b>Chase × death interaction (0.10)</b> plus a <b>knockout / final boost (+0.18)</b> when "
        "<font face='Courier'>knock_out=1</font> or the stage is Final / Qualifier / Eliminator / Semi-final.",
    ], ss))
    story.append(p(
        "High-pressure balls are those with Pressure Index ≥ the 75th percentile of all balls in the "
        f"dataset (threshold = <b>{meta['hp_threshold']:.4f}</b>). This yields exactly the top quartile "
        "(~25% of balls), a threshold that cleanly separates tense passages from routine ones.",
        ss["Body"],
    ))
    story.append(p("2.2 Evidence that the threshold is meaningful", ss["H2"]))
    story.append(img(CHARTS / "01_pressure_distribution.png", 160 * mm))
    story.append(p("Figure 1. Distribution of the ball-level Pressure Index with the Q75 high-pressure threshold.", ss["Caption"]))
    story.append(img(CHARTS / "08_hp_by_over.png", 160 * mm))
    story.append(p(
        "Figure 2. Share of balls labelled high-pressure by over and innings — concentrated in death overs "
        "and rising through the second innings, as intended.",
        ss["Caption"],
    ))
    story.append(img(CHARTS / "02_example_pressure_passage.png", 160 * mm))
    story.append(p(
        f"Figure 3. Worked example — match {meta['charts'].get('example_match_id')}: "
        f"{meta['charts'].get('example_result')}. Pink bars mark balls above the high-pressure threshold; "
        "they align with the tense phase of the chase.",
        ss["Caption"],
    ))

    story += validation_section(ss, meta)

    # Data & cleaning
    story.append(PageBreak())
    story.append(p("3. Data, Cleaning &amp; Verified Semantics", ss["H1"]))
    story.append(p(
        "Source files: <font face='Courier'>ball_by_ball.csv</font> (~201k deliveries), "
        "<font face='Courier'>matches.csv</font> (883), <font face='Courier'>competitions.csv</font>, "
        "teams, competition–team–player mapping, and playing XIs. Coverage spans IPL 2022–2026 and "
        "T20I series from 2022 onward (plus a small set of other T20 events).",
        ss["Body"],
    ))
    story.append(p("3.1 Verified ball semantics", ss["H2"]))
    story.append(bullet_list([
        f"<b>runs</b> = runs off the bat only. Total team runs on a ball = "
        f"<font face='Courier'>runs + extras1_runs + extras_2_runs</font>.",
        f"Reconstructing non-DLS matches won by a runs margin: "
        f"<b>{verify['n_match_reconstructed']}/{verify['n_runs_margin_non_dls']}</b> "
        f"({verify['pct_match']:.1f}%) match the published result margin within 1 run. "
        "Remaining mismatches are almost entirely DLS / Super Over cases.",
        "Wides do not count as balls faced; no-balls do. Bowling economy uses legal deliveries "
        "(non-wides) with all conceded runs (bat + extras).",
        "Bowler wickets include only: Caught, Bowled, LBW, Stumped, Hit Wicket. "
        "<b>Run-outs, retirements, and obstructing the field are excluded</b> from bowling credit "
        "but still count as batter dismissals for survival.",
    ], ss))
    story.append(p("3.2 Pooling IPL and T20I", ss["H2"]))
    story.append(p(
        "IPL balls are up-weighted (×1.35) relative to Full-Member T20I (×1.00) and other T20 "
        "(×0.70), reflecting the auction context without discarding international evidence. "
        "Eligibility further requires either ≥40 high-pressure IPL balls or ≥100 high-pressure "
        "Full-Member T20I balls, so Associate-only samples cannot top the list.",
        ss["Body"],
    ))

    # Metrics
    story.append(p("4. Performance Metrics, Baselines &amp; Scoring", ss["H1"]))
    story.append(p("4.1 Batting under pressure", ss["H2"]))
    story.append(bullet_list([
        "<b>Pressure SR</b> and <b>balls per dismissal (BPD)</b> on high-pressure balls faced.",
        "<b>Baseline SR</b> on the player’s own non-pressure balls (same competitions).",
        "<b>Phase-adjusted runs above expected (RAE)</b>: bat runs minus league expected runs/ball "
        "for that (innings, over) among high-pressure deliveries — so a 150 SR in over 19 of a chase "
        "is valued higher than the same SR in a softer middle-over spot.",
        "<b>Lift</b> = shrunk pressure SR − clamped baseline SR (baseline floored at 120 so chronically "
        "slow batters cannot farm lift by being “less slow”).",
        "<b>Consistency</b>: share of pressure innings with positive contribution vs own baseline, "
        "median contribution, and 20th-percentile pressure SR (floor).",
    ], ss))
    story.append(p("4.2 Bowling under pressure", ss["H2"]))
    story.append(bullet_list([
        "<b>Pressure economy</b>, <b>balls per bowler-wicket</b>, dot-ball %, boundary %.",
        "<b>Phase-adjusted runs saved / ball</b> = expected runs (by innings×over under HP) − actual "
        "runs conceded. This levels the field between death specialists and middle-over spinners.",
        "<b>Lift</b> = clamped baseline economy (capped at 9.5) − pressure economy.",
        "<b>Consistency</b>: share of pressure spells with positive contribution (runs saved vs own "
        "baseline + wicket bonus), plus 80th-percentile spell economy as a high-floor measure.",
    ], ss))
    story.append(p("4.3 Shrinkage &amp; composite formula", ss["H2"]))
    story.append(p(
        "Rates are empirical-Bayes shrunk toward the eligible-population median with a prior strength "
        "of 50 balls: "
        "<font face='Courier'>shrunk = (obs·n + prior·50) / (n+50)</font>. "
        "Component z-scores are computed within the eligible set, then combined:",
        ss["Body"],
    ))
    story.append(p(
        "Batter composite = 0.30·z(lift) + 0.35·z(abs SR/RAE) + 0.15·z(BPD) + 0.20·z(consistency), "
        "then × credibility dampener (0.85 + 0.15·n/(n+25)).",
        ss["Formula"],
    ))
    story.append(p(
        "Bowler composite = 0.22·z(lift) + 0.40·z(abs econ / runs-saved) + 0.18·z(wicket rate) "
        "+ 0.20·z(consistency) + 0.05·z(dot%), with the same credibility dampener.",
        ss["Formula"],
    ))

    # Eligibility
    story.append(p("5. Eligibility &amp; Fair Comparisons", ss["H1"]))
    story.append(bullet_list([
        f"Batters: ≥{meta['min_pressure_balls_bat']} high-pressure balls faced, "
        f"≥{meta['min_pressure_innings_bat']} distinct pressure innings, and auction relevance "
        f"(≥{meta['min_ipl_hp_balls']} IPL HP balls OR ≥{meta['min_fullmember_t20i_hp_balls']} "
        "Full-Member T20I HP balls).",
        f"Bowlers: ≥{meta['min_pressure_balls_bowl']} high-pressure legal balls, "
        f"≥{meta['min_pressure_spells_bowl']} pressure spells, ≥{meta['min_hp_wickets_bowl']} "
        "bowler wickets under pressure, and the same auction-relevance rule.",
        "<b>IPL availability by nationality:</b> Pakistan and Bangladesh players are not available in "
        "the IPL, so any player who appears for Pakistan, Pakistan A, Bangladesh or Bangladesh A in the "
        "competition-team-player mapping is excluded from eligibility (flag "
        "<font face='Courier'>ipl_banned_nation</font> in the ranking CSVs). This removed "
        f"{meta.get('n_excluded_nation_bat', 0)} otherwise-eligible batters and "
        f"{meta.get('n_excluded_nation_bowl', 0)} otherwise-eligible bowlers. Z-scores and shrinkage "
        "priors are computed on the remaining pool; all other thresholds and weights are unchanged.",
        "<b>Not available as a player:</b> Tim Southee stays in the scored pool, but he is removed from the "
        "picks because he is KKR's bowling coach for IPL 2026 (KKR.in, 13 Nov 2025). Picks are re-ranked "
        "over the remaining players.",
        f"Resulting eligible pool: <b>{meta['n_eligible_batters']} batters</b> and "
        f"<b>{meta['n_eligible_bowlers']} bowlers</b>.",
        "All rankings below are taken strictly from this eligible pool, sorted by composite score.",
    ], ss))

    # Top 10 batters
    story.append(PageBreak())
    story.append(p("6. Top 10 Batters Under Pressure", ss["H1"]))
    bat_rows = []
    for _, r in topb.iterrows():
        bat_rows.append([
            int(r["rank"]),
            r["player_name"],
            team_label(r)[:42],
            int(r["hp_balls"]),
            f"{r['hp_sr']:.1f}",
            f"{r['base_sr']:.1f}",
            f"{r['sr_lift']:+.1f}",
            f"{r['hp_bpd']:.1f}",
            f"{100*r['consist_pos_share']:.0f}%",
            f"{r['composite']:.3f}",
        ])
    story.append(styled_table(
        ["Rk", "Player", "Team(s)", "HP balls", "HP SR", "Base SR", "Lift", "BPD", "Consist", "Score"],
        bat_rows,
        [10*mm, 32*mm, 42*mm, 16*mm, 14*mm, 14*mm, 12*mm, 12*mm, 14*mm, 14*mm],
        ss,
    ))
    story.append(p(
        "Table 1. Top 10 batters. HP SR / Base SR are raw; Lift uses shrunk rates with baseline floored at 120. "
        "Consist = % of pressure innings with positive contribution vs own baseline. Score = composite.",
        ss["Caption"],
    ))
    story.append(img(CHARTS / "03_top10_batters_sr.png", 165 * mm))
    story.append(p("Figure 4. Pressure strike rate vs own baseline for the top 10 batters.", ss["Caption"]))
    story.append(img(CHARTS / "05_batter_consistency.png", 155 * mm))
    story.append(p("Figure 5. Match-to-match reliability: share of pressure innings with a positive contribution.", ss["Caption"]))
    story.append(img(CHARTS / "07_batter_components.png", 165 * mm))
    story.append(p("Figure 6. Composite component z-scores — showing why each batter ranks where they do.", ss["Caption"]))

    # Top 10 bowlers
    story.append(PageBreak())
    story.append(p("7. Top 10 Bowlers Under Pressure", ss["H1"]))
    bowl_rows = []
    for _, r in topw.iterrows():
        bowl_rows.append([
            int(r["rank"]),
            r["player_name"],
            team_label(r)[:40],
            int(r["hp_balls"]),
            f"{r['hp_econ']:.2f}",
            f"{r['base_econ']:.2f}",
            f"{r['econ_lift']:+.2f}",
            int(r["hp_wkts"]),
            f"{r['hp_rs_per_ball']:.3f}",
            f"{100*r['consist_pos_share']:.0f}%",
            f"{r['composite']:.3f}",
        ])
    story.append(styled_table(
        ["Rk", "Player", "Team(s)", "HP balls", "HP Econ", "Base", "Lift", "Wkts", "RS/ball", "Consist", "Score"],
        bowl_rows,
        [9*mm, 30*mm, 38*mm, 14*mm, 14*mm, 12*mm, 11*mm, 10*mm, 14*mm, 13*mm, 13*mm],
        ss,
    ))
    story.append(p(
        "Table 2. Top 10 bowlers. RS/ball = phase-adjusted runs saved per high-pressure ball "
        "(expected by innings×over − actual). Lift uses baseline economy capped at 9.5.",
        ss["Caption"],
    ))
    story.append(img(CHARTS / "04_top10_bowlers_econ.png", 165 * mm))
    story.append(p("Figure 7. Pressure economy vs own baseline for the top 10 bowlers.", ss["Caption"]))
    story.append(img(CHARTS / "06_bowler_consistency.png", 155 * mm))
    story.append(p("Figure 8. Match-to-match reliability under pressure for the top 10 bowlers.", ss["Caption"]))

    # Evidence notes for ordering
    story.append(p("7.1 Why this ordering", ss["H2"]))
    story.append(p(
        "Bosch separates clearly: 6.64 pressure economy against a ~9.0 expected economy for the overs he "
        "bowled, 15 pressure wickets and a positive contribution in every pressure spell. Santner ranks "
        "second on volume and floor (523 HP balls, 40 wickets, 82% positive spells). McCarthy and Humphreys "
        "both save ~0.30 runs per pressure ball versus expectation. Mujeeb combines strong absolute "
        "economy (7.23) with a high floor (82% positive spells); Mohit Sharma (27 HP wickets, all in the IPL), "
        "Motie, Narine (426 HP IPL balls at 7.00), Eshan Malinga (83% positive spells) and Harpreet Brar "
        "(7.57 vs 8.51 baseline, 80% positive spells) complete the list. <b>Tim Southee</b> scored 5th on the "
        "composite (1.304) but is excluded from the picks because he is KKR's bowling coach and not available "
        "as a player. Everyone below him moves up one place, and Brar (score rank 11) becomes No. 10. The "
        "scoring pool is unchanged, so no other score moves (bowler_rankings.csv: score_rank, available_as_player).",
        ss["Body"],
    ))

    # RR squad fit
    story += rr_fit_section(ss, topb, topw)

    story.append(p("8.1 Auction availability (public reporting as of 14 Nov 2026)", ss["H2"]))
    story.append(p(
        "As of 14 Nov 2026 no franchise has published its IPL 2027 retention list: the BCCI moved the "
        "retention deadline to <b>17 Nov 2026</b> (Cricinfo; IANS, 2 Nov 2026), registration closes 23 Nov "
        "and the mini-auction is on 16 Dec 2026 in Goa. Ten players have moved in four confirmed trades "
        "(Pant, Kuldeep, Natarajan, Zeeshan Ansari, Livingstone, Jack Edwards, Khaleel Ahmed, Nathan Ellis, "
        "Hardik Pandya, Arshdeep Singh; Sportstar / Cricinfo, 11 Nov 2026). <b>None of our 20 picks is in a "
        "confirmed trade.</b> RR-LSG talks on a Shami / Sam Curran deal were still unconfirmed on 13 Nov "
        "(CricTracker). \"Likely retained\" below comes from a media projection (Sporting News tracker), not "
        "an official list, so treat it as unconfirmed. Ranking is by pressure reliability, and availability "
        "is flagged rather than used to drop players.",
        ss["Body"],
    ))
    story.append(p("Batters", ss["H2"]))
    story.append(avail_table(topb, ss))
    story.append(Spacer(1, 4*mm))
    story.append(p("Bowlers", ss["H2"]))
    story.append(avail_table(topw, ss))

    # Reliability & limitations
    story.append(PageBreak())
    story.append(p("9. Reliability Checks &amp; Limitations", ss["H1"]))
    story.append(bullet_list([
        "<b>Consistency is a scored pillar</b>, not a post-hoc note: every ranked player’s match-level "
        "positive-contribution rate is part of the composite (Figures 5 &amp; 8).",
        "<b>Shrinkage + eligibility floors</b> suppress tiny-sample flukes; clamped baselines stop "
        "chronically poor players from ranking highly merely by being “less bad” under pressure.",
        "<b>Phase adjustment</b> prevents middle-over specialists from being over-credited relative to "
        "death bowlers facing harder expected scoring rates.",
        "<b>Limitations.</b> (i) Pressure is a proxy, not true win probability — we do not model batting "
        "depth or bowling matchups beyond over/innings. (ii) DLS matches use revised targets/overs where "
        "present; a handful of Super Overs are excluded from margin verification. (iii) T20I quality varies "
        "by opponent; the Full-Member filter and IPL up-weight mitigate but do not erase this. "
        "(iv) Fielding dismissals and captaincy effects are outside scope. (v) Players who are elite in "
        "<i>all</i> phases (e.g. some death specialists with flat baselines) can rank below “risers” even "
        "with strong absolute numbers — by design, because the brief asks who delivers when it matters "
        "relative to usual level, with absolute level still heavily weighted.",
    ], ss))

    story.append(p("10. Reproducibility", ss["H1"]))
    story.append(p(
        "All results are regenerated by <font face='Courier'>/workspace/rr_auction/analysis.py</font> "
        "from the supplied CSVs. Outputs: <font face='Courier'>batter_rankings.csv</font>, "
        "<font face='Courier'>bowler_rankings.csv</font>, <font face='Courier'>top10_*.csv</font>, "
        "charts in <font face='Courier'>charts/</font>, and this report. Randomness: none — the pipeline "
        "is fully deterministic.",
        ss["Body"],
    ))

    story.append(Spacer(1, 8 * mm))
    story.append(p(
        "<b>Final submission lists (Unstop dropdowns):</b> use Table 1 ranks 1–10 for batters and "
        "Table 2 ranks 1–10 for bowlers exactly as printed — no ties, no repeats.",
        ss["Body"],
    ))

    doc = SimpleDocTemplate(
        str(PDF),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=18 * mm,
        bottomMargin=14 * mm,
        title="RR SupeRR Selector Season 2 — Round 1 Methodology Report",
        author="SupeRR Selector Submission",
    )
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"Wrote {PDF} ({PDF.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
