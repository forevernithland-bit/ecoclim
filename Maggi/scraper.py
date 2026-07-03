#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robo que acessa o site do Maggi Consorcios, le as assembleias realizadas e
calcula a media do LANCE LIVRE contemplado dos ultimos 3 meses de cada grupo
(excluindo os lances fixos de cada grupo). Gera/atualiza o medias.json.

Robustez:
- Tenta cada requisicao varias vezes (o site as vezes bloqueia acessos automaticos).
- NUNCA apaga um valor bom: se uma rodada nao conseguir os dados de um grupo,
  mantem o valor da rodada anterior (le o medias.json existente).
- Se nao conseguir NENHUM dado novo, nao sobrescreve o arquivo.

Roda pela GitHub Action. Usa so a biblioteca padrao do Python.
"""
import json, re, time, datetime, urllib.request, urllib.error

BASE = "https://www.consorciomaggi.com.br"

# Grupos do simulador e os percentuais de LANCE FIXO a excluir da media.
GRUPOS = {
    "2013": {"fixo": [25, 35]},
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

OBS_SEM_LIVRE = "Sem contemplacao por lance livre nos ultimos resultados disponiveis."

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
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
            print("  tentativa", i + 1, "falhou em", url, ":", e)
            time.sleep(2 * (i + 1))
    return None


def datas_do_site():
    """Le o mapa grupo -> [datas recentes] embutido na pagina /assembleia."""
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
        time.sleep(0.4)
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
        print("Sem datas do site (possivel bloqueio temporario). Mantendo medias.json anterior.")
        return

    grupos = {}
    algum_novo = False
    for g, cfg in GRUPOS.items():
        datas = site.get(pad4(g)) or site.get(g) or []
        media, n, usadas, por_mes = media_grupo(g, cfg["fixo"], datas)
        if media is not None:
            algum_novo = True
            grupos[g] = {"media": media, "n": n, "datas": usadas, "por_mes": por_mes}
            print("Grupo", g, "media", media, "n", n)
        else:
            ant = antigo.get(g)
            if ant and ant.get("media") is not None:
                grupos[g] = ant
                print("Grupo", g, "sem dado agora - mantido valor anterior", ant.get("media"))
            else:
                grupos[g] = {"media": None, "n": 0, "datas": usadas, "por_mes": por_mes, "obs": OBS_SEM_LIVRE}
                print("Grupo", g, "sem lance livre disponivel")

    if not algum_novo:
        print("Nenhum dado novo nesta rodada. Mantendo medias.json anterior.")
        return

    agora = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    saida = {"atualizado_em": agora, "fonte": BASE + "/assembleia", "grupos": grupos}
    with open("medias.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)
    print("medias.json atualizado.")


if __name__ == "__main__":
    main()
