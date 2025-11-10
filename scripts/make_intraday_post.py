from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "outputs"

def main():
    p = OUT / "skytech_3_stats.json"
    if not p.exists(): 
        return
    j = json.loads(p.read_text())
    pct = j.get("pct_intraday", 0.0)
    level = j.get("last_level", "N/A")

    text = f"""【SKYTECH-3｜スカイテック指数】
本日: {pct:+.2f}%
指数: {level}
構成: 6232/218A/278A
#桜Index #SkyTech"""
    (OUT / "skytech_3_post_intraday.txt").write_text(text)
    # 互換
    (OUT / "post_intraday.txt").write_text(text)

if __name__ == "__main__":
    main()
