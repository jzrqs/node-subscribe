import base64
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
import yaml
from bs4 import BeautifulSoup


BASE = "https://clashverge.me"
CATEGORY_URL = "https://clashverge.me/free-node/"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def fetch_text(url: str, timeout: int = 20) -> str:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def find_latest_article() -> str:
    html = fetch_text(CATEGORY_URL)
    soup = BeautifulSoup(html, "html.parser")

    candidates = []

    for a in soup.find_all("a", href=True):
        href = urljoin(BASE, a["href"])
        title = a.get_text(" ", strip=True)

        if "/free-node/" not in href:
            continue

        if not href.endswith(".htm"):
            continue

        title_hit = any(k.lower() in title.lower() for k in [
            "v2ray", "clash", "shadowrocket", "ssr", "免费节点", "订阅链接", "node"
        ])

        href_hit = any(k in href.lower() for k in [
            "v2ray", "clash", "subscribe", "node", "free"
        ])

        if title_hit or href_hit:
            candidates.append(href)

    candidates = list(dict.fromkeys(candidates))

    if not candidates:
        raise RuntimeError("没有在 free-node 分类页找到每日节点文章")

    return candidates[0]


def extract_subscription_links(article_url: str):
    html = fetch_text(article_url)

    links = re.findall(
        r"https://node\.clashverge\.me/uploads/\d{4}/\d{2}/[^\s\"'<>()]+",
        html
    )

    v2ray_links = []
    clash_links = []
    singbox_links = []

    for link in links:
        link = link.strip()

        if link.endswith(".txt"):
            v2ray_links.append(link)
        elif link.endswith(".yaml") or link.endswith(".yml"):
            clash_links.append(link)
        elif link.endswith(".json"):
            singbox_links.append(link)

    return {
        "article": article_url,
        "v2ray": list(dict.fromkeys(v2ray_links)),
        "clash": list(dict.fromkeys(clash_links)),
        "singbox": list(dict.fromkeys(singbox_links)),
    }


def merge_v2ray_txt(urls):
    all_nodes = []

    for url in urls:
        try:
            content = fetch_text(url).strip()

            try:
                padded = content + "=" * (-len(content) % 4)
                decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
            except Exception:
                decoded = content

            for line in decoded.splitlines():
                line = line.strip()
                if line.startswith(("vmess://", "vless://", "trojan://", "ss://", "ssr://")):
                    all_nodes.append(line)

        except Exception as e:
            print(f"[WARN] failed v2ray source {url}: {e}")

    all_nodes = list(dict.fromkeys(all_nodes))
    merged_plain = "\n".join(all_nodes)
    merged_b64 = base64.b64encode(merged_plain.encode("utf-8")).decode("utf-8")

    Path("v2ray.txt").write_text(merged_b64, encoding="utf-8")
    Path("v2ray_plain.txt").write_text(merged_plain, encoding="utf-8")


def merge_clash_yaml(urls):
    proxies = []
    proxy_names = []

    for url in urls:
        try:
            content = fetch_text(url)
            data = yaml.safe_load(content)

            if not isinstance(data, dict):
                continue

            for p in data.get("proxies", []) or []:
                name = p.get("name")
                if name and name not in proxy_names:
                    proxies.append(p)
                    proxy_names.append(name)

        except Exception as e:
            print(f"[WARN] failed clash source {url}: {e}")

    config = {
        "port": 7890,
        "socks-port": 7891,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "proxies": proxies,
        "proxy-groups": [
            {
                "name": "AUTO",
                "type": "url-test",
                "proxies": proxy_names,
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300
            },
            {
                "name": "PROXY",
                "type": "select",
                "proxies": ["AUTO"] + proxy_names
            }
        ],
        "rules": [
            "MATCH,PROXY"
        ]
    }

    Path("clash.yaml").write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8"
    )


def merge_singbox_json(urls):
    for url in urls:
        try:
            content = fetch_text(url)
            data = json.loads(content)
            Path("singbox.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            return
        except Exception as e:
            print(f"[WARN] failed singbox source {url}: {e}")

    Path("singbox.json").write_text("{}", encoding="utf-8")


def main():
    article = find_latest_article()
    print(f"[INFO] latest article: {article}")

    links = extract_subscription_links(article)
    print(json.dumps(links, ensure_ascii=False, indent=2))

    merge_v2ray_txt(links["v2ray"])
    merge_clash_yaml(links["clash"])
    merge_singbox_json(links["singbox"])

    Path("source.json").write_text(
        json.dumps(links, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


if __name__ == "__main__":
    main()
