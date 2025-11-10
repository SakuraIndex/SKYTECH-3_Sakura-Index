import json
from pathlib import Path
from datetime import timezone, timedelta, datetime

import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "outputs"
CONF = ROOT / "src" / "skytech_tickers.json"
JST = timezone(timedelta(hours=9))

def jst_now_str():
    return datetime.now(JST).strftime("%Y/%m/%d %H:%M (JST)")

def load_stats():
    p = OUT / "skytech_3_stats.json"
    return json.loads(p.read_text()) if p.exists() else {}

def main():
    csvp = OUT / "skytech_3_intraday.csv"
    if not csvp.exists():
        print("no intraday csv; skip chart")
        return
    s = pd.read_csv(csvp)
    s["datetime_jst"] = pd.to_datetime(s["datetime_jst"])
    s = s.set_index("datetime_jst")["pct"]

    stats = load_stats()
    pct_now = float(stats.get("pct_intraday", 0.0))
    title = f"SKYTECH-3 Intraday Snapshot ({jst_now_str()})"

    # 黒ベース・精細な見栄え
    fig, ax = plt.subplots(figsize=(14, 6), dpi=130)
    fig.patch.set_facecolor("#0b1420")
    ax.set_facecolor("#0b1420")

    pos = pct_now >= 0
    line_color = "#67e8f9" if pos else "#fda4af"
    fill_color = "#0ea5a880" if pos else "#ef444480"

    ax.plot(s.index, s.values, linewidth=2.2, color=line_color)
    ax.fill_between(s.index, 0, s.values, where=(s.values>=0), interpolate=True, alpha=0.25, color="#0ea5a8")
    ax.fill_between(s.index, 0, s.values, where=(s.values<0),  interpolate=True, alpha=0.25, color="#ef4444")

    ax.set_title(title, color="#d4e9f7", fontsize=14, pad=12)
    ax.set_ylabel("Change vs Open (%)", color="#9fb6c7")
    ax.tick_params(colors="#9fb6c7")
    for spine in ax.spines.values():
        spine.set_color("#1c2a3a")

    fig.tight_layout()
    fig.savefig(OUT / "skytech_3_intraday.png", facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)

if __name__ == "__main__":
    main()
