import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime, parsedate_to_datetime
import hashlib
import re
from html import escape

URL = "http://www.tt.em-net.ne.jp/~tori/waseda2026.html"
OUTPUT = Path(__file__).parent / "team_shimizu.xml"

JST = timezone(timedelta(hours=9))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    )
}

# -------------------------
# 既存RSSを読み込む
# -------------------------

old_items = {}

if OUTPUT.exists():
    try:
        tree = ET.parse(OUTPUT)

        for item in tree.getroot().findall("./channel/item"):
            guid = item.findtext("guid", "")

            if guid:
                old_items[guid] = {
                    "title": item.findtext("title", ""),
                    "link": item.findtext("link", ""),
                    "description": item.findtext("description", ""),
                    "pubDate": item.findtext("pubDate", ""),
                    "guid": guid,
                }

    except Exception:
        old_items = {}

# -------------------------
# ページ取得
# -------------------------

response = requests.get(
    URL,
    headers=HEADERS,
    timeout=30
)

response.raise_for_status()
response.encoding = response.apparent_encoding

soup = BeautifulSoup(response.text, "html.parser")

# -------------------------
# 各記録を抽出
# -------------------------

date_pattern = re.compile(
    r"■\s*(2026)/(\d{1,2})/(\d{1,2})\s*(.*)"
)

current_items = []
seen_guids = set()

# 日付で始まるテキストノードを直接探す
for text_node in soup.find_all(string=True):

    raw = str(text_node).strip()

    match = date_pattern.match(raw)

    if not match:
        continue

    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))

    title = re.sub(r"\s+", " ", raw).strip()
    title = title.lstrip("■").strip()

    # 同じ記録が入れ子構造のため複数回出ても
    # 同一タイトルなら1件だけにする
    guid_source = title

    guid = hashlib.sha256(
        guid_source.encode("utf-8")
    ).hexdigest()

    if guid in seen_guids:
        continue

    seen_guids.add(guid)

    # 記録が入っている最も近いfont要素
    parent = text_node.parent

    links = []

    if parent:
        for a in parent.find_all("a", href=True):
            href = a.get("href", "").strip()

            if "photos.google.com" in href:
                if href not in links:
                    links.append(href)

    # RSS本文
    description_parts = []

    if links:
        if len(links) == 1:
            description_parts.append(
                '<a href="{}">写真を見る</a>'.format(
                    escape(links[0], quote=True)
                )
            )

        else:
            description_parts.append(
                '<a href="{}">サイズ圧縮版写真を見る</a>'.format(
                    escape(links[0], quote=True)
                )
            )

            description_parts.append(
                '<a href="{}">フルサイズ版写真を見る</a>'.format(
                    escape(links[1], quote=True)
                )
            )

    description = "<br>".join(description_parts)

    # 写真リンクがあれば、RSSをクリックした時も写真へ
    # なければ元ページへ
    item_link = links[-1] if links else URL

    event_date = datetime(
        year,
        month,
        day,
        12,
        0,
        0,
        tzinfo=JST
    )

    current_items.append({
        "title": title,
        "link": item_link,
        "description": description,
        "pubDate": format_datetime(event_date),
        "guid": guid,
    })

# -------------------------
# 過去のRSS項目も保存
# -------------------------

all_items = []
seen = set()

for item in current_items:
    if item["guid"] not in seen:
        all_items.append(item)
        seen.add(item["guid"])

for guid, item in old_items.items():
    if guid not in seen:
        all_items.append(item)
        seen.add(guid)

# 新しい日付順
def get_date(item):
    try:
        return parsedate_to_datetime(item["pubDate"])
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)

all_items.sort(
    key=get_date,
    reverse=True
)

all_items = all_items[:300]

# -------------------------
# RSS作成
# -------------------------

rss = ET.Element(
    "rss",
    version="2.0"
)

channel = ET.SubElement(
    rss,
    "channel"
)

ET.SubElement(
    channel,
    "title"
).text = "2026 Team Shimizu"

ET.SubElement(
    channel,
    "link"
).text = URL

ET.SubElement(
    channel,
    "description"
).text = "2026 Team Shimizu 更新情報"

ET.SubElement(
    channel,
    "language"
).text = "ja"

for item in all_items:

    element = ET.SubElement(
        channel,
        "item"
    )

    ET.SubElement(
        element,
        "title"
    ).text = item["title"]

    ET.SubElement(
        element,
        "link"
    ).text = item["link"]

    ET.SubElement(
        element,
        "description"
    ).text = item["description"]

    ET.SubElement(
        element,
        "pubDate"
    ).text = item["pubDate"]

    guid_element = ET.SubElement(
        element,
        "guid"
    )

    guid_element.set(
        "isPermaLink",
        "false"
    )

    guid_element.text = item["guid"]

tree = ET.ElementTree(rss)
ET.indent(tree, space="  ")

tree.write(
    OUTPUT,
    encoding="utf-8",
    xml_declaration=True
)

# -------------------------
# 結果表示
# -------------------------

print("RSS作成成功")
print("今回取得:", len(current_items), "件")
print("RSS保存件数:", len(all_items), "件")
print("保存先:", OUTPUT)

print()
print("最新10件:")

for item in current_items[:10]:
    print("・", item["title"])