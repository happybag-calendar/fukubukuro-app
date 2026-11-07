# -*- coding: utf-8 -*-
"""福袋カレンダー(happy-bag.biz)のトップページを読み取って、アプリ用のデータ(calendar_data.js)を作ります。"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent
URL = "https://happy-bag.biz/"
OUT = BASE / "calendar_data.js"
STATUS_WORDS = ["速報", "予告", "更新", "変更", "延期", "中止", "終了", "完売", "抽選", "先着", "人気"]


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


def guess_year(month, today):
    y = today.year
    if month <= 3 and today.month >= 10:
        y += 1
    return y


def parse(html, today):
    soup = BeautifulSoup(html, "html.parser")
    start = None
    for h in soup.find_all(["h4", "h2"]):
        if "福袋の日程表" in h.get_text():
            start = h
            break
    if start is None:
        raise RuntimeError("「福袋の日程表」が見つかりませんでした。ページの作りが変わった可能性があります。")
    month = day = None
    entries, seen = [], set()
    for el in start.find_next_siblings():
        if el.name in ("h4", "h2"):
            break   # 次の見出し(「本日近辺の日程表」)に来たら終わり
        if el.name != "div":
            continue
        text = el.get_text(" ", strip=True)
        m = re.fullmatch(r"(\d{1,2})月", text)
        if m:
            month, day = int(m.group(1)), None
            continue
        d = re.fullmatch(r"(\d{1,2})日(?:[（(].*?[）)])?", text)
        if d and month:
            day = int(d.group(1))
            continue
        if not (month and day):
            continue
        first = el.find("p")
        head = first.get_text("", strip=True) if first else ""
        genres = re.findall(r"【([^】]+)】", head)
        if not genres:
            continue
        # お店のリンク: 福袋カレンダーの記事ページ(entry○○.html)があればそれ。
        # 無くて、お店のHPへ直接リンクしている行も、拾う(アプリでは、福袋カレンダーのトップへ案内する)
        link = el.find("a", href=re.compile(r"entry\d+\.html"))
        direct = link is None
        if direct:
            link = el.find("a", href=True)
        shop = link.get_text(strip=True) if link is not None else ""
        if not shop:   # リンクの文字が無いときは、行の文章から、お店の名前を取り出す
            shop = re.sub(r"【[^】]*】", "", head)
            shop = re.sub(r"\d{1,2}時(?:\d{1,2}分)?.*$", "", shop).strip()
        if not shop:
            continue
        after = head.split(shop, 1)[-1] if shop in head else ""
        tm = re.search(r"(\d{1,2})時(?:(\d{1,2})分)?", after)
        time = f"{int(tm.group(1))}:{int(tm.group(2) or 0):02d}" if tm else ""
        tags = [w for w in STATUS_WORDS if w in after]
        if "人気" in el.get_text() and "人気" not in tags:   # 「人気」は、お店の欄のどこかに書いてあれば印にする
            tags.append("人気")
        for w in list(genres):          # 【予告】のように、ジャンルではなく印として使われているものは印へ
            if w in STATUS_WORDS:
                genres.remove(w)
                if w not in tags:
                    tags.append(w)
        if not genres:   # ジャンルが無く【予告】だけのものは、まだ販売前なので「予告」に分ける
            genres = ["予告"] if "予告" in tags else ["その他"]
        href = "#4" if direct else link["href"].replace("./", "")   # 直接リンクの行は、お店のHPではなく、福袋カレンダーの日程へ
        y = guess_year(month, today)
        item = {"date": f"{y}-{month:02d}-{day:02d}", "genres": genres, "shop": shop,
                "time": time, "tags": tags, "link": href}
        k = (item["date"], item["shop"], item["time"])
        if k in seen:
            continue
        seen.add(k)
        entries.append(item)
    return entries


def main():
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    entries = parse(load_html(), today)
    if len(entries) < 20:
        raise RuntimeError(f"読み取れた件数が少なすぎます({len(entries)}件)。ページの作りが変わった可能性があります。")
    jst = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    now = jst.strftime("%Y-%m-%d %H:%M")
    changed, same = now, False
    if OUT.exists():   # 中身が前回と同じなら、「日程が変わった日時」は前のまま、「最後に確認した日時」だけ新しくする
        try:
            old = OUT.read_text(encoding="utf-8")
            old = json.loads(old[old.index("{"):old.rindex("}") + 1])
            if old.get("entries") == entries:
                changed, same = old.get("updated", now), True
        except Exception:
            pass
    # updated = 日程が変わった日時 / checked = 最後に確認した日時(毎回新しくなる)
    payload = {"updated": changed, "checked": now, "entries": entries}
    OUT.write_text("window.CAL_DATA = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    if same:
        print(f"前回から変わりありません({len(entries)} 件)。確認の日時だけ更新しました。")
        return entries
    days = len({e["date"] for e in entries})
    print(f"読み取れました: {len(entries)} 件 / {days} 日分  →  {OUT.name}")
    return entries


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("うまくいきませんでした:", e)
        sys.exit(1)
