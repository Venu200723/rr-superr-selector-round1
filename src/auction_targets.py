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
           "William Jacks": "Will Jacks", "Nitish Reddy": "Nitish Kumar Reddy", "Patrick Cummins": "Pat Cummins",
           "M Shahrukh Khan": "Shahrukh Khan"}
# retired / not playing IPL 2027 (never recommend)
UNAVAILABLE = {"Mohit Sharma": "retired 3 Dec 2025", "Tim Southee": "KKR coach", "Ambati Rayudu": "retired",
               "Dinesh Karthik": "retired", "Ajinkya Rahane": "released; reported as retired (Sportstar 17 Nov 2026)",
               "Mitchell Starc": "released; opted out", "Travis Head": "released; opted out",
               "Glenn Maxwell": "not available for IPL 2027 (see rr_target_verification.csv)",
               "Jacob Bethell": "released; will not take part in IPL 2027 (knee)"}
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

# Re-verified 17 Nov 2026 (after Venu's correction on Maxwell). Released players are preferred over
# uncontracted players whose 2027 registration is unknown.
T = [  # tier, player, role, overseas, need, use, price band (rough estimate), extra flag
 ("1 Must-buy", "Rachin Ravindra", "Top/middle-order bat + left-arm spin", True, "Overseas middle-order bat replacing Hetmyer; 6th bowling option", "bat", "2-5", "Released by KKR (bought for Rs 2 cr in 2026). Fit: back from shoulder injury for NZ Tests from 19 Nov 2026 (ICC)."),
 ("1 Must-buy", "Lockie Ferguson", "Express pace", True, "Overseas death / enforcer pace (Milne, Maphaka released)", "bowl", "2-5", "Released by PBKS. Fit: confirmed BBL 2026-27 availability with Sydney Thunder. Age 35; went at 12.8 rpo in 3 IPL 2026 games."),
 ("1 Must-buy", "Avesh Khan", "Indian seam / death", False, "Indian death-overs volume (Deshpande, Kuldeep Sen released; Mohit retired)", "bowl", "3-7", "Released by LSG (Rs 9.75 cr). Played 7 IPL 2026 games after knee surgery. Reliable volume, not elite."),
 ("2 Value", "Gerald Coetzee", "Pace (death)", True, "Third overseas slot: death-overs pace", "bowl", "1-3", "Released by SRH (2026 injury replacement). Reported fit (SA20, Sep 2026)."),
 ("2 Value", "Nitish Rana", "Indian middle-order bat (LH)", False, "Indian middle-order depth / impact bat", "bat", "1-3", "Released by DC."),
 ("2 Value", "Akash Madhwal", "Indian death pace", False, "Cheap Indian seam option", "bowl", "0.3-1.5", "Released by CSK. Below our eligibility (6 HP spells), so the sample is small."),
 ("2 Value", "M Shahrukh Khan", "Indian finisher", False, "Indian lower-order hitter (Hetmyer role)", "bat", "0.75-2.5", "Released by GT. Only 20% positive pressure innings: high-variance."),
 ("3 Backup", "Matheesha Pathirana", "Death pace (sling)", True, "Overseas death specialist IF medically cleared", "bowl", "4-9", "Released by KKR. Hamstring surgery June 2026; not in any SL squad Oct-Nov 2026; no return timeline. Bid only with medical clearance."),
 ("3 Backup", "Zakary Foulkes", "Seam all-rounder", True, "Overseas seam all-rounder (Curran gone)", "bowl", "0.75-2", "Released by CSK. HP death economy 11.10 on 40 balls: middle overs only."),
 ("3 Backup", "Kamindu Mendis", "Bat + two-way spin", True, "Overseas middle-order alternative to Rachin", "bat", "0.75-2", "Released by SRH."),
 ("3 Backup", "Umran Malik", "Indian express pace", False, "Indian pace depth", "bowl", "0.3-1.5", "Released by KKR. Economy 10.06 under pressure: expensive."),
 ("3 Backup", "Mujeeb Ur Rahman", "Off-spin (our bowler #5)", True, "Spin cover only", "bowl", "0.75-2", "Uncontracted. Registered for 2026 and went unsold (Rs 2 cr base). 2027 registration unconfirmed until 3 Dec."),
 ("3 Backup", "Reeza Hendricks", "Opener (our batter #1)", True, "Top-order cover only", "bat", "0.75-2", "Uncontracted. On the official 2026 auction list (Rs 1 cr base). 2027 registration unconfirmed until 3 Dec."),
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
 (5, "Rachin Ravindra", "Proposed buy", True, "Replaces Hetmyer; HP SR 164.1 vs 135.5 (our batter score rank 18), left-arm spin as 6th option"),
 (6, "Donovan Ferreira", "Retained", True, "Finisher; death-overs SR 214.9"),
 (7, "Ravindra Jadeja", "Retained", False, "Spin all-rounder; 4 overs through the middle"),
 (8, "Jofra Archer", "Retained", True, "New ball + 2 death overs (HP death econ 9.34)"),
 (9, "Ravi Bishnoi", "Retained", False, "Middle-overs wicket-taker: 52 HP wkts on 919 HP balls"),
 (10, "Mohammed Shami", "Retained (traded in)", False, "New-ball seam, replaces Deshpande"),
 (11, "Lockie Ferguson", "Proposed buy", True, "Overseas enforcer: 22 HP wkts, 77% positive spells (alt: Coetzee)"),
]
VERIFY = [  # player, previous tier, overseas, contract status 17 Nov 2026, retired/coach, PAK/BAN, fitness / intent, verdict, sources
 ("Glenn Maxwell", "1 Must-buy (17 Nov v1)", True, "Uncontracted (opted out of the IPL 2026 auction; released by PBKS Nov 2025)", "Retired from international, first-class and List A cricket on 2 Nov 2026; still plays T20 leagues", "No",
  "Signed a multi-year Hyderabad Kingsmen (PSL) deal extending beyond PSL 11; the PSL runs in the IPL window. Knee rehab for BBL. No IPL 2027 registration reported", "FAIL - removed",
  "Cricinfo 2 Nov 2026; cricket.com.au 2 Nov 2026; Business Recorder 19 Feb 2026; Sixty.pk 25 Feb 2026; Hindustan Times 27 Apr 2026; thecricpanda (IPL 2027 'not confirmed')"),
 ("Sikandar Raza", "2 Value (v1)", True, "Uncontracted; not on the official IPL 2026 auction list", "No", "No (Zimbabwe)",
  "Played PSL 11 for Lahore Qalandars in the IPL window; reported two-year PSL cycle. Age 40", "FAIL - removed (no IPL registration evidence, PSL clash)", "thecricscope; PCB PSL retention release; iplt20.com 2026 auction list"),
 ("Reece Topley", "2 Value (v1)", True, "Uncontracted; not on the official IPL 2026 auction list (15 Dec 2025)", "No", "No",
  "Returned to county cricket in Apr 2026; long injury history. No IPL registration in 2026 and none reported for 2027", "FAIL - removed (no registration evidence)", "iplt20.com 2026 auction list; Wisden Apr 2026"),
 ("Adil Rashid", "3 Backup (v1)", True, "Uncontracted; not on the official IPL 2026 auction list", "No", "No",
  "No IPL since 2023 (4 IPL HP balls in data); no 2027 registration reported", "FAIL - removed (no registration evidence)", "iplt20.com 2026 auction list; Guardian 16 Nov 2026"),
 ("Barry McCarthy", "3 Backup (v1)", True, "Never in the IPL; not on the official 2026 auction list", "No", "No (Ireland)", "No IPL registration reported", "FAIL - removed (no registration evidence)", "iplt20.com 2026 auction list"),
 ("Matheesha Pathirana", "1 Must-buy (v1)", True, "RELEASED by KKR, 17 Nov 2026", "No", "No (Sri Lanka)",
  "Hamstring surgery June 2026, rehab in France with no return timeline; not in SL squads Oct-Nov 2026; 1 IPL 2026 game (8 balls)", "CONDITIONAL - moved to backup (medical clearance needed)", "Cricbuzz 17 Nov 2026; CNBC-TV18 17 Nov 2026; CricketAddictor Jun 2026"),
 ("Avesh Khan", "1 Must-buy", False, "RELEASED by LSG, 17 Nov 2026", "No", "No", "Knee surgery after IPL 2025, then 7 IPL 2026 games", "PASS", "Cricinfo 17 Nov 2026; Tribune 17 Nov 2026; Rediff 25 Jun 2026"),
 ("Rachin Ravindra", "2 Value -> 1 Must-buy", True, "RELEASED by KKR, 17 Nov 2026", "No", "No (New Zealand)", "Recovered from a dislocated shoulder; named for NZ v India Tests from 19 Nov 2026", "PASS", "Cricinfo 17 Nov 2026; Sportstar 17 Nov 2026; ICC Nov 2026"),
 ("Lockie Ferguson", "3 Backup -> 1 Must-buy", True, "RELEASED by PBKS, 17 Nov 2026", "No", "No (New Zealand)", "Confirmed BBL 2026-27 availability (Sydney Thunder); age 35; poor IPL 2026 (3 games)", "PASS (form flag)", "Cricinfo 17 Nov 2026; cricket.com.au; Moneycontrol 17 Nov 2026"),
 ("Akash Madhwal", "2 Value", False, "RELEASED by CSK, 17 Nov 2026", "No", "No", "Unsold in the 2026 auction, later with CSK", "PASS (small sample)", "Cricinfo 17 Nov 2026; Wisden 16 Dec 2025"),
 ("Nitish Rana", "2 Value", False, "RELEASED by DC, 17 Nov 2026", "No", "No", "No reported issue", "PASS", "Cricinfo 17 Nov 2026"),
 ("Mujeeb Ur Rahman", "3 Backup", True, "Uncontracted; registered for 2026 and went unsold (Rs 2 cr base)", "No", "No (Afghanistan)", "2027 registration unconfirmed until 3 Dec", "PASS (registration risk)", "iplt20.com 2026 auction list; Wisden 16 Dec 2025"),
 ("Reeza Hendricks", "3 Backup", True, "Uncontracted; on the official 2026 auction list (Rs 1 cr base)", "No", "No (South Africa)", "2027 registration unconfirmed until 3 Dec", "PASS (registration risk)", "iplt20.com 2026 auction list"),
 ("Gerald Coetzee", "new - 2 Value", True, "RELEASED by SRH, 17 Nov 2026", "No", "No (South Africa)", "2026 injury replacement at SRH; reported fit Sep 2026", "PASS", "Cricinfo 17 Nov 2026; SA20 Sep 2026"),
 ("Zakary Foulkes", "new - 3 Backup", True, "RELEASED by CSK, 17 Nov 2026", "No", "No (New Zealand)", "No reported issue", "PASS", "Cricinfo 17 Nov 2026; Sportstar 17 Nov 2026"),
 ("M Shahrukh Khan", "new - 2 Value", False, "RELEASED by GT, 17 Nov 2026", "No", "No", "No reported issue", "PASS", "Cricinfo 17 Nov 2026"),
 ("Kamindu Mendis", "new - 3 Backup", True, "RELEASED by SRH, 17 Nov 2026", "No", "No (Sri Lanka)", "No reported issue", "PASS", "Cricinfo 17 Nov 2026"),
 ("Umran Malik", "new - 3 Backup", False, "RELEASED by KKR, 17 Nov 2026", "No", "No", "No reported issue", "PASS (expensive under pressure)", "Cricinfo 17 Nov 2026"),
]
pd.DataFrame(VERIFY, columns=["player_name", "previous_tier", "overseas", "contract_status", "retired_or_coach", "pak_ban",
                              "fitness_intent", "verdict", "sources"]).to_csv(OUT / "rr_target_verification.csv", index=False)
xi = pd.DataFrame(XI, columns=["bat_order", "player_name", "status", "overseas", "rationale"])
assert xi.overseas.sum() <= 4
xi.to_csv(OUT / "rr_proposed_xi.csv", index=False)
print(sq[["player_name", "fee_cr"]].to_string(index=False), "\nretained fees total", sq.fee_cr.sum())
print(tg[["tier", "player_name", "status_17nov", "price_band_cr_estimate"]].to_string(index=False))
for e in tg.pressure_evidence: print("-", e)
