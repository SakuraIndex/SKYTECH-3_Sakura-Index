from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "outputs"

def _style_ax(ax, title):
    ax.set_title(title, color="#d4e9f7", fontsize=13, pad=10)
    ax.set_facecolor("#0b1420")
    ax.tick_params(colors="#9fb6c7")
    for s in ax.spines.values():
        s.set_color("#1c2a3a")

def plot_range(levels: pd.Series, days: int, fn: str, title: str):
    if levels.empty: 
        return
    s = levels.copy()
    s.index = pd.to_datetime(s.index)
    s = s[s.index >= (s.index.max() - pd.Timedelta(days=days))]
    fig, ax = plt.subplots(figsize=(14, 6), dpi=130)
    fig.patch.set_facecolor("#0b1420")
    _style_ax(ax, title)
    ax.plot(s.index, s.values, color="#93c5fd", linewidth=2.2)
    fig.tight_layout()
    fig.savefig(OUT / fn, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)

def main():
    csv = OUT / "skytech_3_levels.csv"
    if not csv.exists():
        print("no levels csv")
        return
    levels = pd.read_csv(csv, index_col=0, squeeze=True)
    if isinstance(levels, pd.DataFrame):
        levels = levels.iloc[:,0]
    plot_range(levels, 7,   "skytech_3_7d.png", "SKYTECH-3 | 7日")
    plot_range(levels, 30,  "skytech_3_1m.png", "SKYTECH-3 | 1ヶ月")
    plot_range(levels, 365, "skytech_3_1y.png", "SKYTECH-3 | 1年")

if __name__ == "__main__":
    main()
