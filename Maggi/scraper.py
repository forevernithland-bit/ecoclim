#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robô que acessa o site do Maggi Consórcios, lê as assembleias realizadas
e calcula a média do LANCE LIVRE contemplado dos últimos 3 meses de cada
grupo (excluindo os lances fixos de cada grupo). Gera/atualiza o medias.json.

Roda automaticamente pela GitHub Action (ver .github/workflows). Usa só a
biblioteca padrão do Python (sem instalar nada).
"""
import json, re, datetime, urllib.request

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

# Observação exibida quando não há lance livre disponível no período.
OBS_SEM_LIVRE = "Sem contemplação por lance livre nos últimos resultados disponíveis."


def pad4(g):
    g = str(g).strip()
    return g if len(g) >= 4 else g.rjust(4, "0")


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; MaggiSimuladorBot/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def datas_do_site():
    """Lê o mapa grupo -> [datas recentes] embutido na página /assembleia."""
    try:
        html = get(BASE + "/assembleia")
    except Exception as e:
        print("Falha ao ler /assembleia:", e)
        return {}
    mapa = {}
    # A página traz algo como: \"group\":\"0619\",\"dates\":[\"2026-06-24T00:00:00\",...]
    for m in re.finditer(r'group\\?"\s*:\s*\\?"(\d+)\\?"', html):
        g = m.group(1)
        trecho = html[m.end(): m.end() + 240]
        ds = re.findall(r"(\d{4}-\d{2}-\d{2})", trecho)
        if g not in mapa:
            mapa[g] = ds[:3]
    return mapa


def lances_da_pagina(html):
    """Extrai os percentuais das linhas 'Lance' da tabela de resultado."""
    return [float(x) for x in re.findall(r"Lance\s*</td>\s*<td[^>]*>\s*([\d.]+)", html)]


def media_grupo(g, fixo, datas):
    fixoset = set(float(f) for f in fixo)
    vals = []
    usadas = []
    por_mes = []   # média do lance livre em cada assembleia (mês a mês)
    for d in datas[:3]:
        url = "{}/assembleia/resultado/{}/{}".format(BASE, pad4(g), d)
        try:
            html = get(url)
        except Exception as e:
            print("  falha", url, e)
            continue
        linha = [n for n in lances_da_pagina(html) if n not in fixoset]
        if linha:
            vals.extend(linha)
            usadas.append(d)
            por_mes.append({"data": d, "media": round(sum(linha) / len(linha), 2), "n": len(linha)})
    if not vals:
        return None, 0, usadas, por_mes
    return round(sum(vals) / len(vals), 2), len(vals), usadas, por_mes


def main():
    site = datas_do_site()
    saida = {
        "atualizado_em": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "fonte": BASE + "/assembleia",
        "grupos": {},
    }
    for g, cfg in GRUPOS.items():
        datas = site.get(pad4(g)) or site.get(g) or []
        media, n, usadas, por_mes = media_grupo(g, cfg["fixo"], datas)
        item = {"media": media, "n": n, "datas": usadas, "por_mes": por_mes}
        if media is None:
            item["obs"] = OBS_SEM_LIVRE
        saida["grupos"][g] = item
        print("Grupo {:>5}: media={} (n={}) por_mes={}".format(g, media, n, por_mes))

    with open("medias.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)
    print("medias.json atualizado.")


if __name__ == "__main__":
    main()
