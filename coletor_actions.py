# -*- coding: utf-8 -*-
"""Coletor que roda no GitHub Actions, para multiplicar os enderecos de saida.

POR QUE ELE EXISTE, e o numero que obriga.

O Worker da Cloudflare responde, mas sai **sempre pelo mesmo endereco**, e o Instagram
nao trabalha com balde que enche sozinho: ele penaliza o endereco por reputacao. Medido
em 13/08, com o endereco ja' usado no dia:

    intervalo de 20 s  ->   0 de 12 passaram
    intervalo de 40 s  ->   2 de 10 passaram, 18 leituras por hora
    40 minutos de gatilho ->  0 leituras, 22 recusas

Dezoito leituras por hora sustentam duzentas contas com duas leituras por dia. Nao
sustentam mil, e nenhuma esperteza de ritmo muda isso: **um endereco tem um teto**.

O GitHub Actions resolve pela unica via que resta, que e' ter muitos enderecos: cada
execucao roda numa maquina nova, com endereco novo. Em repositorio publico o tempo de
execucao e' ilimitado e gratuito, e o gatilho de hora e' nativo.

O QUE ESTE ARQUIVO **NAO** CARREGA: nada seu. A lista de contas mora no armazenamento da
Cloudflare e chega aqui por credencial guardada nos segredos do repositorio. Quem ler o
repositorio publico ve' um coletor generico e mais nada.
"""
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

CONTA = os.environ.get("CF_CONTA", "")
TOKEN = os.environ.get("CF_TOKEN", "")
KV = os.environ.get("CF_KV", "")
API = "https://api.cloudflare.com/client/v4"

# Quantos perfis por execucao e com que intervalo. Como o endereco e' novo a cada
# execucao, aqui a folga e' outra: o limite vira o tempo do proprio trabalho.
QUANTOS = int(os.environ.get("QUANTOS", "25"))
INTERVALO = (14, 22)   # segundos entre um perfil e o proximo, sorteado

CAB = {
    "x-ig-app-id": "936619743392459",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
}
PERFIL = "https://www.instagram.com/api/v1/users/web_profile_info/?username="


def cf(metodo, caminho, corpo=None, tipo="application/json", bruto=False):
    req = urllib.request.Request(f"{API}{caminho}", data=corpo, method=metodo)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    if corpo is not None and tipo:
        req.add_header("Content-Type", tipo)
    with urllib.request.urlopen(req, timeout=60) as r:
        dado = r.read().decode("utf-8", "ignore")
        return dado if bruto else json.loads(dado)


def ler_chave(chave):
    try:
        return cf("GET", f"/accounts/{CONTA}/storage/kv/namespaces/{KV}/values/"
                         f"{urllib.parse.quote(chave)}", bruto=True)
    except urllib.error.HTTPError:
        return ""


def escrever_chave(chave, valor, ttl=None):
    limite = "----stkv"
    partes = [f'--{limite}\r\nContent-Disposition: form-data; name="value"\r\n\r\n'
              f"{valor}\r\n",
              f'--{limite}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'
              f"{{}}\r\n", f"--{limite}--\r\n"]
    q = f"?expiration_ttl={ttl}" if ttl else ""
    return cf("PUT", f"/accounts/{CONTA}/storage/kv/namespaces/{KV}/values/"
                     f"{urllib.parse.quote(chave)}{q}",
              "".join(partes).encode("utf-8"),
              f"multipart/form-data; boundary={limite}")


def formato_de(p):
    if (p.get("product_type") or "").lower() == "clips":
        return "reel"
    if "Sidecar" in (p.get("__typename") or ""):
        return "carrossel"
    return "reel" if p.get("is_video") else "feed"


def extrair(u):
    posts = []
    for e in (u.get("edge_owner_to_timeline_media") or {}).get("edges", []):
        p = e.get("node") or {}
        cap = ((p.get("edge_media_to_caption") or {}).get("edges") or [{}])[0]
        posts.append({
            "shortcode": p.get("shortcode"),
            "publicado": p.get("taken_at_timestamp"),
            "tipo": (p.get("__typename") or "").replace("Graph", ""),
            "formato": formato_de(p),
            "legenda": ((cap.get("node") or {}).get("text") or "")[:1000],
            "curtidas": (p.get("edge_media_preview_like")
                         or p.get("edge_liked_by") or {}).get("count") or 0,
            "comentarios": (p.get("edge_media_to_comment")
                            or p.get("edge_media_preview_comment") or {}).get("count") or 0,
            "views": max(p.get("video_view_count") or 0, p.get("video_play_count") or 0),
            "url_midia": p.get("video_url") or p.get("display_url"),
            "url_capa": p.get("display_url"),
        })
    return {"username": u.get("username"), "id": u.get("id"),
            "nome": u.get("full_name") or "",
            "seguidores": (u.get("edge_followed_by") or {}).get("count"),
            "seguindo": (u.get("edge_follow") or {}).get("count"),
            "total_posts": (u.get("edge_owner_to_timeline_media") or {}).get("count"),
            "privado": bool(u.get("is_private")),
            "foto": u.get("profile_pic_url_hd") or u.get("profile_pic_url") or "",
            "posts": posts}


def coletar(perfil):
    req = urllib.request.Request(PERFIL + urllib.parse.quote(perfil), headers=CAB)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            d = json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 429):
            return {"erro": "orcamento", "status": e.code}
        if e.code == 404:
            return {"erro": "inexistente", "status": 404}
        if e.code == 400:
            return {"erro": "categoria", "status": 400}
        return {"erro": "http", "status": e.code}
    except Exception as e:
        return {"erro": "excecao", "detalhe": f"{type(e).__name__}"}
    u = (d.get("data") or {}).get("user")
    return {"dados": extrair(u)} if u else {"erro": "sem_usuario"}


def main():
    if not (CONTA and TOKEN and KV):
        print("faltam os segredos CF_CONTA, CF_TOKEN e CF_KV")
        sys.exit(1)
    contas = json.loads(ler_chave("contas") or "[]")
    if not contas:
        print("a lista de contas está vazia")
        return

    # RODIZIO PELO RELOGIO, o mesmo criterio do coletor da Cloudflare: cada execucao pega
    # o pedaco seguinte da lista, sem marcador guardado em lugar nenhum.
    passo = max(1, QUANTOS)
    inicio = (int(time.time() // 600) * passo) % len(contas)

    lote = {"em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "origem": "actions", "coletadas": [], "erros": []}
    naos = 0
    for i in range(min(QUANTOS, len(contas))):
        perfil = contas[(inicio + i) % len(contas)]
        if i:
            time.sleep(random.uniform(*INTERVALO))
        r = coletar(perfil)
        if r.get("dados"):
            lote["coletadas"].append(r["dados"])
            naos = 0
            print(f"  {perfil:<26} {r['dados']['seguidores']:>12,} seg | "
                  f"{len(r['dados']['posts'])} posts", flush=True)
        else:
            lote["erros"].append({"perfil": perfil, **r})
            print(f"  {perfil:<26} {r.get('erro')} {r.get('status', '')}", flush=True)
            if r.get("erro") == "orcamento":
                naos += 1
                # DUAS RECUSAS SEGUIDAS ENCERRAM. Esta maquina e' descartavel, mas
                # insistir depois do nao so' ensina o Instagram a lembrar dela.
                if naos >= 2:
                    lote["parou"] = "orçamento"
                    break

    if lote["coletadas"] or lote["erros"]:
        escrever_chave("lote:" + lote["em"], json.dumps(lote, ensure_ascii=False),
                       ttl=172800)
    print(f"\ncoletadas {len(lote['coletadas'])} | erros {len(lote['erros'])} | "
          f"parou: {lote.get('parou') or 'não'}")


if __name__ == "__main__":
    main()
