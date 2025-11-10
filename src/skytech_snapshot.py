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

def jst_now():
    return datetime.now(JST)

def jst_now_str():
    return jst_now().strftime("%Y/%m/%d %H:%M (JST)")

def _download_daily(tickers: list[str], start: str = "2023-01-01") -> pd.DataFrame:
    """日足のAdj Close（等金額正規化用）"""
    df = yf.download(tickers, start=start, interval="1d", group_by="ticker", auto_adjust=False, progress=False)
    # yfinance の列構造を平坦化
    if isinstance(df.columns, pd.MultiIndex):
        df = df.stack(0)  # -> (Date, Ticker, Field)
        df = df.reset_index()
        df = df.pivot_table(index="Date", columns="level_1", values="Adj Close")
    else:
        # 1銘柄時
        df = df[["Adj Close"]].rename(columns={"Adj Close": tickers[0]})
    df.index = pd.to_datetime(df.index)
    return df.sort_index()

def _download_intraday(tickers: list[str], target_date: datetime) -> pd.DataFrame:
    """
    当日（JST）の5分足を取得し、各銘柄の日中始値に対する変化率(%)を算出。
    空なら直近営業日にフォールバック。
    """
    def fetch_for(date0: datetime) -> pd.DataFrame:
        # yfinance はローカルTZで period="1d" 取得 → 全ティッカーまとめては難しいので個別取得＆結合
        frames = []
        for t in tickers:
            try:
                df = yf.download(t, period="1d", interval="5m", auto_adjust=False, progress=False)
            except Exception:
                df = pd.DataFrame()
            if df.empty:
                continue
            df.index = df.index.tz_localize("UTC").tz_convert(JST)
            df = df[(df.index.date == date0.date())]
            if df.empty:
                continue
            price0 = df["Open"].iloc[0]
            pct = (df["Close"] / float(price0) - 1.0) * 100.0
            frames.append(pct.rename(t))
        if not frames:
            return pd.DataFrame()
        mat = pd.concat(frames, axis=1).sort_index()
        return mat

    df = fetch_for(target_date)
    if df.empty:
        # 前営業日へフォールバック（最大3日さかのぼり）
        for k in range(1, 4):
            prev = target_date - timedelta(days=k)
            df = fetch_for(prev)
            if not df.empty:
                break
    return df  # columns = tickers, values = pct vs open

def build_levels_eq(daily: pd.DataFrame, base_level: float) -> pd.Series:
    # 等金額：各列を初期値で正規化→平均→ベースレベルを掛ける
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

    # 1) 長期（レベル時系列）
    daily = _download_daily(tickers, start=base_date)
    # base_date 以降でスライス（存在しなければ全期間）
    if not daily.empty:
        daily = daily[daily.index >= pd.to_datetime(base_date)]
    levels = build_levels_eq(daily, base_level)
    (OUT / "skytech_3_levels.csv").write_text(levels.to_csv(date_format="%Y-%m-%d"))

    # 2) Intraday（当日5分足ベースの等金額％変化）
    today_jst = jst_now()
    iday = _download_intraday(tickers, today_jst)  # % vs open per ticker
    intraday = iday.mean(axis=1).rename("pct") if not iday.empty else pd.Series(dtype=float, name="pct")
    if not intraday.empty:
        intraday.index.name = "datetime_jst"
        (OUT / "skytech_3_intraday.csv").write_text(intraday.to_csv(date_format="%Y-%m-%d %H:%M"))
        pct_now = float(np.round(intraday.iloc[-1], 2))
    else:
        pct_now = 0.0

    # 3) 統計＋ポスト文
    last_level = float(np.round(levels.iloc[-1], 2)) if not levels.empty else None
    stats = {
        "key": conf["key"],
        "pct_intraday": pct_now,
        "updated_at": jst_now_str(),
        "unit": "pct",
        "last_level": last_level,
        "tickers": tickers
    }
    (OUT / "skytech_3_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    (OUT / "last_run.txt").write_text(jst_now_str())

    post_text = f"""【SKYTECH-3｜スカイテック指数】
本日: {pct_now:+.2f}%
指数: {last_level if last_level is not None else 'N/A'}
構成: 6232/218A/278A
#桜Index #SkyTech"""
    (OUT / "skytech_3_post_intraday.txt").write_text(post_text)

    # 旧互換名（indexサイト側の拾い用に念のため）
    (OUT / "post_intraday.txt").write_text(post_text)

if __name__ == "__main__":
    main()
