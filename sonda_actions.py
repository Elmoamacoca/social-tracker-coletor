# -*- coding: utf-8 -*-
"""Sonda que roda dentro do GitHub Actions: por qual porta o Instagram deixa entrar?

O QUE JA' SE SABE. O endpoint de perfil devolveu **429** para o endereco da Azure na
primeira execucao. Faz sentido: os enderecos do Actions sao os mais usados do mundo para
raspagem, e o Instagram ja' os conhece.

Mas 429 naquela porta nao quer dizer 429 em todas. Esta sonda bate em quatro portas
diferentes do mesmo Instagram e diz qual respondeu, para o coletor passar a usar a que
funciona em vez da que eu escolhi primeiro.
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
ALVO = os.environ.get("ALVO", "nasa")


def bater(nome, url, cabecalho):
    t0 = time.time()
    req = urllib.request.Request(url, headers=cabecalho)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            corpo = r.read().decode("utf-8", "ignore")
            status = r.status
    except urllib.error.HTTPError as e:
        corpo, status = e.read().decode("utf-8", "ignore")[:300], e.code
    except Exception as e:
        print(f"  {nome:<16} EXCECAO {type(e).__name__}")
        return
    seg = None
    m = re.search(r'"edge_followed_by":\{"count":(\d+)', corpo)
    if m:
        seg = int(m.group(1))
    else:
        # A pagina publica traz o numero na descricao, no formato
        # "104M Followers, 78 Following, 4,206 Posts".
        m2 = re.search(r'([\d.,KMB]+)\s+Followers', corpo)
        if m2:
            seg = m2.group(1)
    print(f"  {nome:<16} status={status:<5} {len(corpo)//1024:>4} KB  "
          f"seguidores={seg if seg is not None else 'nenhum'}  "
          f"{time.time()-t0:.1f}s")


print("endereço de saída desta máquina:")
try:
    with urllib.request.urlopen("https://api.ipify.org", timeout=20) as r:
        print("  ", r.read().decode())
except Exception as e:
    print("  não deu:", type(e).__name__)

print(f"\nbatendo nas portas, alvo @{ALVO}:")

bater("api perfil", f"https://www.instagram.com/api/v1/users/web_profile_info/"
                    f"?username={urllib.parse.quote(ALVO)}",
      {"x-ig-app-id": "936619743392459", "User-Agent": NAVEGADOR, "Accept": "*/*",
       "X-Requested-With": "XMLHttpRequest"})
time.sleep(6)

bater("html perfil", f"https://www.instagram.com/{urllib.parse.quote(ALVO)}/",
      {"User-Agent": NAVEGADOR,
       "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
       "Accept-Language": "en-US,en;q=0.9"})
time.sleep(6)

bater("html sem barra", f"https://www.instagram.com/{urllib.parse.quote(ALVO)}",
      {"User-Agent": NAVEGADOR, "Accept": "text/html,*/*;q=0.8"})
time.sleep(6)

# O mesmo endpoint, mas com a assinatura de aplicativo de celular. E' outro cliente aos
# olhos do Instagram, e as vezes outro balde.
bater("api celular", f"https://i.instagram.com/api/v1/users/web_profile_info/"
                     f"?username={urllib.parse.quote(ALVO)}",
      {"x-ig-app-id": "936619743392459",
       "User-Agent": "Instagram 219.0.0.12.117 Android",
       "Accept": "*/*"})
