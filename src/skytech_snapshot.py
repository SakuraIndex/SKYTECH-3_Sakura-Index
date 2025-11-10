from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "outputs"
CONF = ROOT / "src" / "skytech_tickers.json"

JST = timezone(timedelta(hours=9))

def jst_now() -> datetime:
    return datetime.now(JST)

def jst_now_str() -> str:
    return jst_now().strftime("%Y/%m/%d %H:%M (JST)")

# ---------- 修正：日足ダウンロードを頑健化 ----------
def _download_daily(tickers: list[str], start: str = "2023-01-01") -> pd.DataFrame:
    """
    複数形状に対応して 'Adj Close' を列=ティッカーの DataFrame にする。
    返り値: index=Date, columns=[tickers], values=Adj Close
    """
    df = yf.download(
        tickers,
        start=start,
        interval="1d",
        group_by="ticker",      # (Ticker, Field) になるケースが多い
        auto_adjust=False,
        progress=False,
    )

    # 1銘柄時: 単純列
    if not isinstance(df.columns, pd.MultiIndex):
        if "Adj Close" in df.columns:
            out = df[["Adj Close"]].rename(columns={"Adj Close": tickers[0]})
        else:
            # 予備: Closeしかない等
            col = "Adj Close" if "Adj Close" in df.columns else "Close"
            out = df[[col]].rename(columns={col: tickers[0]})
        out.index = pd.to_datetime(out.index)
        return out.sort_index()

    # 複数銘柄時: (Ticker, Field) or (Field, Ticker) の両方に対応
    cols = df.columns
    # どちらのレベルに Field がいるか判定
    lvl_has = [
        "Adj Close" in cols.get_level_values(0),
        "Adj Close" in cols.get_level_values(1),
    ]
    if lvl_has[1]:
        # (Ticker, Field) なので Field=1 を指定
        out = df.xs("Adj Close", axis=1, level=1, drop_level=True)
    elif lvl_has[0]:
        # (Field, Ticker)
        out = df.xs("Adj Close", axis=1, level=0, drop_level=True)
    else:
        # 'Adj Close' が無い場合は Close を使う
        if "Close" in cols.get_level_values(1):
            out = df.xs("Close", axis=1, level=1, drop_level=True)
        else:
            out = df.xs("Close", axis=1, level=0, drop_level=True)

    out.index = pd.to_datetime(out.index)
    return out.sort_index()

def _download_intraday(tickers: list[str], target_date: datetime) -> pd.DataFrame:
    """当日（JST）5分足: 各銘柄の『日中始値比％』を返す。空なら最大3日フォールバック。"""
    def fetch_for(date0: datetime) -> pd.DataFrame:
        frames = []
        for t in tickers:
            try:
                dfi = yf.download(t, period="1d", interval="5m", auto_adjust=False, progress=False)
            except Exception:
                dfi = pd.DataFrame()
            if dfi.empty:
                continue
            # index -> JST
            if dfi.index.tz is None:
                dfi.index = dfi.index.tz_localize("UTC")
            dfi.index = dfi.index.tz_convert(JST)
            dfi = dfi[dfi.index.date == date0.date()]
            if dfi.empty:
                continue
            price0 = float(dfi["Open"].iloc[0])
            pct = (dfi["Close"] / price0 - 1.0) * 100.0
            frames.append(pct.rename(t))
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, axis=1).sort_index()

    df = fetch_for(target_date)
    if df.empty:
        for k in range(1, 4):
            prev = target_date - timedelta(days=k)
            df = fetch_for(prev)
            if not df.empty:
                break
    return df  # columns=tickers, values=% vs open

def build_levels_eq(daily: pd.DataFrame, base_level: float) -> pd.Series:
    """等金額：初期値で正規化→平均→base_levelを掛ける"""
    if daily.empty:
        return pd.Series(dtype=float, name="level")
    base = daily.ffill().bfill().iloc[0]
    norm = daily.ffill().bfill().div(base)
    mean = norm.mean(axis=1)
    return (mean * base_level).rename("level")

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    conf = json.loads(CONF.read_text(encoding="utf-8"))

    tickers = conf["tickers"]
    base_date = conf["base_date"]
    base_level = float(conf.get("base_level", 1000.0))

    # ---- 長期レベル算出
    daily = _download_daily(tickers, start=base_date)
    if not daily.empty:
        daily = daily[daily.index >= pd.to_datetime(base_date)]
    levels = build_levels_eq(daily, base_level)
    (OUT / "skytech_3_levels.csv").write_text(levels.to_csv(date_format="%Y-%m-%d"))

    # ---- Intraday（当日5分足の等金額平均％）
    today_jst = jst_now()
    iday = _download_intraday(tickers, today_jst)
    intraday = iday.mean(axis=1).rename("pct") if not iday.empty else pd.Series(dtype=float, name="pct")
    if not intraday.empty:
        intraday.index.name = "datetime_jst"
        (OUT / "skytech_3_intraday.csv").write_text(intraday.to_csv(date_format="%Y-%m-%d %H:%M"))
        pct_now = float(np.round(intraday.iloc[-1], 2))
    else:
        pct_now = 0.0

    last_level = float(np.round(levels.iloc[-1], 2)) if not levels.empty else None
    stats = {
        "key": conf["key"],
        "pct_intraday": pct_now,
        "updated_at": jst_now_str(),
        "unit": "pct",
        "last_level": last_level,
        "tickers": tickers,
    }
    (OUT / "skytech_3_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    (OUT / "last_run.txt").write_text(jst_now_str())

    post_text = f"""【SKYTECH-3｜スカイテック指数】
本日: {pct_now:+.2f}%
指数: {last_level if last_level is not None else 'N/A'}
構成: 6232/218A/278A
#桜Index #SkyTech"""
    (OUT / "skytech_3_post_intraday.txt").write_text(post_text)
    (OUT / "post_intraday.txt").write_text(post_text)  # 互換

if __name__ == "__main__":
    main()
