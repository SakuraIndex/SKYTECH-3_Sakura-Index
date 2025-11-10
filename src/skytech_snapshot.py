# src/skytech_snapshot.py  (tz-safe 版)
import json, os
from datetime import datetime, timezone
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

def ensure_utc_index(idx) -> pd.DatetimeIndex:
    """idxがnaiveならUTCでtz_localize、既にtzありならUTCへtz_convert。"""
    di = pd.DatetimeIndex(idx)
    if di.tz is None:
        return di.tz_localize("UTC")
    return di.tz_convert("UTC")

def fetch_intraday_5m(tickers: list[str], days: int = 5) -> pd.DataFrame:
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
    if isinstance(df.columns, pd.MultiIndex):
        return df
    # 単一銘柄時は MultiIndex 化
    return pd.concat({tickers[0]: df}, axis=1)

def build_today_pct(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, float, datetime]:
    """
    当日(JST)の寄り付き比%の等金額加重を作成。
    戻り値: (pct_df[["pct"]], last_pct, use_date_jst)
    """
    # UTC→JST への安全変換
    utc_index = ensure_utc_index(df_raw.index)
    jst_index = utc_index.tz_convert(JST)
    df_raw = df_raw.copy()
    df_raw.index = jst_index

    today = jst_now().date()
    date_candidates = sorted({ts.date() for ts in df_raw.index})
    use_date = today if today in date_candidates else (date_candidates[-1] if date_candidates else today)

    frames = []
    for disp, yf_t in JP_TICKERS.items():
        col = (yf_t, "Close")
        if col not in df_raw.columns:
            continue
        s = df_raw[col].dropna()
        s = s[s.index.date == use_date]
        if s.empty:
            continue
        open_px = float(s.iloc[0])
        pct = (s / open_px - 1.0) * 100.0
        frames.append(pct.rename(disp))

    if not frames:
        raise RuntimeError("no intraday data for JP tickers")

    wide = pd.concat(frames, axis=1)
    avg = wide.mean(axis=1, skipna=True).to_frame("pct")
    last_pct = float(avg.iloc[-1])
    return avg, last_pct, datetime.combine(use_date, datetime.min.time(), tzinfo=JST)

def save_chart(avg_pct: pd.DataFrame, last_pct: float, data_date_jst: datetime):
    fig = plt.figure(figsize=(12, 6), dpi=150)
    ax = fig.add_subplot(111)
    # ダークテーマ
    ax.set_facecolor("#0b1420"); fig.patch.set_facecolor("#0b1420")
    ax.tick_params(colors="#cfe6f3")
    for s in ax.spines.values(): s.set_color("#223447")

    ax.plot(avg_pct.index, avg_pct["pct"], lw=2.2, color="#8ce7e7")
    fillc = "#34d399" if last_pct >= 0 else "#fb7185"
    ax.fill_between(avg_pct.index, avg_pct["pct"], 0, alpha=0.18, color=fillc)

    ax.set_ylabel("Change vs Open (%)", color="#cfe6f3")
    ax.set_title(f"SKYTECH-3 Intraday Snapshot ({data_date_jst.strftime('%Y/%m/%d')} JST)",
                 color="#d9f0ff", fontsize=13, pad=10)
    ax.grid(True, alpha=0.15, color="#4b5b6b")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "skytech_3_intraday.png"),
                facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)

def save_csv(avg_pct: pd.DataFrame):
    out_csv = os.path.join(OUT, "skytech_3_intraday.csv")
    df = avg_pct.copy()
    df.index = pd.DatetimeIndex(df.index).tz_convert(JST)
    df.index.name = "datetime_jst"
    df.to_csv(out_csv, float_format="%.6f")

def save_stats(last_pct: float):
    payload = {
        "key": "SKYTECH-3",
        "pct_intraday": round(last_pct, 2),
        "updated_at": jst_now().strftime("%Y/%m/%d %H:%M"),
        "unit": "pct",
        "tickers": DISPLAY_CODES,
    }
    with open(os.path.join(OUT, "skytech_3_stats.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def save_post_text(last_pct: float):
    lines = [
        "【SKYTECH-3｜スカイテック指数】",
        f"本日：{last_pct:+.2f}%",
        "指数：None",
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
    save_stats(last_pct)
    save_post_text(last_pct)
    save_heartbeat()

if __name__ == "__main__":
    main()
