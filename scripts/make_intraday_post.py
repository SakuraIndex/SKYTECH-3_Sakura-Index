# scripts/make_intraday_post.py
from pathlib import Path
import json

OUT = Path("docs/outputs")
stats = json.loads((OUT / "skytech_3_stats.json").read_text(encoding="utf-8"))
pct = stats.get("pct_intraday", 0.0)
codes = stats.get("tickers", [])
lines = [
    "【SKYTECH-3｜スカイテック指数】",
    f"本日：{pct:+.2f}%",
    "指数：None",
    f"構成：{'/'.join(codes)}",
    "#桜Index #SkyTech",
]
(OUT / "post_intraday.txt").write_text("\n".join(lines), encoding="utf-8")
