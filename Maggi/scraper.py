#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robô que acessa o site do Maggi Consórcios, lê as assembleias realizadas e
calcula a média do LANCE LIVRE contemplado dos últimos 3 meses de cada grupo
(excluindo os lances fixos de cada grupo). Gera/atualiza o medias.json.

Robustez:
- Tenta cada requisição várias vezes (o site às vezes bloqueia acessos automáticos).
- NUNCA apaga um valor bom: se uma rodada não conseguir os dados de um grupo,
  mantém o valor da rodada anterior (lê o medias.json existente).
- Se não conseguir NENHUM dado novo, não sobrescreve o arquivo.

Roda pela GitHub Action (ver .github/workflows). Usa só a biblioteca padrão.
"""
import json, re, time, datetime, urllib.request, urllib.error

BASE = "https://www.consorciomaggi.com.br"

# Grupos do simulador e os percentuais de LANCE FIXO a excluir da média.
GRUPOS = {
    "2014": {"fixo": [25, 35]},
    "2015": {"fixo": [25]},
    "2016": {"fixo": [20]},
    "2017": {"fixo": [20, 30]},
    "2018": {"fixo": [25]},
    "2019": {"fixo": [25, 35]},
    "2020": {"fixo": [25, 35]},
    "634":  {"fixo": [25, 30]},
    "644":  {"fixo": []},
    "8000": {"fixo": []},
    "755":  {"fixo": [25, 35]},
}

OBS_SEM_LIVRE = "Sem contemplação por lance livre nos últimos resultados disponíveis."

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


def pad4(g):
    g = str(g).strip()
    return g if len(g) >= 4 else g.rjust(4, "0")


def get(url, tentativas=4, timeout=30):
    """GET com retries e backoff. Retorna o HTML ou None."""
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            print("  tentativa {} falhou em {}: {}".format(i + 1, url, e))
            time.sleep(2 * (i + 1))
    return None


def datas_do_site():
    """Lê o mapa grupo -> [datas recentes] embutido na página /assembleia."""
    html = get(BASE + "/assembleia")
    if not html:
        return {}
    mapa = {}
    for m in re.finditer(r'group\\?"\s*:\s*\\?"(\d+)\\?"', html):
        g = m.group(1)
        trecho = html[m.end(): m.end() + 240]
        ds = re.findall(r"(\d{4}-\d{2}-\d{2})", trecho)
        if g not in mapa:
            mapa[g] = ds[:3]
    return mapa


def lances_da_pagina(html):
    return [float(x) for x in re.findall(r"Lance\s*</td>\s*<td[^>]*>\s*([\d.]+)", html or "")]


def media_grupo(g, fixo, datas):
    fixoset = set(float(f) for f in fixo)
    vals = []
    usadas = []
    por_mes = []
    for d in datas[:3]:
        url = "{}/assembleia/resultado/{}/{}".format(BASE, pad4(g), d)
        html = get(url)
        if html is None:
            continue
        linha = [n for n in lances_da_pagina(html) if n not in fixoset]
        if linha:
            vals.extend(linha)
            usadas.append(d)
            por_mes.append({"data": d, "media": round(sum(linha) / len(linha), 2), "n": len(linha)})
        time.sleep(0.4)  # gentileza para não tomar bloqueio
    if not vals:
        return None, 0, usadas, por_mes
    return round(sum(vals) / len(vals), 2), len(vals), usadas, por_mes


def carregar_antigo():
    try:
        with open("medias.json", encoding="utf-8") as f:
            return json.load(f).get("grupos", {})
    except Exception:
        return {}


def main():
    antigo = carregar_antigo()
    site = datas_do_site()
    if not site:
        print("Não consegui ler as datas no site (possível bloqueio temporário). "
              "Mantendo 
