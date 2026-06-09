import requests
from bs4 import BeautifulSoup
from pathlib import Path
import time

BASE_URL = "https://www.myinstants.com"
INDEX_URL = f"{BASE_URL}/en/index/vn/"

def parse_sounds_from_html(html: str, base_url: str = BASE_URL) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    sounds = []
    for instant in soup.select(".instant"):
        name_tag = instant.select_one(".instant-link")
        btn = instant.select_one("[data-url]")
        if not name_tag or not btn:
            continue
        name = name_tag.get_text(strip=True)
        mp3_url = btn.get("data-url", "")
        if mp3_url and not mp3_url.startswith("http"):
            mp3_url = base_url + mp3_url
        page_url = name_tag.get("href", "")
        if page_url and not page_url.startswith("http"):
            page_url = base_url + page_url
        sounds.append({"name": name, "mp3_url": mp3_url, "source_url": page_url})
    return sounds

def crawl_myinstants(max_pages: int = 10) -> list[dict]:
    all_sounds = []
    for page in range(1, max_pages + 1):
        url = f"{INDEX_URL}?page={page}"
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            sounds = parse_sounds_from_html(resp.text)
            if not sounds:
                break
            all_sounds.extend(sounds)
            time.sleep(1)  # polite crawling
        except Exception as e:
            print(f"Error on page {page}: {e}")
            break
    return all_sounds

def download_mp3(mp3_url: str, dest_dir: str, filename: str) -> str:
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    dest = str(Path(dest_dir) / filename)
    resp = requests.get(mp3_url, timeout=15)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)
    return dest
