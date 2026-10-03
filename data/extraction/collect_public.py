"""Bounded fixture acquisition from official nursery pages, operator only.

Captures short factual or explicit missing-value snippets, never private cases.
It deliberately does not invent opening hours from office contact hours.
"""
import json
import re
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin
import httpx
from api.importer import fetch_public


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href = None
        self.label = ""
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.label = ""
    def handle_data(self, data):
        if self.href:
            self.label += data
    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            if "żłobek" in self.label.lower():
                self.links.append((self.label.strip(), self.href))
            self.href = None


def main():
    index = "https://bip.krakow.pl/?dok_id=14269"
    parser = Links()
    parser.feed(httpx.get(index, timeout=20).text)
    links = [(name, urljoin(index, url)) for name, url in parser.links if url.startswith("?") or "bip.krakow.pl" in url]
    out = Path(__file__).parent / "public-pages.json"
    documents = []
    for name, url in links[:25]:
        try:
            doc = fetch_public(url)
            documents.append({**doc, "label": name})
            print(name, len(doc["text"]), flush=True)
        except Exception as exc:
            print(name, type(exc).__name__, flush=True)
    # Acquisition evidence is private build material, with only short labelled
    # factual snippets promoted to the distributable fixture corpus.
    out.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
