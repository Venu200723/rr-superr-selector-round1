"""IPL 2027 mini-auction update for RR: merges the 17 Nov 2026 retention lists with our
pressure-reliability rankings. Writes rr_retained_squad.csv, rr_auction_targets.csv, rr_proposed_xi.csv.
Price bands are the analyst's rough estimates, not reported figures."""
import json
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
OUT = BASE / "output"
R = json.load(open(BASE / "retention" / "retention_2027.json"))
bat = pd.read_csv(OUT / "batter_rankings.csv")
bowl = pd.read_csv(OUT / "bowler_rankings.csv")
phase = pd.read_csv(OUT / "rr_fit_phase_stats.csv")

# data-pack name -> name used in news retention lists
ALIASES = {"Namboori Tilak Varma": "Tilak Varma", "Lokesh Rahul": "KL Rahul", "Rasikh Salam": "Rasikh Dar",
           "Vyshak Kumar": "Vyshak Vijaykumar", "Allah Ghazanfar": "AM Ghazanfar", "Zakary Foulkes": "Zak Foulkes",
           "William Jacks": "Will Jacks", "Nitish Reddy": "Nitish Kumar Reddy", "Patrick Cummins": "Pat Cummins"}
# retired / not playing IPL 2027 (never recommend)
UNAVAILABLE = {"Mohit Sharma": "retired 3 Dec 2025", "Tim Southee": "KKR coach", "Ambati Rayudu": "retired",
               "Dinesh Karthik": "retired", "Ajinkya Rahane": "released; reported as retired (Sportstar 17 Nov 2026)",
               "Mitchell Starc": "released; opted out", "Travis Head": "released; opted out"}
OS_RR = {"Jofra Archer", "Nandre Burger", "Dasun Shanaka", "Donovan Ferreira", "Lhuan-dre Pretorius"}
RR_PRICE = {"Yashasvi Jaiswal": 18, "Dhruv Jurel": 14, "Riyan Parag": 14, "Ravindra Jadeja": 14, "Jofra Archer": 12.5,
            "Mohammed Shami": 8, "Ravi Bishnoi": 7.2, "Sandeep Sharma": 4, "Nandre Burger": 3.5, "Dasun Shanaka": 2,
            "Vaibhav Sooryavanshi": 1.1, "Donovan Ferreira": 1, "Sushant Mishra": 0.9, "Shubham Dubey": 0.8,
            "Manimaran Siddharth": 0.75, "Aman Rao Perala": 0.3, "Lhuan-dre Pretorius": 0.3, "Yash Raj Punja": 0.3,
            "Brijesh Sharma": 0.3}


def pstat(df, name):
    r = df[df.player_name == name]
    return r.iloc[0] if len(r) else None


def death(name, role):
    r = phase[(phase.player_name == name) & (phase.role == role) & (phase.phase == "Overs 16-20")]
    return r.iloc[0] if len(r) else None


def bat_line(n):
    r = pstat(bat, n)
    if r is None or pd.isna(r.hp_balls):
        return "no high-pressure batting sample in data", None
    rk = f"#{int(r['score_rank'])} of 122" if r.eligible and not pd.isna(r['score_rank']) else "below eligibility"
    return f"bat {rk}: HP SR {r.hp_sr:.1f} vs {r.base_sr:.1f} normal on {int(r.hp_balls)} HP balls, {r.consist_pos_share*100:.0f}% positive inns", r


def bowl_line(n):
    r = pstat(bowl, n)
    if r is None or pd.isna(r.hp_balls):
        return "no high-pressure bowling sample in data", None
    rk = f"#{int(r['score_rank'])} of 112" if r.eligible and not pd.isna(r['score_rank']) else "below eligibility"
    return (f"bowl {rk}: HP econ {r.hp_econ:.2f} vs {r.base_econ:.2f}, {int(r.hp_wkts)} HP wkts on {int(r.hp_balls)} HP balls, "
            f"{r.consist_pos_share*100:.0f}% positive spells"), r


# ---------------- RR retained squad ----------------
roles = {"Riyan Parag": "Batting all-rounder (c)", "Yashasvi Jaiswal": "Opener", "Vaibhav Sooryavanshi": "Opener",
         "Ravindra Jadeja": "Spin all-rounder", "Dhruv Jurel": "Wicket-keeper batter", "Jofra Archer": "Pace",
         "Aman Rao Perala": "Batter", "Brijesh Sharma": "Pace", "Nandre Burger": "Left-arm pace",
         "Dasun Shanaka": "Seam all-rounder", "Donovan Ferreira": "Finisher / wk", "Lhuan-dre Pretorius": "Batter / wk",
         "Ravi Bishnoi": "Leg-spin", "Sandeep Sharma": "Pace", "Shubham Dubey": "Finisher", "Sushant Mishra": "Left-arm pace",
         "Yash Raj Punja": "Spin", "Mohammed Shami": "Pace (traded in)", "Manimaran Siddharth": "Left-arm spin (traded in)"}
rows = []
for n in R["retained"]["RR"]:
    bl, _ = bat_line(n); wl, _ = bowl_line(n)
    rows.append({"player_name": n, "role": roles.get(n, ""), "overseas": n in OS_RR,
                 "fee_cr": RR_PRICE.get(n), "how_acquired": "Trade (17 Nov 2026)" if n in ("Mohammed Shami", "Manimaran Siddharth") else "Retained",
                 "pressure_batting": bl, "pressure_bowling": wl})
sq = pd.DataFrame(rows)
sq.to_csv(OUT / "rr_retained_squad.csv", index=False)

# ---------------- target shortlist ----------------
retained_all = {n for l in R["retained"].values() for n in l}
released_all = {n for l in R["released"].values() for n in l}
def status(n):
    nm = ALIASES.get(n, n)
    if n in UNAVAILABLE: return "UNAVAILABLE"
    if nm in retained_all: return "RETAINED"
    for t, l in R["released"].items():
        if nm in l: return f"RELEASED by {t} (17 Nov 2026)"
    return "UNCONTRACTED - must register by 23 Nov"

T = [  # tier, player, role, overseas, need, use, price band (rough estimate), extra flag
 ("1 Must-buy", "Matheesha Pathirana", "Death pace (sling)", True, "Overseas death bowler (Milne, Maphaka released; RR death econ problem)", "bowl", "7-12", "Hamstring injury in 2026; had cost Rs 18 cr (Cricbuzz). Fitness check before bidding."),
 ("1 Must-buy", "Glenn Maxwell", "Finisher + off-spin", True, "Overseas finisher to replace Hetmyer; 6th bowling option", "bat", "2-5", "Skipped IPL 2026; 2027 registration UNCONFIRMED - fall back to Rachin Ravindra/Sikandar Raza."),
 ("1 Must-buy", "Avesh Khan", "Indian seam / death", False, "Indian death-overs volume (Deshpande, Kuldeep Sen released; Mohit retired)", "bowl", "2-5", "Reliable volume rather than elite: HP economy roughly equal to his normal."),
 ("2 Value", "Reece Topley", "Left-arm pace", True, "Overseas new-ball/death left-armer; cover for Archer", "bowl", "1-2.5", "Uncontracted in IPL 2026; injury history. Must register."),
 ("2 Value", "Rachin Ravindra", "Top/middle-order bat + left-arm spin", True, "Alternative overseas bat if Maxwell absent", "bat", "2-5", "Released by KKR."),
 ("2 Value", "Sikandar Raza", "Two-way all-rounder", True, "Overseas all-rounder who bowls tight middle overs", "both", "1-2.5", "Age 40; short-term buy."),
 ("2 Value", "Akash Madhwal", "Indian death pace", False, "Cheap Indian death option", "bowl", "0.3-1.5", "Below our eligibility (6 HP spells) - small sample."),
 ("2 Value", "Nitish Rana", "Indian middle-order bat (LH)", False, "Indian middle-order depth / impact bat", "bat", "1-3", "Released by DC."),
 ("3 Backup", "Lockie Ferguson", "Express pace", True, "Fallback if Pathirana price too high", "bowl", "2-5", "Released by PBKS after 3 games in 2026 (Moneycontrol 17 Nov 2026)."),
 ("3 Backup", "Barry McCarthy", "Seam (our bowler #3)", True, "Cheap overseas seam depth", "bowl", "0.3-1", "Never played IPL; must register."),
 ("3 Backup", "Mujeeb Ur Rahman", "Off-spin (our bowler #5)", True, "Powerplay spin if Bishnoi/Jadeja injured", "bowl", "0.75-2", "Uncontracted; must register. RR already has Bishnoi, Jadeja, Siddharth."),
 ("3 Backup", "Reeza Hendricks", "Opener (our batter #1)", True, "Top-order cover only; RR openers settled", "bat", "0.75-2", "Never played IPL; must register."),
 ("3 Backup", "Adil Rashid", "Leg-spin", True, "Experienced wrist-spin cover", "bowl", "1-2", "Only 4 IPL HP balls in data."),
]
rows = []
for tier, n, role, os_, need, use, band, flag in T:
    bl, _ = bat_line(n); wl, _ = bowl_line(n)
    ev = {"bat": bl, "bowl": wl, "both": bl + "; " + wl}[use]
    d = death(n, "bowler" if use != "bat" else "batter")
    if d is not None:
        ev += (f"; death overs: {int(d.hp_balls)} HP balls at econ {d.hp_econ:.2f}, {int(d.hp_wkts)} wkts" if use != "bat"
               else f"; death overs: SR {d.hp_sr:.1f} on {int(d.hp_balls)} HP balls")
    rows.append({"tier": tier, "player_name": n, "role": role, "overseas": os_, "status_17nov": status(n),
                 "rr_need": need, "pressure_evidence": ev, "price_band_cr_estimate": band, "flag": flag})
tg = pd.DataFrame(rows)
assert not tg.status_17nov.isin(["RETAINED", "UNAVAILABLE"]).any(), tg[["player_name", "status_17nov"]]
tg.to_csv(OUT / "rr_auction_targets.csv", index=False)

# ---------------- proposed XI ----------------
XI = [
 (1, "Yashasvi Jaiswal", "Retained", False, "Opener; left-hand powerplay anchor (Rs 18 cr core)"),
 (2, "Vaibhav Sooryavanshi", "Retained", False, "Opener; highest-tempo option (small HP sample: 40 balls)"),
 (3, "Dhruv Jurel", "Retained", False, "Wicket-keeper; 162 death-over HP balls at SR 170.4"),
 (4, "Riyan Parag", "Retained", False, "Captain; anchors overs 7-15, part-time spin"),
 (5, "Glenn Maxwell", "Proposed buy", True, "Overseas finisher replacing Hetmyer; HP SR 174.8 (alt: Rachin Ravindra)"),
 (6, "Donovan Ferreira", "Retained", True, "Second finisher; death-overs SR 214.9"),
 (7, "Ravindra Jadeja", "Retained", False, "Spin all-rounder; 4 overs through the middle"),
 (8, "Jofra Archer", "Retained", True, "New ball + 1-2 death overs"),
 (9, "Ravi Bishnoi", "Retained", False, "Middle-overs wicket-taker: 52 HP wkts on 919 HP balls"),
 (10, "Mohammed Shami", "Retained (traded in)", False, "New-ball seam, replaces Deshpande"),
 (11, "Matheesha Pathirana", "Proposed buy", True, "Death specialist: 24 death-over HP wkts (alt: Ferguson / Topley)"),
]
xi = pd.DataFrame(XI, columns=["bat_order", "player_name", "status", "overseas", "rationale"])
assert xi.overseas.sum() <= 4
xi.to_csv(OUT / "rr_proposed_xi.csv", index=False)
print(sq[["player_name", "fee_cr"]].to_string(index=False), "\nretained fees total", sq.fee_cr.sum())
print(tg[["tier", "player_name", "status_17nov", "price_band_cr_estimate"]].to_string(index=False))
for e in tg.pressure_evidence: print("-", e)
