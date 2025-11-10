# src/skytech_snapshot.py
import json, os, io, math
from datetime import datetime, timedelta, timezone
import pytz
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

JST = pytz.timezone("Asia/Tokyo")
OUT = "docs/outputs"
os.makedirs(OUT, exist_ok=True)

# 表示用コード -> Yahoo! Finance ティッカー
JP_TICKERS = {
    "6232":  "6232.T",   # ACSL
    "218A":  "218A.T",   # リベラウェア
    "278A":  "278A.T",   # テラドローン
}
DISPLAY_CODES = list(JP_TICKERS.keys())
YF_TICKERS = list(JP_TICKERS.values())

def jst_now():
    return datetime.now(JST)

def to_jst(ts):
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(JST)

def fetch_intraday_5m(tickers: list[str], days: int = 5) -> pd.DataFrame:
    """
    直近days日分の5分足を取得し、マルチインデックス:
      index: Datetime (UTC)
      columns: (ticker, field)
    """
    df = yf.download(
        tickers=" ".join(tickers),
        period=f"{days}d",
        interval="5m",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        prepost=False,
        threads=True,
    )
    # yfinanceの戻りは単一銘柄と複数で構造が変わるので正規化
    if isinstance(df.columns, pd.MultiIndex):
        return df
    # 単一銘柄のとき
    df = pd.concat({tickers[0]: df}, axis=1)
    return df

def build_today_pct(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, float, datetime]:
    """
    当日(JST)の寄り付き比%の等加重平均を作る。
    返り値: (jst_time, pct_df[["pct"]], last_pct, data_date_jst)
    """
    # UTC→JST の DatetimeIndex へ
    utc_index = df_raw.index
    jst_index = pd.to_datetime(utc_index).tz_localize("UTC").tz_convert(JST)
    df_raw = df_raw.copy()
    df_raw.index = jst_index

    today = jst_now().date()
    # 当日JSTのデータ抽出。無ければ直近営業日を使う
    date_candidates = sorted({ts.date() for ts in df_raw.index})
    use_date = today if today in date_candidates else (date_candidates[-1] if date_candidates else today)

    frames = []
    for disp, yf_t in JP_TICKERS.items():
        # yfinanceの列: (ticker, 'Close') が基本（auto_adjust=True）
        if (yf_t, "Close") not in df_raw.columns:
            continue
        s = df_raw[(yf_t, "Close")].dropna()
        s = s[s.index.date == use_date]
        if s.empty:
            continue
        # 最初のバーを「当日寄り付き価格」とみなす（場中前場再開を考慮し最初の値）
        open_px = float(s.iloc[0])
        pct = (s / open_px - 1.0) * 100.0
        frames.append(pct.rename(disp))

    if not frames:
        raise RuntimeError("no intraday data for JP tickers")

    wide = pd.concat(frames, axis=1)
    # 等金額加重平均（NaN除外で平均）
    avg = wide.mean(axis=1, skipna=True).to_frame("pct")
    last_pct = float(avg.iloc[-1])

    return avg, last_pct, datetime.combine(use_date, datetime.min.time(), tzinfo=JST)

def save_chart(avg_pct: pd.DataFrame, last_pct: float, data_date_jst: datetime):
    fig = plt.figure(figsize=(12, 6), dpi=150)
    ax = fig.add_subplot(111)
    # ダークテーマ
    ax.set_facecolor("#0b1420")
    fig.patch.set_facecolor("#0b1420")
    ax.tick_params(colors="#cfe6f3")
    for spine in ax.spines.values():
        spine.set_color("#223447")

    color = "#34d399" if last_pct >= 0 else "#fb7185"
    ax.plot(avg_pct.index, avg_pct["pct"], lw=2.2, color="#8ce7e7")  # ラインは爽やかに
    ax.fill_between(avg_pct.index, avg_pct["pct"], 0, alpha=0.18, color=color)

    ax.set_ylabel("Change vs Open (%)", color="#cfe6f3")
    ax.set_title(f"SKYTECH-3 Intraday Snapshot ({data_date_jst.strftime('%Y/%m/%d')} JST)",
                 color="#d9f0ff", fontsize=13, pad=10)
    ax.grid(True, alpha=0.15, color="#4b5b6b")

    out_png = os.path.join(OUT, "skytech_3_intraday.png")
    fig.tight_layout()
    fig.savefig(out_png, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)

def save_csv(avg_pct: pd.DataFrame):
    out_csv = os.path.join(OUT, "skytech_3_intraday.csv")
    df = avg_pct.copy()
    df.index = df.index.tz_convert(JST)
    df.index.name = "datetime_jst"
    df.to_csv(out_csv, float_format="%.6f")

def save_stats(last_pct: float, when: datetime):
    payload = {
        "key": "SKYTECH-3",
        "pct_intraday": round(last_pct, 2),
        "updated_at": when.strftime("%Y/%m/%d %H:%M"),
        "unit": "pct",
        "tickers": DISPLAY_CODES,
    }
    with open(os.path.join(OUT, "skytech_3_stats.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def save_post_text(last_pct: float):
    lines = [
        "【SKYTECH-3｜スカイテック指数】",
        f"本日：{last_pct:+.2f}%",
        "指数：None",  # 将来 日次レベル導入時に差替え
        f"構成：{'/'.join(DISPLAY_CODES)}",
        "#桜Index #SkyTech",
    ]
    with open(os.path.join(OUT, "skytech_3_post_intraday.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def save_heartbeat():
    with open(os.path.join(OUT, "last_run.txt"), "w", encoding="utf-8") as f:
        f.write(jst_now().strftime("%Y/%m/%d %H:%M:%S"))

def main():
    os.makedirs(OUT, exist_ok=True)
    df_raw = fetch_intraday_5m(YF_TICKERS, days=5)
    avg, last_pct, use_date = build_today_pct(df_raw)
    save_chart(avg, last_pct, use_date)
    save_csv(avg)
    save_stats(last_pct, jst_now())
    save_post_text(last_pct)
    save_heartbeat()

if __name__ == "__main__":
    main()
