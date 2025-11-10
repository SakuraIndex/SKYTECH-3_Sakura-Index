# scripts/make_intraday_chart.py
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import pytz, os

JST = pytz.timezone("Asia/Tokyo")
OUT = "docs/outputs"

def main():
    df = pd.read_csv(os.path.join(OUT, "skytech_3_intraday.csv"))
    df["datetime_jst"] = pd.to_datetime(df["datetime_jst"]).dt.tz_localize(JST)
    df = df.set_index("datetime_jst")
    last = float(df["pct"].iloc[-1])

    # 簡略チャート（snapshotと同じ色味に合わせる）
    fig = plt.figure(figsize=(12, 6), dpi=150)
    ax = fig.add_subplot(111)
    ax.set_facecolor("#0b1420")
    fig.patch.set_facecolor("#0b1420")
    ax.tick_params(colors="#cfe6f3")
    for s in ax.spines.values():
        s.set_color("#223447")
    ax.plot(df.index, df["pct"], lw=2.2, color="#8ce7e7")
    ax.fill_between(df.index, df["pct"], 0, alpha=0.18, color=("#34d399" if last>=0 else "#fb7185"))
    ax.set_ylabel("Change vs Open (%)", color="#cfe6f3")
    ax.set_title("SKYTECH-3 Intraday Snapshot", color="#d9f0ff")
    ax.grid(True, alpha=0.15, color="#4b5b6b")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "skytech_3_intraday.png"))
    plt.close(fig)

if __name__ == "__main__":
    main()
