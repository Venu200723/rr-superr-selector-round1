#!/usr/bin/env python3
"""
Rajasthan Royals SupeRR Selector Season 2 — Round 1
Identify the Most Reliable Players Under Pressure

Reproducible end-to-end analysis: pressure index → eligibility →
composite ratings → rankings → charts → supporting CSVs.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))

warnings.filterwarnings("ignore", category=FutureWarning)
sns.set_theme(style="whitegrid", context="talk")
plt.rcParams.update({
    "figure.dpi": 140,
    "savefig.dpi": 160,
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
})

ROOT = Path("/workspace/rr_auction")
DATA = ROOT / "Data Pack"
OUT = ROOT / "output"
CHARTS = ROOT / "charts"
OUT.mkdir(exist_ok=True)
CHARTS.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Constants / methodology knobs (documented in the report)
# ---------------------------------------------------------------------------
BOWLER_WICKET_TYPES = {
    "Caught", "Bowled", "LBW", "Stump", "Hit Wicket",
}
# Exclude: RunOut, Retire Out, Obstracting/Obstructing the field

# Eligibility
MIN_PRESSURE_BALLS_BAT = 80       # balls faced under high pressure
MIN_PRESSURE_INNINGS_BAT = 7     # distinct innings with ≥1 HP ball faced
MIN_PRESSURE_BALLS_BOWL = 100    # legal balls bowled under high pressure
MIN_PRESSURE_SPELLS_BOWL = 8     # distinct innings with ≥1 HP ball bowled
MIN_HP_WICKETS_BOWL = 6          # minimum bowler wickets under pressure
# Auction-relevance: need meaningful IPL sample OR Full-Member T20I sample
MIN_IPL_HP_BALLS = 40
MIN_FULLMEMBER_T20I_HP_BALLS = 100

# High-pressure threshold: top quartile of the continuous pressure index
HP_QUANTILE = 0.75

# Composite weights (sum to 1)
BAT_W_LIFT = 0.30          # pressure vs own baseline (reliability of level)
BAT_W_ABS = 0.35           # absolute pressure output vs peers
BAT_W_SURVIVAL = 0.15      # balls-per-dismissal under pressure
BAT_W_CONSIST = 0.20       # match-to-match consistency

BOWL_W_LIFT = 0.22
BOWL_W_ABS = 0.40
BOWL_W_WICKETS = 0.18
BOWL_W_CONSIST = 0.20

# Shrinkage prior strength (empirical Bayes): effective prior balls
PRIOR_BALLS_BAT = 50
PRIOR_BALLS_BOWL = 50

# Competition weights when pooling IPL + T20I (IPL up-weighted for auction context)
IPL_WEIGHT = 1.35
T20I_WEIGHT = 1.00
OTHER_T20_WEIGHT = 0.70

# Individual players scored but excluded from picks (not available as players)
NOT_AVAILABLE_AS_PLAYER = {
    "Tim Southee": "KKR bowling coach for IPL 2026 (KKR.in, 13 Nov 2025); not available as a player",
    "Mohit Sharma": "Retired from all forms of cricket on 3 Dec 2025 (ESPNcricinfo); not available as a player",
}

# Nations whose players are not available in the IPL -> excluded from eligibility
IPL_EXCLUDED_TEAMS = {"Pakistan", "Pakistan A", "Bangladesh", "Bangladesh A"}

# ICC Full Member nations (for T20I auction-relevance filter)
FULL_MEMBER_TEAMS = {
    "India", "Australia", "England", "South Africa", "New Zealand",
    "Pakistan", "West Indies", "Sri Lanka", "Bangladesh", "Afghanistan",
    "Ireland", "Zimbabwe",
}

RR_PURPLE = "#2541B2"
RR_PINK = "#E11D48"
RR_GOLD = "#F59E0B"
RR_TEAL = "#0D9488"


def load_data():
    bbb = pd.read_csv(DATA / "ball_by_ball.csv")
    matches = pd.read_csv(DATA / "matches.csv")
    comps = pd.read_csv(DATA / "competitions.csv")
    teams = pd.read_csv(DATA / "teams.csv")
    mapping = pd.read_csv(DATA / "competition_team_player_mapping.csv")
    pe = pd.read_csv(DATA / "playing_eleven.csv")
    return bbb, matches, comps, teams, mapping, pe


def verify_runs_semantics(bbb: pd.DataFrame, matches: pd.DataFrame) -> dict:
    """Reconstruct innings totals and compare to result margins."""
    bbb = bbb.copy()
    bbb["ball_total"] = (
        bbb["runs"].fillna(0)
        + bbb["extras1_runs"].fillna(0)
        + bbb["extras_2_runs"].fillna(0)
    )
    inn = bbb.groupby(["match_id", "innings"], as_index=False)["ball_total"].sum()
    p = inn.pivot(index="match_id", columns="innings", values="ball_total")
    p = p.rename(columns={1: "runs_inn1", 2: "runs_inn2"}).reset_index()
    m = matches.merge(p, on="match_id", how="left")

    def parse_margin(r):
        if pd.isna(r):
            return np.nan, None
        import re
        r = str(r)
        mm = re.search(r"by (\d+) Runs?", r, re.I)
        if mm:
            return int(mm.group(1)), "runs"
        mm = re.search(r"by (\d+) Wickets?", r, re.I)
        if mm:
            return int(mm.group(1)), "wickets"
        return np.nan, None

    parsed = m["result"].apply(parse_margin)
    m["margin"] = [x[0] for x in parsed]
    m["margin_type"] = [x[1] for x in parsed]
    m["score_diff"] = m["runs_inn1"] - m["runs_inn2"]

    runs_wins = m[(m["margin_type"] == "runs") & m["score_diff"].notna() & m["margin"].notna()]
    non_dls = runs_wins[runs_wins["revised_target"].isna()]
    ok = (non_dls["score_diff"] - non_dls["margin"]).abs() <= 1
    report = {
        "n_runs_margin_non_dls": int(len(non_dls)),
        "n_match_reconstructed": int(ok.sum()),
        "pct_match": float(100 * ok.mean()) if len(non_dls) else 0.0,
        "runs_is_bat_only": True,
        "total_formula": "runs + extras1_runs + extras_2_runs",
        "bowler_wicket_types": sorted(BOWLER_WICKET_TYPES),
    }
    print(f"[verify] non-DLS runs-margin reconstruction: {ok.sum()}/{len(non_dls)} ({report['pct_match']:.1f}%)")
    return report


def enrich_balls(bbb, matches, comps):
    """Add match context, legal-ball flags, bowler wickets, innings state, pressure."""
    bbb = bbb.copy()
    matches = matches.copy()
    comps = comps.copy()

    # Competition tags
    comps["is_ipl"] = comps["comp_name"].str.startswith("IPL")
    comps["comp_bucket"] = np.where(
        comps["is_ipl"], "IPL",
        np.where(comps["match_format"] == "T20I", "T20I", "OtherT20"),
    )
    comps["comp_weight"] = comps["comp_bucket"].map(
        {"IPL": IPL_WEIGHT, "T20I": T20I_WEIGHT, "OtherT20": OTHER_T20_WEIGHT}
    )

    mctx = matches.merge(
        comps[["comp_id", "comp_name", "match_format", "season", "comp_bucket", "comp_weight", "is_ipl"]],
        on="comp_id",
        how="left",
    )
    bbb = bbb.merge(
        mctx[
            [
                "match_id", "comp_id", "comp_name", "match_format", "season",
                "comp_bucket", "comp_weight", "is_ipl", "knock_out", "stage",
                "revised_target", "first_inn_revised_overs", "second_inn_revised_overs",
                "win_team_id", "result", "home_team_id", "away_team_id",
            ]
        ],
        on="match_id",
        how="left",
    )

    # Semantics
    bbb["bat_runs"] = bbb["runs"].fillna(0).astype(float)
    bbb["extras"] = bbb["extras1_runs"].fillna(0) + bbb["extras_2_runs"].fillna(0)
    bbb["ball_total"] = bbb["bat_runs"] + bbb["extras"]
    bbb["is_wide"] = bbb["extras_type"].fillna("").str.lower().eq("wide")
    bbb["is_noball"] = bbb["extras_type"].fillna("").isin(["Overstep", "other"])
    # Legal ball for batting SR / bowling economy: not a wide (noballs count as faced for batter)
    bbb["is_legal"] = ~bbb["is_wide"]
    # Ball faced by batter (wides don't count as faced; noballs do)
    bbb["ball_faced"] = (~bbb["is_wide"]).astype(int)
    # Ball bowled for economy (legal deliveries; wides/noballs inflate overs denominator via 6-ball overs — use legal only)
    bbb["ball_bowled"] = bbb["is_legal"].astype(int)

    bbb["is_bowler_wicket"] = (
        bbb["is_wicket"].fillna(False)
        & bbb["dismissal_type"].isin(BOWLER_WICKET_TYPES)
    )
    bbb["is_batter_dismissed"] = (
        bbb["is_wicket"].fillna(False)
        & bbb["dismissed_player_id"].notna()
        & (bbb["dismissed_player_id"] == bbb["striker_id"])
    )
    # Also count run-outs of the striker as dismissals for batter survival
    bbb["is_striker_out"] = (
        bbb["is_wicket"].fillna(False)
        & bbb["dismissed_player_id"].notna()
        & (bbb["dismissed_player_id"] == bbb["striker_id"])
    )

    # Sort for cumulative state
    bbb = bbb.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)

    # Cumulative within innings BEFORE this ball
    g = bbb.groupby(["match_id", "innings"], sort=False)
    bbb["cum_runs_before"] = g["ball_total"].cumsum() - bbb["ball_total"]
    bbb["cum_wkts_before"] = g["is_wicket"].cumsum() - bbb["is_wicket"].fillna(False).astype(int)
    bbb["cum_balls_before"] = g["ball_bowled"].cumsum() - bbb["ball_bowled"]

    # Target for 2nd innings
    inn1_totals = (
        bbb[bbb["innings"] == 1]
        .groupby("match_id", as_index=False)["ball_total"]
        .sum()
        .rename(columns={"ball_total": "inn1_total"})
    )
    bbb = bbb.merge(inn1_totals, on="match_id", how="left")

    # Effective overs available
    bbb["overs_available"] = 20.0
    bbb.loc[bbb["innings"] == 1, "overs_available"] = bbb.loc[bbb["innings"] == 1, "first_inn_revised_overs"].fillna(20.0)
    bbb.loc[bbb["innings"] == 2, "overs_available"] = bbb.loc[bbb["innings"] == 2, "second_inn_revised_overs"].fillna(20.0)
    # If revised_overs is stored oddly, clamp
    bbb["overs_available"] = bbb["overs_available"].clip(lower=1, upper=20)

    bbb["balls_available"] = (bbb["overs_available"] * 6).astype(int)
    bbb["balls_remaining"] = (bbb["balls_available"] - bbb["cum_balls_before"]).clip(lower=0)
    bbb["wickets_in_hand"] = (10 - bbb["cum_wkts_before"]).clip(lower=0, upper=10)

    # Target: revised_target if present else inn1_total + 1
    bbb["target"] = np.where(
        bbb["innings"] == 2,
        np.where(
            bbb["revised_target"].notna(),
            bbb["revised_target"],
            bbb["inn1_total"] + 1,
        ),
        np.nan,
    )
    bbb["runs_needed"] = np.where(
        bbb["innings"] == 2,
        (bbb["target"] - bbb["cum_runs_before"]).clip(lower=0),
        np.nan,
    )
    bbb["rrr"] = np.where(
        (bbb["innings"] == 2) & (bbb["balls_remaining"] > 0),
        bbb["runs_needed"] * 6.0 / bbb["balls_remaining"],
        np.nan,
    )
    bbb["crr"] = np.where(
        bbb["cum_balls_before"] > 0,
        bbb["cum_runs_before"] * 6.0 / bbb["cum_balls_before"],
        0.0,
    )

    # Recent wickets (collapse signal): wickets in previous 12 legal balls
    bbb["recent_wkts"] = (
        bbb.groupby(["match_id", "innings"])["is_wicket"]
        .transform(lambda s: s.fillna(False).astype(int).rolling(12, min_periods=1).sum().shift(1).fillna(0))
    )

    # Over number 1-20
    bbb["over_num"] = bbb["overid"].clip(1, 20)

    return bbb


def compute_pressure_index(bbb: pd.DataFrame) -> pd.DataFrame:
    """
    Continuous Pressure Index (0–1) per ball.

    Components (justified in report):
      1. Chase difficulty (2nd innings): sigmoid of (RRR - par), scaled by
         resource scarcity (few balls / few wickets).
      2. Death-over intensity (overs 16–20), stronger in chases.
      3. Collapse pressure: recent wicket cluster + few wickets in hand.
      4. Match-stage multiplier: knockouts / finals elevate pressure.
      5. Closeness: when chase is still live (runs needed ≤ remaining × 2.5
         and RRR between 6–14) — the "game on the line" zone.

    High-pressure = pressure_index >= Q75 across all balls.
    """
    bbb = bbb.copy()

    # --- 1. Chase component ---
    # Par T20 chase rate ~8.5; difficulty rises as RRR exceeds that
    par = 8.5
    rrr = bbb["rrr"].fillna(0)
    # Soft-clip extreme RRR so abandoned chases don't dominate
    rrr_clip = rrr.clip(0, 18)
    chase_raw = 1 / (1 + np.exp(-(rrr_clip - par) / 1.8))  # ~0.5 at par

    # Resource scarcity: fewer wickets / balls → more pressure
    wih = bbb["wickets_in_hand"].clip(1, 10)
    br = bbb["balls_remaining"].clip(1, 120)
    scarcity = (1 - (wih / 10.0)) * 0.55 + (1 - (br / 120.0)) * 0.45

    # Live-chase gate: if RRR > 16 and balls left plenty with many wkts, still hard;
    # if already lost (runs_needed huge vs balls), reduce "meaningful" pressure a bit
    # but keep it high — bowling under a lost chase is less "pressure" for batters
    live = (
        (bbb["innings"] == 2)
        & (bbb["runs_needed"] > 0)
        & (bbb["balls_remaining"] > 0)
        & (rrr_clip <= 16)
    ).astype(float)
    # Still assign some chase pressure when RRR>16 (desperation) but dampen
    desperate = ((bbb["innings"] == 2) & (rrr_clip > 16)).astype(float) * 0.55

    chase = np.where(
        bbb["innings"] == 2,
        (0.65 * chase_raw + 0.35 * scarcity) * np.maximum(live, desperate),
        0.0,
    )

    # --- 2. Death overs ---
    over = bbb["over_num"]
    death = np.where(over >= 16, 1.0, np.where(over >= 15, 0.55, np.where(over >= 14, 0.25, 0.0)))
    # Death matters more when defending/chasing a competitive total
    death = death * np.where(bbb["innings"] == 2, 0.9, 0.7)

    # --- 3. Collapse ---
    collapse = (
        (bbb["recent_wkts"].clip(0, 4) / 4.0) * 0.6
        + ((10 - bbb["wickets_in_hand"]).clip(0, 8) / 8.0) * 0.4
    )
    # Collapse more relevant mid-innings (overs 6–15) when a side is folding
    mid = ((over >= 6) & (over <= 15)).astype(float)
    collapse = collapse * (0.5 + 0.5 * mid)

    # --- 4. Knockout / stage ---
    stage = bbb["stage"].fillna("").str.lower()
    is_ko = (
        (bbb["knock_out"].fillna(0) == 1)
        | stage.str.contains("final|qualifier|eliminator|semi")
    )
    ko_boost = np.where(is_ko, 0.18, 0.0)

    # --- Combine ---
    # Weighted blend, then clip to [0,1]
    raw = (
        0.50 * chase
        + 0.25 * death
        + 0.15 * collapse
        + 0.10 * (chase * death)  # interaction: death overs while chasing hard
    )
    pressure = (raw + ko_boost).clip(0, 1)

    # First 2 overs of an innings: lower floor (new-ball is different pressure)
    pressure = np.where(over <= 2, pressure * 0.85, pressure)

    bbb["pressure_chase"] = chase
    bbb["pressure_death"] = death
    bbb["pressure_collapse"] = collapse
    bbb["pressure_ko"] = ko_boost
    bbb["pressure_index"] = pressure

    thr = float(np.nanquantile(bbb["pressure_index"], HP_QUANTILE))
    bbb["is_high_pressure"] = bbb["pressure_index"] >= thr
    bbb.attrs["hp_threshold"] = thr
    print(f"[pressure] HP threshold (Q{int(HP_QUANTILE*100)}): {thr:.4f}")
    print(f"[pressure] HP ball share: {bbb['is_high_pressure'].mean()*100:.1f}%")
    return bbb


def player_team_lookup(mapping: pd.DataFrame) -> pd.DataFrame:
    """Most recent / most common team name(s) per player."""
    # Prefer IPL team names when available
    m = mapping.copy()
    m["is_ipl"] = m["comp_name"].fillna("").str.startswith("IPL")
    # Count appearances
    cnt = (
        m.groupby(["player_id", "player_name", "team_name", "is_ipl"])
        .size()
        .reset_index(name="n")
    )
    # Prefer IPL teams
    cnt = cnt.sort_values(["player_id", "is_ipl", "n"], ascending=[True, False, False])
    top = cnt.groupby("player_id").first().reset_index()
    # Also collect all distinct IPL teams
    ipl_teams = (
        m[m["is_ipl"]]
        .groupby("player_id")["team_name"]
        .agg(lambda s: ", ".join(sorted(set(s))))
        .rename("ipl_teams")
    )
    all_teams = (
        m.groupby("player_id")["team_name"]
        .agg(lambda s: ", ".join(sorted(set(s))[:4]))
        .rename("teams_all")
    )
    out = top[["player_id", "player_name", "team_name"]].rename(columns={"team_name": "primary_team"})
    out = out.merge(ipl_teams, on="player_id", how="left").merge(all_teams, on="player_id", how="left")
    out["team_display"] = out["ipl_teams"].fillna(out["primary_team"])
    # Nationality: national T20I side(s) the player represents (incl. A sides)
    nat = (
        m[~m["is_ipl"]]
        .groupby("player_id")["team_name"]
        .agg(lambda s: ", ".join(sorted(set(s))))
        .rename("national_teams")
    )
    out = out.merge(nat, on="player_id", how="left")
    out["ipl_banned_nation"] = out["national_teams"].fillna("").apply(
        lambda t: any(x.strip() in IPL_EXCLUDED_TEAMS for x in t.split(","))
    )
    return out


def shrink(obs, n, prior_mean, prior_n):
    """Empirical-Bayes shrinkage of a rate toward prior_mean."""
    return (obs * n + prior_mean * prior_n) / (n + prior_n)


def zscore(s: pd.Series) -> pd.Series:
    mu, sd = s.mean(), s.std(ddof=0)
    if sd == 0 or np.isnan(sd):
        return pd.Series(0.0, index=s.index)
    return (s - mu) / sd


def add_phase_expected(bbb: pd.DataFrame) -> pd.DataFrame:
    """Attach league expected runs/ball under HP by (innings, over)."""
    bbb = bbb.copy()
    bbb["over_bin"] = bbb["over_num"].clip(1, 20)
    hp = bbb[bbb["is_high_pressure"]]
    exp = (
        hp.groupby(["innings", "over_bin"])["ball_total"]
        .mean()
        .rename("exp_runs_hp")
    )
    bbb = bbb.merge(exp, on=["innings", "over_bin"], how="left")
    # For non-HP, also compute a general expected by over/innings
    exp_all = (
        bbb.groupby(["innings", "over_bin"])["ball_total"]
        .mean()
        .rename("exp_runs_all")
    )
    bbb = bbb.merge(exp_all, on=["innings", "over_bin"], how="left")
    bbb["exp_runs"] = np.where(
        bbb["is_high_pressure"], bbb["exp_runs_hp"], bbb["exp_runs_all"]
    )
    return bbb



def analyze_batters(bbb: pd.DataFrame, teams_lu: pd.DataFrame) -> pd.DataFrame:
    df = bbb.copy()
    # Weight each ball by competition weight
    df["w"] = df["comp_weight"]

    def agg_block(sub, prefix):
        # Faced balls & runs (bat runs only for SR)
        faced = sub.loc[sub["ball_faced"] == 1]
        # Weighted
        balls = faced["w"].sum()
        runs = (faced["bat_runs"] * faced["w"]).sum()
        dismissals = (sub.loc[sub["is_striker_out"], "w"]).sum()
        fours = (faced["is_four"].fillna(False).astype(int) * faced["w"]).sum()
        sixes = (faced["is_six"].fillna(False).astype(int) * faced["w"]).sum()
        raw_balls = int((sub["ball_faced"] == 1).sum())
        raw_runs = float(faced["bat_runs"].sum())
        raw_outs = int(sub["is_striker_out"].sum())
        innings = sub.loc[sub["ball_faced"] == 1, ["match_id", "innings"]].drop_duplicates().shape[0]
        matches = sub.loc[sub["ball_faced"] == 1, "match_id"].nunique()
        sr = 100.0 * runs / balls if balls > 0 else np.nan
        bpd = balls / dismissals if dismissals > 0 else (balls if balls > 0 else np.nan)
        return {
            f"{prefix}_balls": raw_balls,
            f"{prefix}_balls_w": float(balls),
            f"{prefix}_runs": raw_runs,
            f"{prefix}_runs_w": float(runs),
            f"{prefix}_outs": raw_outs,
            f"{prefix}_sr": float(sr) if pd.notna(sr) else np.nan,
            f"{prefix}_bpd": float(bpd) if pd.notna(bpd) else np.nan,
            f"{prefix}_innings": int(innings),
            f"{prefix}_matches": int(matches),
            f"{prefix}_fours": float(faced["is_four"].fillna(False).sum()),
            f"{prefix}_sixes": float(faced["is_six"].fillna(False).sum()),
        }

    rows = []
    for pid, g in df.groupby("striker_id"):
        name = g["striker_name"].mode().iloc[0] if len(g["striker_name"].mode()) else g["striker_name"].iloc[0]
        hp = g[g["is_high_pressure"]]
        np_ = g[~g["is_high_pressure"]]
        if hp["ball_faced"].sum() == 0:
            continue
        rec = {"player_id": pid, "player_name": name}
        rec.update(agg_block(hp, "hp"))
        rec.update(agg_block(np_, "base"))
        rec.update(agg_block(g, "all"))

        # IPL-only HP balls (for transparency)
        hp_ipl = hp[hp["is_ipl"] == True]
        rec["hp_ipl_balls"] = int(hp_ipl["ball_faced"].sum())
        rec["hp_t20i_balls"] = int(hp.loc[hp["comp_bucket"] == "T20I", "ball_faced"].sum())

        # Phase-adjusted runs above expected under HP (absolute value)
        faced_hp = hp[hp["ball_faced"] == 1]
        if len(faced_hp):
            # exp_runs is total runs/ball; for batting use bat_runs vs situation expected * (bat share)
            # Use exp_runs as the situation par for scoring rate
            rae = float((faced_hp["bat_runs"] - faced_hp["exp_runs"]).sum())
            rec["hp_rae"] = rae
            rec["hp_rae_per_ball"] = rae / len(faced_hp)
        else:
            rec["hp_rae"] = 0.0
            rec["hp_rae_per_ball"] = 0.0

        # Per-innings pressure contribution for consistency
        base_sr = rec["base_sr"] if pd.notna(rec["base_sr"]) and rec["base_balls"] >= 30 else rec["all_sr"]
        inn_stats = []
        for (mid, inn), ig in hp.groupby(["match_id", "innings"]):
            faced = ig[ig["ball_faced"] == 1]
            if len(faced) < 3:
                continue
            runs = faced["bat_runs"].sum()
            balls = len(faced)
            exp_self = (base_sr / 100.0) * balls if pd.notna(base_sr) else runs
            exp_phase = float(faced["exp_runs"].sum())
            out = int(ig["is_striker_out"].sum())
            # Consistency uses self-baseline lift; phase-adj used in absolute score
            contrib = (runs - exp_self) - 4.0 * out
            inn_stats.append({"contrib": contrib, "runs": runs, "balls": balls, "out": out,
                              "sr": 100 * runs / balls, "rae": runs - exp_phase})
        if inn_stats:
            idf = pd.DataFrame(inn_stats)
            rec["consist_pos_share"] = float((idf["contrib"] > 0).mean())
            rec["consist_median_contrib"] = float(idf["contrib"].median())
            rec["consist_std_sr"] = float(idf["sr"].std(ddof=0)) if len(idf) > 1 else 0.0
            rec["consist_n_innings"] = int(len(idf))
            # Floor: 20th percentile of per-innings SR under pressure
            rec["consist_sr_p20"] = float(idf["sr"].quantile(0.20))
        else:
            rec["consist_pos_share"] = np.nan
            rec["consist_median_contrib"] = np.nan
            rec["consist_std_sr"] = np.nan
            rec["consist_n_innings"] = 0
            rec["consist_sr_p20"] = np.nan
        rows.append(rec)

    bat = pd.DataFrame(rows)
    bat = bat.merge(teams_lu, on="player_id", how="left", suffixes=("", "_lu"))
    if "player_name_lu" in bat.columns:
        bat["player_name"] = bat["player_name"].fillna(bat["player_name_lu"])

    def _teams_blob(r):
        return " ".join(str(r.get(c, "") or "") for c in
                        ("team_display", "primary_team", "teams_all", "ipl_teams"))

    def _auction_relevant_bat(r):
        if r["hp_balls"] < MIN_PRESSURE_BALLS_BAT or r["hp_innings"] < MIN_PRESSURE_INNINGS_BAT:
            return False
        if r["hp_ipl_balls"] >= MIN_IPL_HP_BALLS:
            return True
        if r["hp_t20i_balls"] >= MIN_FULLMEMBER_T20I_HP_BALLS:
            if any(fm in _teams_blob(r) for fm in FULL_MEMBER_TEAMS):
                return True
        return False

    bat["eligible"] = bat.apply(_auction_relevant_bat, axis=1)
    bat["ipl_banned_nation"] = bat["ipl_banned_nation"].fillna(False).astype(bool)
    bat["eligible_pre_nation_filter"] = bat["eligible"]
    bat["eligible"] = bat["eligible"] & ~bat["ipl_banned_nation"]

    # Population priors from eligible players' HP performance
    elig = bat[bat["eligible"]]
    prior_sr = elig["hp_sr"].median()
    prior_bpd = elig["hp_bpd"].median()

    # Shrunk HP metrics
    bat["hp_sr_shrunk"] = bat.apply(
        lambda r: shrink(r["hp_sr"], r["hp_balls"], prior_sr, PRIOR_BALLS_BAT)
        if pd.notna(r["hp_sr"]) else np.nan,
        axis=1,
    )
    bat["hp_bpd_shrunk"] = bat.apply(
        lambda r: shrink(r["hp_bpd"], r["hp_balls"], prior_bpd, PRIOR_BALLS_BAT)
        if pd.notna(r["hp_bpd"]) else np.nan,
        axis=1,
    )
    bat["base_sr_shrunk"] = bat.apply(
        lambda r: shrink(r["base_sr"], max(r["base_balls"], 1), prior_sr, PRIOR_BALLS_BAT)
        if pd.notna(r["base_sr"]) else prior_sr,
        axis=1,
    )

    # Lift vs own baseline, but clamp a weak baseline so chronically poor
    # batters do not farm lift by being "less bad" under pressure.
    # Floor baseline at 120 SR for lift calculation (still report raw lift separately).
    bat["base_sr_for_lift"] = bat["base_sr_shrunk"].clip(lower=120.0)
    bat["sr_lift"] = bat["hp_sr_shrunk"] - bat["base_sr_for_lift"]
    bat["sr_lift_raw"] = bat["hp_sr_shrunk"] - bat["base_sr_shrunk"]
    bat["sr_lift_pct"] = bat["hp_sr_shrunk"] / bat["base_sr_for_lift"].replace(0, np.nan) - 1

    # Scoring on eligible set only for z-scores
    e = bat[bat["eligible"]].copy()
    e["z_abs_sr"] = 0.60 * zscore(e["hp_sr_shrunk"]) + 0.40 * zscore(e["hp_rae_per_ball"].fillna(0))
    e["z_lift"] = zscore(e["sr_lift"])
    e["z_bpd"] = zscore(e["hp_bpd_shrunk"])
    e["z_consist"] = (
        0.55 * zscore(e["consist_pos_share"].fillna(e["consist_pos_share"].median()))
        + 0.25 * zscore(e["consist_median_contrib"].fillna(0))
        + 0.20 * zscore(e["consist_sr_p20"].fillna(e["consist_sr_p20"].median()))
        - 0.10 * zscore(e["consist_std_sr"].fillna(e["consist_std_sr"].median()))  # lower variance better
    )

    e["composite"] = (
        BAT_W_LIFT * e["z_lift"]
        + BAT_W_ABS * e["z_abs_sr"]
        + BAT_W_SURVIVAL * e["z_bpd"]
        + BAT_W_CONSIST * e["z_consist"]
    )
    # Small sample credibility dampener (already shrunk, but extra for borderline)
    e["credibility"] = e["hp_balls"] / (e["hp_balls"] + PRIOR_BALLS_BAT / 2)
    e["composite"] = e["composite"] * (0.85 + 0.15 * e["credibility"])

    e = e.sort_values("composite", ascending=False).reset_index(drop=True)
    e["rank"] = e.index + 1

    # Attach scores from eligible set; keep full table for export
    score_cols = ["z_abs_sr", "z_lift", "z_bpd", "z_consist", "composite", "credibility", "rank"]
    scores = e[["player_id"] + score_cols]
    # Drop score cols from bat if present to avoid collisions, then merge
    bat = bat.drop(columns=[c for c in score_cols if c in bat.columns], errors="ignore")
    out = bat.merge(scores, on="player_id", how="left")
    out = out.sort_values(["eligible", "composite"], ascending=[False, False]).reset_index(drop=True)
    out.loc[out["eligible"], "rank"] = range(1, int(out["eligible"].sum()) + 1)
    return out, e


def analyze_bowlers(bbb: pd.DataFrame, teams_lu: pd.DataFrame) -> pd.DataFrame:
    df = bbb.copy()
    df["w"] = df["comp_weight"]

    def agg_block(sub, prefix):
        legal = sub[sub["ball_bowled"] == 1]
        balls = legal["w"].sum()
        runs_conc = (sub["ball_total"] * sub["w"]).sum()  # all runs conceded incl extras
        wkts = sub.loc[sub["is_bowler_wicket"], "w"].sum()
        dots = ((legal["ball_total"] == 0) * legal["w"]).sum()
        boundaries = (
            (legal["is_four"].fillna(False) | legal["is_six"].fillna(False)).astype(int) * legal["w"]
        ).sum()
        raw_balls = int(len(legal))
        raw_runs = float(sub["ball_total"].sum())
        raw_wkts = int(sub["is_bowler_wicket"].sum())
        innings = sub[["match_id", "innings"]].drop_duplicates().shape[0]
        matches = sub["match_id"].nunique()
        econ = (runs_conc * 6.0 / balls) if balls > 0 else np.nan
        bpw = (balls / wkts) if wkts > 0 else (balls if balls > 0 else np.nan)
        dot_pct = 100.0 * dots / balls if balls > 0 else np.nan
        bnd_pct = 100.0 * boundaries / balls if balls > 0 else np.nan
        return {
            f"{prefix}_balls": raw_balls,
            f"{prefix}_balls_w": float(balls),
            f"{prefix}_runs": raw_runs,
            f"{prefix}_runs_w": float(runs_conc),
            f"{prefix}_wkts": raw_wkts,
            f"{prefix}_econ": float(econ) if pd.notna(econ) else np.nan,
            f"{prefix}_bpw": float(bpw) if pd.notna(bpw) else np.nan,
            f"{prefix}_dot_pct": float(dot_pct) if pd.notna(dot_pct) else np.nan,
            f"{prefix}_bnd_pct": float(bnd_pct) if pd.notna(bnd_pct) else np.nan,
            f"{prefix}_innings": int(innings),
            f"{prefix}_matches": int(matches),
        }

    rows = []
    for pid, g in df.groupby("bowler_id"):
        name = g["bowler_name"].mode().iloc[0] if len(g["bowler_name"].mode()) else g["bowler_name"].iloc[0]
        hp = g[g["is_high_pressure"]]
        np_ = g[~g["is_high_pressure"]]
        if hp["ball_bowled"].sum() == 0:
            continue
        rec = {"player_id": pid, "player_name": name}
        rec.update(agg_block(hp, "hp"))
        rec.update(agg_block(np_, "base"))
        rec.update(agg_block(g, "all"))
        rec["hp_ipl_balls"] = int(hp.loc[hp["is_ipl"] == True, "ball_bowled"].sum())
        rec["hp_t20i_balls"] = int(hp.loc[hp["comp_bucket"] == "T20I", "ball_bowled"].sum())

        # Phase-adjusted runs saved under HP
        rs = float((hp["exp_runs"] - hp["ball_total"]).sum())
        legal_n = int(hp["ball_bowled"].sum())
        rec["hp_runs_saved"] = rs
        rec["hp_rs_per_ball"] = rs / legal_n if legal_n else 0.0
        rec["hp_exp_econ"] = float(hp["exp_runs"].sum() * 6.0 / legal_n) if legal_n else np.nan

        base_econ = rec["base_econ"] if pd.notna(rec["base_econ"]) and rec["base_balls"] >= 30 else rec["all_econ"]
        inn_stats = []
        for (mid, inn), ig in hp.groupby(["match_id", "innings"]):
            legal = ig[ig["ball_bowled"] == 1]
            if len(legal) < 3:
                continue
            runs = ig["ball_total"].sum()
            balls = len(legal)
            econ = runs * 6.0 / balls
            wkts = int(ig["is_bowler_wicket"].sum())
            exp_self = (base_econ / 6.0) * balls if pd.notna(base_econ) else runs
            contrib = (exp_self - runs) + 6.0 * wkts
            inn_stats.append({"contrib": contrib, "econ": econ, "wkts": wkts, "balls": balls})
        if inn_stats:
            idf = pd.DataFrame(inn_stats)
            rec["consist_pos_share"] = float((idf["contrib"] > 0).mean())
            rec["consist_median_contrib"] = float(idf["contrib"].median())
            rec["consist_std_econ"] = float(idf["econ"].std(ddof=0)) if len(idf) > 1 else 0.0
            rec["consist_n_innings"] = int(len(idf))
            rec["consist_econ_p80"] = float(idf["econ"].quantile(0.80))  # high floor = low p80 econ
        else:
            rec["consist_pos_share"] = np.nan
            rec["consist_median_contrib"] = np.nan
            rec["consist_std_econ"] = np.nan
            rec["consist_n_innings"] = 0
            rec["consist_econ_p80"] = np.nan
        rows.append(rec)

    bowl = pd.DataFrame(rows)
    bowl = bowl.merge(teams_lu, on="player_id", how="left", suffixes=("", "_lu"))
    if "player_name_lu" in bowl.columns:
        bowl["player_name"] = bowl["player_name"].fillna(bowl["player_name_lu"])

    def _teams_blob(r):
        return " ".join(str(r.get(c, "") or "") for c in
                        ("team_display", "primary_team", "teams_all", "ipl_teams"))

    def _auction_relevant_bowl(r):
        if r["hp_balls"] < MIN_PRESSURE_BALLS_BOWL or r["hp_innings"] < MIN_PRESSURE_SPELLS_BOWL:
            return False
        if r.get("hp_wkts", 0) < MIN_HP_WICKETS_BOWL:
            return False
        if r["hp_ipl_balls"] >= MIN_IPL_HP_BALLS:
            return True
        if r["hp_t20i_balls"] >= MIN_FULLMEMBER_T20I_HP_BALLS:
            if any(fm in _teams_blob(r) for fm in FULL_MEMBER_TEAMS):
                return True
        return False

    bowl["eligible"] = bowl.apply(_auction_relevant_bowl, axis=1)
    bowl["ipl_banned_nation"] = bowl["ipl_banned_nation"].fillna(False).astype(bool)
    bowl["eligible_pre_nation_filter"] = bowl["eligible"]
    bowl["eligible"] = bowl["eligible"] & ~bowl["ipl_banned_nation"]

    elig = bowl[bowl["eligible"]]
    prior_econ = elig["hp_econ"].median()
    prior_bpw = elig["hp_bpw"].median()

    bowl["hp_econ_shrunk"] = bowl.apply(
        lambda r: shrink(r["hp_econ"], r["hp_balls"], prior_econ, PRIOR_BALLS_BOWL)
        if pd.notna(r["hp_econ"]) else np.nan,
        axis=1,
    )
    bowl["hp_bpw_shrunk"] = bowl.apply(
        lambda r: shrink(r["hp_bpw"], r["hp_balls"], prior_bpw, PRIOR_BALLS_BOWL)
        if pd.notna(r["hp_bpw"]) else np.nan,
        axis=1,
    )
    bowl["base_econ_shrunk"] = bowl.apply(
        lambda r: shrink(r["base_econ"], max(r["base_balls"], 1), prior_econ, PRIOR_BALLS_BOWL)
        if pd.notna(r["base_econ"]) else prior_econ,
        axis=1,
    )
    # Lift: lower econ under pressure vs baseline is GOOD.
    # Cap a bloated baseline at 9.5 so chronically expensive bowlers
    # cannot farm lift merely by being less expensive under pressure.
    bowl["base_econ_for_lift"] = bowl["base_econ_shrunk"].clip(upper=9.5)
    bowl["econ_lift"] = bowl["base_econ_for_lift"] - bowl["hp_econ_shrunk"]
    bowl["econ_lift_raw"] = bowl["base_econ_shrunk"] - bowl["hp_econ_shrunk"]

    e = bowl[bowl["eligible"]].copy()
    # Absolute: blend phase-adjusted runs saved/ball with raw economy
    e["z_abs_econ"] = (
        0.55 * zscore(e["hp_rs_per_ball"].fillna(0))
        + 0.45 * (-zscore(e["hp_econ_shrunk"]))
    )
    e["z_lift"] = zscore(e["econ_lift"])
    e["z_wkts"] = -zscore(e["hp_bpw_shrunk"])  # lower balls/wkt better
    e["z_dots"] = zscore(e["hp_dot_pct"].fillna(e["hp_dot_pct"].median()))
    e["z_consist"] = (
        0.55 * zscore(e["consist_pos_share"].fillna(e["consist_pos_share"].median()))
        + 0.25 * zscore(e["consist_median_contrib"].fillna(0))
        - 0.20 * zscore(e["consist_econ_p80"].fillna(e["consist_econ_p80"].median()))
        - 0.10 * zscore(e["consist_std_econ"].fillna(e["consist_std_econ"].median()))
    )

    e["composite"] = (
        BOWL_W_LIFT * e["z_lift"]
        + BOWL_W_ABS * e["z_abs_econ"]
        + BOWL_W_WICKETS * e["z_wkts"]
        + BOWL_W_CONSIST * e["z_consist"]
        + 0.05 * e["z_dots"]  # small bonus for dots; renormalize conceptually
    )
    # Renormalize soft: the 0.05 dots is extra; leave as-is for ranking
    e["credibility"] = e["hp_balls"] / (e["hp_balls"] + PRIOR_BALLS_BOWL / 2)
    e["composite"] = e["composite"] * (0.85 + 0.15 * e["credibility"])

    e = e.sort_values("composite", ascending=False).reset_index(drop=True)
    e["rank"] = e.index + 1

    score_cols = ["z_abs_econ", "z_lift", "z_wkts", "z_dots", "z_consist",
                  "composite", "credibility", "rank"]
    scores = e[["player_id"] + score_cols]
    bowl = bowl.drop(columns=[c for c in score_cols if c in bowl.columns], errors="ignore")
    out = bowl.merge(scores, on="player_id", how="left")
    out = out.sort_values(["eligible", "composite"], ascending=[False, False]).reset_index(drop=True)
    out.loc[out["eligible"], "rank"] = range(1, int(out["eligible"].sum()) + 1)
    return out, e


def make_charts(bbb, bat_e, bowl_e, thr):
    charts = {}

    # 1. Pressure index distribution
    fig, ax = plt.subplots(figsize=(9, 5))
    vals = bbb["pressure_index"].dropna()
    ax.hist(vals, bins=50, color=RR_PURPLE, alpha=0.85, edgecolor="white", linewidth=0.4)
    ax.axvline(thr, color=RR_PINK, linewidth=2.5, label=f"High-pressure threshold (Q75 = {thr:.3f})")
    ax.set_xlabel("Pressure Index")
    ax.set_ylabel("Number of balls")
    ax.set_title("Distribution of the Ball-Level Pressure Index")
    ax.legend(frameon=True)
    fig.tight_layout()
    p = CHARTS / "01_pressure_distribution.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    charts["pressure_dist"] = str(p)

    # 2. Example tense passage — pick a close chase with high pressure
    # Find a match with many HP balls in 2nd innings and close result
    m2 = bbb[(bbb["innings"] == 2) & (bbb["is_high_pressure"])]
    match_hp = m2.groupby("match_id").size().sort_values(ascending=False)
    # Prefer close finishes
    example_id = None
    for mid in match_hp.head(40).index:
        sub = bbb[bbb["match_id"] == mid]
        res = str(sub["result"].iloc[0])
        if "Won by 1" in res or "Won by 2" in res or "Won by 3" in res or "Super Over" in res:
            example_id = mid
            break
    if example_id is None:
        example_id = int(match_hp.index[0])

    ex = bbb[bbb["match_id"] == example_id].sort_values(["innings", "innings_ball_num"])
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=False, gridspec_kw={"height_ratios": [2, 1]})
    for inn, ax in [(1, axes[0]), (2, axes[0])]:
        pass
    ax = axes[0]
    for inn, color in [(1, RR_TEAL), (2, RR_PINK)]:
        s = ex[ex["innings"] == inn]
        if s.empty:
            continue
        ax.plot(s["innings_ball_num"], s["cum_runs_before"] + s["ball_total"],
                color=color, label=f"Innings {inn}", linewidth=2)
    ax.set_ylabel("Cumulative runs")
    ax.set_title(f"Example match {example_id}: {ex['result'].iloc[0]}\nPressure index flags the tense passages")
    ax.legend()

    ax2 = axes[1]
    s2 = ex[ex["innings"] == 2]
    if not s2.empty:
        colors = [RR_PINK if hp else "#94A3B8" for hp in s2["is_high_pressure"]]
        ax2.bar(s2["innings_ball_num"], s2["pressure_index"], color=colors, width=1.0, alpha=0.9)
        ax2.axhline(thr, color=RR_GOLD, linestyle="--", linewidth=1.5, label="HP threshold")
        ax2.set_xlabel("Ball number (2nd innings)")
        ax2.set_ylabel("Pressure Index")
        ax2.legend(loc="upper left")
    fig.tight_layout()
    p = CHARTS / "02_example_pressure_passage.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    charts["example"] = str(p)
    charts["example_match_id"] = int(example_id)
    charts["example_result"] = str(ex["result"].iloc[0])

    # 3. Top 10 batters: HP SR vs baseline
    topb = bat_e.head(10).copy()
    fig, ax = plt.subplots(figsize=(10, 6))
    y = np.arange(len(topb))
    ax.hlines(y, topb["base_sr_shrunk"], topb["hp_sr_shrunk"], color="#CBD5E1", linewidth=3)
    ax.scatter(topb["base_sr_shrunk"], y, color="#64748B", s=80, zorder=3, label="Baseline SR (shrunk)")
    ax.scatter(topb["hp_sr_shrunk"], y, color=RR_PINK, s=100, zorder=3, label="Pressure SR (shrunk)")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{int(r.rank)}. {r.player_name}" for r in topb.itertuples()])
    ax.invert_yaxis()
    ax.set_xlabel("Strike rate")
    ax.set_title("Top 10 Batters: Strike Rate Under Pressure vs Own Baseline")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False)
    fig.tight_layout()
    p = CHARTS / "03_top10_batters_sr.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    charts["bat_sr"] = str(p)

    # 4. Top 10 bowlers: HP econ vs baseline
    topw = bowl_e.head(10).copy()
    fig, ax = plt.subplots(figsize=(10, 6))
    y = np.arange(len(topw))
    ax.hlines(y, topw["hp_econ_shrunk"], topw["base_econ_shrunk"], color="#CBD5E1", linewidth=3)
    ax.scatter(topw["base_econ_shrunk"], y, color="#64748B", s=80, zorder=3, label="Baseline economy (shrunk)")
    ax.scatter(topw["hp_econ_shrunk"], y, color=RR_PURPLE, s=100, zorder=3, label="Pressure economy (shrunk)")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{int(r.rank)}. {r.player_name}" for r in topw.itertuples()])
    ax.invert_yaxis()
    ax.set_xlabel("Economy rate")
    ax.set_title("Top 10 Bowlers: Economy Under Pressure vs Own Baseline")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False)
    fig.tight_layout()
    p = CHARTS / "04_top10_bowlers_econ.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    charts["bowl_econ"] = str(p)

    # 5. Consistency chart — batters
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.barh(
        [f"{int(r.rank)}. {r.player_name}" for r in topb.itertuples()][::-1],
        topb["consist_pos_share"].values[::-1] * 100,
        color=RR_TEAL,
    )
    ax.set_xlabel("% of pressure innings with positive contribution")
    ax.set_title("Top 10 Batters: Match-to-Match Reliability Under Pressure")
    ax.set_xlim(0, 100)
    fig.tight_layout()
    p = CHARTS / "05_batter_consistency.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    charts["bat_consist"] = str(p)

    # 6. Consistency bowlers
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.barh(
        [f"{int(r.rank)}. {r.player_name}" for r in topw.itertuples()][::-1],
        topw["consist_pos_share"].values[::-1] * 100,
        color=RR_PURPLE,
    )
    ax.set_xlabel("% of pressure spells with positive contribution")
    ax.set_title("Top 10 Bowlers: Match-to-Match Reliability Under Pressure")
    ax.set_xlim(0, 100)
    fig.tight_layout()
    p = CHARTS / "06_bowler_consistency.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    charts["bowl_consist"] = str(p)

    # 7. Component breakdown for top batters (stacked-ish grouped bars of z)
    fig, ax = plt.subplots(figsize=(11, 6))
    x = np.arange(10)
    width = 0.2
    ax.bar(x - 1.5 * width, topb["z_lift"], width, label="Lift vs self", color=RR_PINK)
    ax.bar(x - 0.5 * width, topb["z_abs_sr"], width, label="Absolute HP SR", color=RR_PURPLE)
    ax.bar(x + 0.5 * width, topb["z_bpd"], width, label="Survival (BPD)", color=RR_TEAL)
    ax.bar(x + 1.5 * width, topb["z_consist"], width, label="Consistency", color=RR_GOLD)
    ax.set_xticks(x)
    ax.set_xticklabels([r.player_name.split()[-1] for r in topb.itertuples()], rotation=30, ha="right")
    ax.axhline(0, color="#94A3B8", linewidth=1)
    ax.set_ylabel("Component z-score")
    ax.set_title("Top 10 Batters: Composite Score Components")
    ax.legend(ncol=2, fontsize=9)
    fig.tight_layout()
    p = CHARTS / "07_batter_components.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    charts["bat_comp"] = str(p)

    # 8. HP share by innings/over heatmap-ish
    fig, ax = plt.subplots(figsize=(10, 4))
    tmp = bbb.copy()
    tmp["over_bin"] = tmp["over_num"].clip(1, 20)
    heat = tmp.groupby(["innings", "over_bin"])["is_high_pressure"].mean().unstack(0) * 100
    heat.plot(kind="bar", ax=ax, color=[RR_TEAL, RR_PINK], width=0.8)
    ax.set_xlabel("Over")
    ax.set_ylabel("% balls classified high-pressure")
    ax.set_title("Where High-Pressure Balls Occur (by over & innings)")
    ax.legend(["1st innings", "2nd innings"])
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
    fig.tight_layout()
    p = CHARTS / "08_hp_by_over.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    charts["hp_over"] = str(p)

    return charts


def export_tables(bat_all, bat_e, bowl_all, bowl_e, verify, thr, charts):
    bat_cols = [
        "rank", "score_rank", "available_as_player", "excluded_from_picks_reason", "player_id", "player_name", "team_display", "latest_ipl_team", "latest_ipl_season", "availability_status", "availability_note", "source", "national_teams", "ipl_banned_nation", "eligible_pre_nation_filter", "eligible",
        "hp_balls", "hp_innings", "hp_matches", "hp_runs", "hp_outs",
        "hp_sr", "hp_sr_shrunk", "base_sr", "base_sr_shrunk", "sr_lift", "sr_lift_pct",
        "hp_bpd", "hp_bpd_shrunk", "hp_rae", "hp_rae_per_ball",
        "consist_pos_share", "consist_median_contrib", "consist_sr_p20", "consist_n_innings",
        "hp_ipl_balls", "hp_t20i_balls",
        "z_lift", "z_abs_sr", "z_bpd", "z_consist", "credibility", "composite",
    ]
    bowl_cols = [
        "rank", "score_rank", "available_as_player", "excluded_from_picks_reason", "player_id", "player_name", "team_display", "latest_ipl_team", "latest_ipl_season", "availability_status", "availability_note", "source", "national_teams", "ipl_banned_nation", "eligible_pre_nation_filter", "eligible",
        "hp_balls", "hp_innings", "hp_matches", "hp_runs", "hp_wkts",
        "hp_econ", "hp_econ_shrunk", "base_econ", "base_econ_shrunk", "econ_lift",
        "hp_bpw", "hp_bpw_shrunk", "hp_dot_pct", "hp_bnd_pct",
        "hp_runs_saved", "hp_rs_per_ball", "hp_exp_econ",
        "consist_pos_share", "consist_median_contrib", "consist_econ_p80", "consist_n_innings",
        "hp_ipl_balls", "hp_t20i_balls",
        "z_lift", "z_abs_econ", "z_wkts", "z_consist", "credibility", "composite",
    ]

    # Latest IPL franchise (from data) + externally sourced availability notes
    mp = pd.read_csv(DATA / "competition_team_player_mapping.csv")
    ipl = mp[mp["comp_name"].str.startswith("IPL")].copy()
    ipl["season"] = ipl["comp_name"].str.extract(r"(\d{4})").astype(int)
    latest = (ipl.sort_values("season").groupby("player_id")
              .agg(latest_ipl_team=("team_name", "last"), latest_ipl_season=("season", "last"))
              .reset_index())
    avail_path = ROOT / "auction_availability.csv"
    avail = pd.read_csv(avail_path) if avail_path.exists() else pd.DataFrame(columns=["player_name"])
    bat_all = bat_all.merge(latest, on="player_id", how="left").merge(avail, on="player_name", how="left")
    bowl_all = bowl_all.merge(latest, on="player_id", how="left").merge(avail, on="player_name", how="left")
    bat_e = bat_e.merge(latest, on="player_id", how="left").merge(avail, on="player_name", how="left")
    bowl_e = bowl_e.merge(latest, on="player_id", how="left").merge(avail, on="player_name", how="left")
    for d in (bat_all, bowl_all, bat_e, bowl_e):
        d["availability_status"] = d["availability_status"].fillna("Status unreported")

    bat_out = bat_all.copy()
    # ensure team_display
    if "team_display" not in bat_out.columns:
        bat_out["team_display"] = bat_out.get("primary_team", "")
    bat_export = bat_out[[c for c in bat_cols if c in bat_out.columns]].copy()
    bat_export.to_csv(OUT / "batter_rankings.csv", index=False)

    bowl_out = bowl_all.copy()
    if "team_display" not in bowl_out.columns:
        bowl_out["team_display"] = bowl_out.get("primary_team", "")
    bowl_export = bowl_out[[c for c in bowl_cols if c in bowl_out.columns]].copy()
    bowl_export.to_csv(OUT / "bowler_rankings.csv", index=False)

    top10b = bat_e.head(10).copy()
    top10w = bowl_e.head(10).copy()
    top10b.to_csv(OUT / "top10_batters.csv", index=False)
    top10w.to_csv(OUT / "top10_bowlers.csv", index=False)

    meta = {
        "hp_threshold": thr,
        "hp_quantile": HP_QUANTILE,
        "min_pressure_balls_bat": MIN_PRESSURE_BALLS_BAT,
        "min_pressure_innings_bat": MIN_PRESSURE_INNINGS_BAT,
        "min_pressure_balls_bowl": MIN_PRESSURE_BALLS_BOWL,
        "min_pressure_spells_bowl": MIN_PRESSURE_SPELLS_BOWL,
        "min_hp_wickets_bowl": MIN_HP_WICKETS_BOWL,
        "min_ipl_hp_balls": MIN_IPL_HP_BALLS,
        "min_fullmember_t20i_hp_balls": MIN_FULLMEMBER_T20I_HP_BALLS,
        "bat_weights": {
            "lift": BAT_W_LIFT, "abs": BAT_W_ABS,
            "survival": BAT_W_SURVIVAL, "consistency": BAT_W_CONSIST,
        },
        "bowl_weights": {
            "lift": BOWL_W_LIFT, "abs": BOWL_W_ABS,
            "wickets": BOWL_W_WICKETS, "consistency": BOWL_W_CONSIST,
        },
        "verify": verify,
        "charts": charts,
        "n_excluded_nation_bat": int((bat_all["eligible_pre_nation_filter"] & bat_all["ipl_banned_nation"]).sum()),
        "n_excluded_nation_bowl": int((bowl_all["eligible_pre_nation_filter"] & bowl_all["ipl_banned_nation"]).sum()),
        "excluded_nation_teams": sorted(IPL_EXCLUDED_TEAMS),
        "n_eligible_batters": int(len(bat_e)),
        "n_eligible_bowlers": int(len(bowl_e)),
    }
    with open(OUT / "meta.json", "w") as f:
        json.dump(meta, f, indent=2, default=str)

    print("[export] wrote batter_rankings.csv, bowler_rankings.csv, top10_*.csv, meta.json")
    return bat_export, bowl_export, top10b, top10w, meta


def main():
    print("=== Loading data ===")
    bbb, matches, comps, teams, mapping, pe = load_data()
    print(f"balls={len(bbb)} matches={len(matches)}")

    print("=== Verifying runs/extras semantics ===")
    verify = verify_runs_semantics(bbb, matches)

    print("=== Enriching balls + pressure index ===")
    bbb = enrich_balls(bbb, matches, comps)
    bbb = compute_pressure_index(bbb)
    bbb = add_phase_expected(bbb)
    thr = bbb.attrs["hp_threshold"]

    # Save enriched sample for debugging
    bbb[
        [
            "match_id", "innings", "over_num", "innings_ball_num",
            "striker_name", "bowler_name", "bat_runs", "ball_total",
            "rrr", "wickets_in_hand", "balls_remaining",
            "pressure_index", "is_high_pressure", "comp_bucket",
        ]
    ].head(5000).to_csv(OUT / "sample_enriched_balls.csv", index=False)

    print("=== Player-team lookup ===")
    teams_lu = player_team_lookup(mapping)

    print("=== Batter analysis ===")
    bat_all, bat_e = analyze_batters(bbb, teams_lu)
    print(f"eligible batters: {len(bat_e)}")
    print(bat_e[["rank", "player_name", "hp_balls", "hp_sr", "sr_lift", "consist_pos_share", "composite"]].head(12).to_string(index=False))

    print("=== Bowler analysis ===")
    bowl_all, bowl_e = analyze_bowlers(bbb, teams_lu)
    # Players scored in the pool but removed from the picks because they are not
    # available as players (scoring pool and z-scores are left unchanged).
    def _apply_unavailable(full, e):
        full = full.copy(); e = e.copy()
        full["score_rank"] = full["rank"]; e["score_rank"] = e["rank"]
        full["available_as_player"] = ~full["player_name"].isin(NOT_AVAILABLE_AS_PLAYER)
        e = e[~e["player_name"].isin(NOT_AVAILABLE_AS_PLAYER)].reset_index(drop=True)
        e["rank"] = e.index + 1
        full["rank"] = np.nan
        m = full["eligible"] & full["available_as_player"]
        full.loc[m, "rank"] = range(1, int(m.sum()) + 1)  # full already sorted by composite
        full["excluded_from_picks_reason"] = full["player_name"].map(NOT_AVAILABLE_AS_PLAYER)
        return full, e
    bowl_all, bowl_e = _apply_unavailable(bowl_all, bowl_e)
    bat_all, bat_e = _apply_unavailable(bat_all, bat_e)
    print(f"eligible bowlers: {len(bowl_e)}")
    print(bowl_e[["rank", "player_name", "hp_balls", "hp_econ", "econ_lift", "consist_pos_share", "composite"]].head(12).to_string(index=False))

    print("=== Charts ===")
    charts = make_charts(bbb, bat_e, bowl_e, thr)

    print("=== Validation of pressure index ===")
    from validation import run_validation, outcome_chart
    cols = {"pink": RR_PINK, "purple": RR_PURPLE, "teal": RR_TEAL, "gold": RR_GOLD}
    val = run_validation(bbb, OUT, CHARTS, cols)
    charts["validation_deciles"] = val["chart"]
    charts["validation_outcome"] = outcome_chart(val["outcome"], CHARTS, cols)
    charts["val_spearman_wicket"] = val["spearman_wicket"]
    charts["val_spearman_runrate"] = val["spearman_runrate"]
    charts["val_chase_win_hp_ball"] = val["chase_win_hp_ball"]
    charts["val_chase_win_normal_ball"] = val["chase_win_normal_ball"]
    print(val["overall"].round(2))
    from validation import phase_split
    extra_bat = ["Glenn Maxwell", "Rachin Ravindra", "Sikandar Raza", "Donovan Ferreira", "Riyan Parag",
                 "Dhruv Jurel", "Yashasvi Jaiswal", "Ravindra Jadeja", "Nitish Rana", "Mark Chapman"]
    extra_bowl = ["Matheesha Pathirana", "Lockie Ferguson", "Reece Topley", "Sikandar Raza", "Avesh Khan",
                  "Akash Madhwal", "Jofra Archer", "Mohammed Shami", "Ravi Bishnoi", "Ravindra Jadeja",
                  "Brijesh Sharma", "Sandeep Sharma", "Nandre Burger", "Glenn Maxwell", "Adil Rashid"]
    phase_split(bbb, bat_e.head(10)["player_name"].tolist() + extra_bat,
                bowl_e.head(10)["player_name"].tolist() + extra_bowl, OUT)

    print("=== Export tables ===")
    export_tables(bat_all, bat_e, bowl_all, bowl_e, verify, thr, charts)

    # Persist enriched bbb summary stats
    summary = {
        "n_balls": int(len(bbb)),
        "n_hp_balls": int(bbb["is_high_pressure"].sum()),
        "hp_share": float(bbb["is_high_pressure"].mean()),
        "hp_by_innings": bbb.groupby("innings")["is_high_pressure"].mean().to_dict(),
        "hp_by_bucket": bbb.groupby("comp_bucket")["is_high_pressure"].mean().to_dict(),
    }
    with open(OUT / "summary_stats.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("=== Done analysis core ===")
    return bat_e, bowl_e, thr, verify, charts


if __name__ == "__main__":
    main()
