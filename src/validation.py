"""Validation of the pressure index (imported by analysis.py)."""
import numpy as np, pandas as pd, matplotlib.pyplot as plt

def _stats(d):
    legal = d[d["ball_bowled"] == 1]
    faced = d[d["ball_faced"] == 1]
    return pd.Series({
        "balls": len(d),
        "run_rate": d["ball_total"].sum() * 6 / max(len(legal), 1),
        "dot_pct": 100 * (legal["ball_total"] == 0).mean(),
        "boundary_pct": 100 * (faced["is_four"].fillna(False) | faced["is_six"].fillna(False)).mean(),
        "wicket_pct": 100 * d["is_wicket"].fillna(False).sum() / max(len(legal), 1),
        "bowler_wkt_pct": 100 * d["is_bowler_wicket"].sum() / max(len(legal), 1),
        "batting_sr": 100 * faced["bat_runs"].sum() / max(len(faced), 1),
        "balls_per_wicket": len(legal) / max(d["is_wicket"].fillna(False).sum(), 1),
    })

def run_validation(bbb, out_dir, chart_dir, colors):
    b = bbb.copy()
    res = {}
    # 1. HP vs normal, overall
    t = b.groupby(b["is_high_pressure"].map({True: "High pressure", False: "Normal"})).apply(_stats).T
    t["Gap (HP - Normal)"] = t["High pressure"] - t["Normal"]
    t.to_csv(out_dir / "validation_hp_vs_normal.csv")
    res["overall"] = t
    # 2. Same over band (phase-controlled): within death overs, and within overs 7-15
    rows = []
    for band, mask in [("Overs 1-6", b.over_num <= 6), ("Overs 7-15", (b.over_num >= 7) & (b.over_num <= 15)),
                       ("Overs 16-20", b.over_num >= 16)]:
        for hp in [True, False]:
            s = _stats(b[mask & (b.is_high_pressure == hp)]); s["band"] = band; s["hp"] = "High pressure" if hp else "Normal"
            rows.append(s)
    ph = pd.DataFrame(rows); ph.to_csv(out_dir / "validation_by_phase.csv", index=False); res["phase"] = ph
    # 3. Deciles (rank-based to handle ties at 0)
    b["decile"] = pd.qcut(b["pressure_index"].rank(method="first"), 10, labels=range(1, 11)).astype(int)
    dec = b.groupby("decile").apply(_stats)
    dec["mean_pi"] = b.groupby("decile")["pressure_index"].mean()
    dec.to_csv(out_dir / "validation_deciles.csv"); res["deciles"] = dec
    rho_w = dec["wicket_pct"].corr(pd.Series(dec.index, index=dec.index), method="spearman")
    rho_r = dec["run_rate"].corr(pd.Series(dec.index, index=dec.index), method="spearman")
    res["spearman_wicket"] = float(rho_w); res["spearman_runrate"] = float(rho_r)
    # 4. Outcome check: 2nd innings HP balls -> chasing team loses more often?
    c = b[(b.innings == 2) & b.win_team_id.notna()].copy()
    c["chase_won"] = c["batting_team_id"] == c["win_team_id"]
    inn = c.groupby(["match_id"]).agg(hp_share=("is_high_pressure", "mean"), won=("chase_won", "first"))
    inn["hp_quartile"] = pd.qcut(inn["hp_share"].rank(method="first"), 4, labels=["Q1 (least)", "Q2", "Q3", "Q4 (most)"])
    oc = inn.groupby("hp_quartile", observed=True).agg(matches=("won", "size"), chase_win_pct=("won", lambda s: 100 * s.mean()))
    # Ball-level: chasing side win % when ball is HP vs normal
    bl = c.groupby("is_high_pressure")["chase_won"].mean() * 100
    oc.to_csv(out_dir / "validation_outcome.csv"); res["outcome"] = oc
    res["chase_win_hp_ball"] = float(bl.get(True, np.nan)); res["chase_win_normal_ball"] = float(bl.get(False, np.nan))

    # Chart: deciles
    fig, ax1 = plt.subplots(figsize=(10, 5))
    x = dec.index
    ax1.bar(x, dec["wicket_pct"], color=colors["pink"], alpha=0.85, label="Wicket % per legal ball")
    ax1.set_xlabel("Pressure Index decile (1 = calmest, 10 = most pressure)")
    ax1.set_ylabel("Wickets per 100 legal balls", color=colors["pink"])
    ax2 = ax1.twinx()
    ax2.plot(x, dec["dot_pct"], color=colors["purple"], marker="o", lw=2.5, label="Dot-ball %")
    ax2.plot(x, dec["boundary_pct"], color=colors["teal"], marker="s", lw=2.5, label="Boundary %")
    ax2.set_ylabel("% of balls")
    ax2.grid(False)
    ax1.set_xticks(list(x))
    h1, l1 = ax1.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, fontsize=10, frameon=False)
    ax1.set_title("Validation: dismissal risk rises with the Pressure Index")
    fig.tight_layout(); p = chart_dir / "09_validation_deciles.png"; fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    res["chart"] = str(p)
    return res


def outcome_chart(oc, chart_dir, colors):
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.bar([str(i) for i in oc.index], oc["chase_win_pct"], color=[colors["teal"], colors["purple"], colors["gold"], colors["pink"]])
    for i, v in enumerate(oc["chase_win_pct"]):
        ax.text(i, v + 1.5, f"{v:.1f}%", ha="center", fontsize=10)
    ax.set_ylim(0, 105); ax.set_ylabel("Chasing side win %")
    ax.set_xlabel("Share of the chase spent in high pressure (quartile of matches)")
    ax.set_title("Validation: more pressure in a chase -> chasing side loses")
    fig.tight_layout(); p = chart_dir / "10_validation_outcome.png"; fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return str(p)


def phase_split(bbb, bat_names, bowl_names, out_dir):
    """HP performance by phase for top picks (used for the RR-fit section)."""
    hp = bbb[bbb["is_high_pressure"]]
    phases = {"Overs 1-6": (1, 6), "Overs 7-11": (7, 11), "Overs 12-15": (12, 15), "Overs 16-20": (16, 20)}
    rows = []
    for n in bowl_names:
        g = hp[hp["bowler_name"] == n]
        for ph, (a, z) in phases.items():
            s = g[(g.over_num >= a) & (g.over_num <= z)]
            legal = int(s["ball_bowled"].sum())
            rows.append({"role": "bowler", "player_name": n, "phase": ph, "hp_balls": legal,
                         "hp_econ": round(s["ball_total"].sum() * 6 / legal, 2) if legal else None,
                         "hp_wkts": int(s["is_bowler_wicket"].sum()), "hp_sr": None})
    for n in bat_names:
        g = hp[(hp["striker_name"] == n)]
        for ph, (a, z) in phases.items():
            s = g[(g.over_num >= a) & (g.over_num <= z)]
            faced = int(s["ball_faced"].sum())
            rows.append({"role": "batter", "player_name": n, "phase": ph, "hp_balls": faced,
                         "hp_sr": round(100 * s.loc[s.ball_faced == 1, "bat_runs"].sum() / faced, 1) if faced else None,
                         "hp_wkts": int(s["is_striker_out"].sum()), "hp_econ": None})
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "rr_fit_phase_stats.csv", index=False)
    return df
