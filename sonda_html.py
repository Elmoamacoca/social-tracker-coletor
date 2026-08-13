# -*- coding: utf-8 -*-
"""O HTML publico do perfil carrega numero? E' a porta que respondeu 200 no Actions."""
import os, re, urllib.request

NAV = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
alvo = os.environ.get("ALVO", "nasa")
req = urllib.request.Request(f"https://www.instagram.com/{alvo}/", headers={
    "User-Agent": NAV,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9"})
with urllib.request.urlopen(req, timeout=40) as r:
    h = r.read().decode("utf-8", "ignore")
print("tamanho:", len(h) // 1024, "KB")

for nome, padrao in [
    ("og:description", r'property="og:description" content="([^"]{0,200})"'),
    ("meta description", r'name="description" content="([^"]{0,200})"'),
    ("edge_followed_by", r'"edge_followed_by":\{"count":(\d+)\}'),
    ("follower_count", r'"follower_count":(\d+)'),
    ("titulo", r"<title>([^<]{0,120})</title>"),
    ("profile_pic", r'"profile_pic_url[^"]*":"([^"]{0,80})'),
    ("media_count", r'"media_count":(\d+)'),
    ("shortcode", r'"shortcode":"([A-Za-z0-9_-]{5,20})"'),
]:
    m = re.search(padrao, h)
    print(f"  {nome:<18}", (m.group(1)[:120] if m else "não achou"))

print("\ntem 'login' no titulo?", "login" in h[:4000].lower())
print("trecho do inicio:", re.sub(r"\s+", " ", h[:300]))
