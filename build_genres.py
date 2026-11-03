# -*- coding: utf-8 -*-
"""福袋カレンダーの「ジャンル一覧」(entry625.html)を読み取って、アプリ用の genres_data.js を作ります。
うまく読み取れなかったときは、今の genres_data.js をそのまま残します(アプリは壊れません)。"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent
URL = "https://happy-bag.biz/entry625.html"
OUT = BASE / "genres_data.js"
SKIP_WORDS = ("▲", "▼", "ページ", "戻る", "TOP", "トップ", "上へ", "一覧へ")


def load_html():
    if len(sys.argv) > 1:   # テスト用: 保存したHTMLを読む
        return Path(sys.argv[1]).read_text(encoding="utf-8")
    import requests
    r = requests.get(URL, timeout=30, headers={"User-Agent": "Mozilla/5.0 (compatible; HappyBagCalendarOwner)"})
    r.raise_for_status()
    raw = r.content
    for enc in ("utf-8", "cp932", "euc-jp"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp932", errors="replace")


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    genres, seen = [], set()
    for a in soup.find_all("a", href=True):
        m = re.search(r"#(\d+)$", a["href"].strip())
        if not m:
            continue
        path = a["href"].split("#")[0]
        if path and "entry625" not in path:      # 別のページへのリンクは対象外
            continue
        name = re.sub(r"\s+", "", a.get_text(strip=True))
        if not name or len(name) > 20 or any(w in name for w in SKIP_WORDS):
            continue
        num = int(m.group(1))
        if num in seen:
            continue
        seen.add(num)
        genres.append({"name": name, "id": num})
    return genres


def main():
    try:
        genres = parse(load_html())
    except Exception as e:      # 読み取れなくても、今のファイルを残して終わる
        print("ジャンル一覧を読み取れませんでした:", e)
        return 0
    if not (15 <= len(genres) <= 60):
        print(f"ジャンルの数が想定外({len(genres)}件)なので、今のファイルを残します")
        return 0
    old = None
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8").split("=", 1)[1].rstrip().rstrip(";")).get("genres")
        except Exception:
            old = None
    if old == genres:
        print(f"ジャンルは変わっていません({len(genres)}件)")
        return 0
    payload = {"updated": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "genres": genres}
    OUT.write_text("window.GENRE_DATA = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    print(f"ジャンル一覧を更新しました({len(genres)}件)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
