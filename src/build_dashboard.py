#!/usr/bin/env python3
"""Build the public interactive dashboard (output/dashboard/index.html) from the final CSVs."""
import json
from pathlib import Path
import pandas as pd

ROOT = Path("/workspace/rr_auction"); OUT = ROOT / "output"; DASH = OUT / "dashboard"
DASH.mkdir(parents=True, exist_ok=True)
meta = json.load(open(OUT / "meta.json"))
tb = pd.read_csv(OUT / "top10_batters.csv").sort_values("rank")
tw = pd.read_csv(OUT / "top10_bowlers.csv").sort_values("rank")
ov = pd.read_csv(OUT / "validation_hp_vs_normal.csv", index_col=0)
ph = pd.read_csv(OUT / "validation_by_phase.csv")
dec = pd.read_csv(OUT / "validation_deciles.csv")
oc = pd.read_csv(OUT / "validation_outcome.csv")
ps = pd.read_csv(OUT / "rr_fit_phase_stats.csv")

def team(r):
    t = r.get("latest_ipl_team")
    if isinstance(t, str) and t:
        return f"{t} (IPL {int(r['latest_ipl_season'])})"
    n = r.get("national_teams")
    return n if isinstance(n, str) else ""

def s(v): return "" if pd.isna(v) else str(v)

bat = [{"rank": int(r["rank"]), "player": r["player_name"], "team": team(r), "hp_balls": int(r["hp_balls"]),
        "hp": round(r["hp_sr"], 1), "base": round(r["base_sr"], 1), "lift": round(r["sr_lift"], 1),
        "bpd": round(r["hp_bpd"], 1), "consist": round(100 * r["consist_pos_share"]), "score": round(r["composite"], 3),
        "status": s(r["availability_status"]), "note": s(r["availability_note"]), "src": s(r["source"]),
        "hp_shr": round(r["hp_sr_shrunk"], 1), "base_shr": round(r["base_sr_shrunk"], 1)} for _, r in tb.iterrows()]
bowl = [{"rank": int(r["rank"]), "player": r["player_name"], "team": team(r), "hp_balls": int(r["hp_balls"]),
         "hp": round(r["hp_econ"], 2), "base": round(r["base_econ"], 2), "lift": round(r["econ_lift"], 2),
         "wkts": int(r["hp_wkts"]), "consist": round(100 * r["consist_pos_share"]), "score": round(r["composite"], 3),
         "status": s(r["availability_status"]), "note": s(r["availability_note"]), "src": s(r["source"]),
         "hp_shr": round(r["hp_econ_shrunk"], 2), "base_shr": round(r["base_econ_shrunk"], 2)} for _, r in tw.iterrows()]

hp, nm = ov["High pressure"], ov["Normal"]
death = ph[ph.band == "Overs 16-20"].set_index("hp")
val = {
    "wkt_hp": round(hp["wicket_pct"], 2), "wkt_n": round(nm["wicket_pct"], 2),
    "wkt_up": round(100 * (hp["wicket_pct"] / nm["wicket_pct"] - 1)),
    "bpw_hp": round(hp["balls_per_wicket"], 1), "bpw_n": round(nm["balls_per_wicket"], 1),
    "death_rr_n": round(death.loc["Normal", "run_rate"], 2), "death_rr_hp": round(death.loc["High pressure", "run_rate"], 2),
    "death_sr_n": round(death.loc["Normal", "batting_sr"], 1), "death_sr_hp": round(death.loc["High pressure", "batting_sr"], 1),
    "chase_lo": round(oc.iloc[0]["chase_win_pct"], 1), "chase_hi": round(oc.iloc[-1]["chase_win_pct"], 1),
    "dec_wkt": [round(x, 2) for x in dec["wicket_pct"]], "dec_dot": [round(x, 1) for x in dec["dot_pct"]],
    "oc_labels": [str(x) for x in oc["hp_quartile"]], "oc_vals": [round(x, 1) for x in oc["chase_win_pct"]],
    "spearman": round(meta["charts"]["val_spearman_wicket"], 2),
    "thr": round(meta["hp_threshold"], 3),
}
def g(n, p): return ps[(ps.player_name == n) & (ps.phase == p)].iloc[0]
rank_w = {r["player"]: r["rank"] for r in bowl}; rank_b = {r["player"]: r["rank"] for r in bat}
m, b_, sa = g("Mohit Sharma", "Overs 16-20"), g("Corbin Bosch", "Overs 16-20"), g("Mitchell Santner", "Overs 7-11")
du, ri = g("Shubham Dubey", "Overs 16-20"), g("Rinku Singh", "Overs 16-20")
fit = [
    {"need": "An Indian death-overs bowler", "pick": f"Mohit Sharma (bowler #{rank_w['Mohit Sharma']})",
     "stat": f"Death overs under pressure: {int(m.hp_balls)} balls, economy {m.hp_econ:.2f}, {int(m.hp_wkts)} wickets",
     "src": "Sports Yaari RR report card, 31 May 2026; Sandeep Sharma went at 11.39 (Hindustan Times, 12 Nov 2026)"},
    {"need": "An overseas all-rounder who can bowl at the death", "pick": f"Corbin Bosch (bowler #{rank_w['Corbin Bosch']})",
     "stat": f"Death overs under pressure: {int(b_.hp_balls)} balls, economy {b_.hp_econ:.2f}, {int(b_.hp_wkts)} wickets; positive in 100% of pressure spells",
     "src": "Sports Yaari RR report card, 31 May 2026"},
    {"need": "Middle-overs control (RR economy in overs 7-11 was 9.71, second-worst)", "pick": f"Mitchell Santner (bowler #{rank_w['Mitchell Santner']})",
     "stat": f"Overs 7-11 under pressure: {int(sa.hp_balls)} balls, economy {sa.hp_econ:.2f}, {int(sa.hp_wkts)} wickets",
     "src": "Hindustan Times, 12 Nov 2026; The Hindu, 25 May 2026 (spin a concern)"},
    {"need": "A reliable finisher (RR death-overs scoring rate 10.62, 7th)", "pick": f"Shubham Dubey (#{rank_b['Shubham Dubey']}, already at RR) / Rinku Singh (#{rank_b['Rinku Singh']})",
     "stat": f"Death overs under pressure: Dubey SR {du.hp_sr:.1f} on {int(du.hp_balls)} balls; Rinku SR {ri.hp_sr:.1f} on {int(ri.hp_balls)} balls, {int(ri.hp_wkts)} dismissals",
     "src": "Hindustan Times, 12 Nov 2026; Sports Yaari, 31 May 2026"},
]
elig = {k: meta[k] for k in ["min_pressure_balls_bat", "min_pressure_innings_bat", "min_pressure_balls_bowl",
        "min_pressure_spells_bowl", "min_hp_wickets_bowl", "min_ipl_hp_balls", "min_fullmember_t20i_hp_balls",
        "n_eligible_batters", "n_eligible_bowlers", "n_excluded_nation_bat", "n_excluded_nation_bowl"]}
data = {"bat": bat, "bowl": bowl, "val": val, "fit": fit, "elig": elig,
        "w": {"bat": meta["bat_weights"], "bowl": meta["bowl_weights"]}}
html = (ROOT / "dashboard_template.html").read_text().replace("/*__DATA__*/null", json.dumps(data))
(DASH / "index.html").write_text(html)
print("wrote", DASH / "index.html", len(html))
