"""Motor de dados e análise da aba "Ações" (Controle Financeiro). Sem Streamlit.

Fontes (todas gratuitas, sem chave):
  * Cotação e histórico de preço/dividendos: Yahoo Finance (endpoint `chart`).
    ATENÇÃO: o preço vem com atraso de ~15 min (igual ao "Cotação (Há 15 min)"
    do app do Inter) — não é tempo real tick a tick.
  * Lucro anual, quantidade de ações e setor: Dados Abertos da CVM (ver
    acoes_base.py), guardados no Supabase.

A "análise" é um conjunto de REGRAS TRANSPARENTES sobre números — cada sinal
mostra os motivos e os critérios são configuráveis. Não é recomendação de
investimento nem substitui assessor/analista credenciado (CVM).
"""
import datetime
import json
import math
import re
import statistics
import time
import urllib.request
import concurrent.futures

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}.SA?range={rng}&interval=1d&events=div%2Csplit"

CONFIG_PADRAO = {
    "yield_alvo": 6.0,          # % — base do "preço teto" (método Bazin): média de dividendos / yield alvo
    "limite_papel": 12.0,       # % máximo de um único papel na carteira (alerta)
    "limite_grupo": 30.0,       # % máximo de um grupo/setor (alerta)
    "liquidez_min": 5_000_000,  # R$ negociados por dia (média 60 pregões) mínimo para entrar no radar
    "div_anos_min": 5,          # anos (dos últimos 7) com pagamento de proventos, para entrar no radar
    "so_setores_perenes": True,
    "grupos_perenes": ["Bancos", "Seguros e Corretoras", "Energia Elétrica", "Saneamento", "Alimentos", "Bebidas",
                       "Telecomunicações", "Saúde", "Varejo e Comércio", "Financeiro (outros)", "Papel e Celulose", "Indústria", "Agro"],
}

ETFS_CONHECIDOS = {"BOVA11", "IVVB11", "SMAL11", "HASH11", "GOLD11", "BDIV11", "DIVO11", "FIND11", "MATB11", "GOVE11", "BOVV11", "XINA11", "NASD11", "SPXI11", "QBTC11", "ECOO11"}


# ----------------------------------------------------------------------------
# Classificação
# ----------------------------------------------------------------------------
def _cnpj_do_ticker(t, base):
    """CNPJ do ticker: direto, ou pelo radical de 4 letras quando ele aponta
    para uma única companhia (ex.: ALUP3 quando a CVM só lista ALUP11)."""
    tk = (base or {}).get("tickers") or {}
    if t in tk:
        return tk[t]
    raiz = {c for x, c in tk.items() if x[:4] == t[:4]}
    return next(iter(raiz)) if len(raiz) == 1 else None


def tipo_do_ticker(ticker, base):
    t = str(ticker).upper().strip()
    em_base = bool(base and _cnpj_do_ticker(t, base))
    if t in ETFS_CONHECIDOS:
        return "ETF"
    if re.fullmatch(r"[A-Z][A-Z0-9]{3}3[2-5]|[A-Z][A-Z0-9]{3}39", t):
        return "BDR"
    if em_base and t.endswith("11"):
        return "Unit"
    if t.endswith("11"):
        return "FII/Fundo"
    if em_base:
        return "Ação"
    if re.fullmatch(r"[A-Z][A-Z0-9]{3}\d{1,2}", t) and not t.endswith(("11", "12", "13")):
        return "Ação"  # ação que não achei na CVM (ex.: ticker novo) — segue como ação
    return "Outro"


def grupo_do_ticker(ticker, base, tipo=None):
    t = str(ticker).upper().strip()
    tipo = tipo or tipo_do_ticker(t, base)
    c = _cnpj_do_ticker(t, base) if base else None
    if c:
        return base["empresas"][c].get("g") or "Outros"
    return {"ETF": "ETFs", "FII/Fundo": "Fundos Imobiliários", "BDR": "BDRs (exterior)"}.get(tipo, "Outros")


def empresa_da_base(ticker, base):
    t = str(ticker).upper().strip()
    c = _cnpj_do_ticker(t, base) if base else None
    return base["empresas"][c] if c else None


def anos_lucro_seguidos(empresa, anos):
    """Exercícios SEGUIDOS com lucro > 0, do mais recente pra trás."""
    n = 0
    for a in sorted(anos, reverse=True):
        v = ((empresa or {}).get("l") or {}).get(str(a))
        if v is None or v <= 0:
            break
        n += 1
    return n


# ----------------------------------------------------------------------------
# Cotação / histórico (Yahoo)
# ----------------------------------------------------------------------------
def _get_json(url, tentativas=3):
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            ultimo = e
            time.sleep(0.6 * (i + 1))
    raise RuntimeError(str(ultimo)[:120])


def buscar_historico(ticker, anos=7):
    """Preços diários + dividendos + desdobramentos de `anos` anos. Nunca
    levanta exceção: devolve {"ticker", "erro"} quando não consegue."""
    t = str(ticker).upper().strip()
    try:
        j = _get_json(YAHOO.format(sym=t, rng=f"{anos}y"))
        r = j["chart"]["result"][0]
        meta = r["meta"]
        ts = r.get("timestamp") or []
        q = r["indicators"]["quote"][0]
        datas, fechos, vols = [], [], []
        for i, stamp in enumerate(ts):
            c = q["close"][i]
            if c is None:
                continue
            datas.append(datetime.datetime.fromtimestamp(stamp, datetime.timezone.utc).date())
            fechos.append(float(c))
            vols.append(float(q["volume"][i] or 0))
        divs = []
        for d in ((r.get("events") or {}).get("dividends") or {}).values():
            divs.append((datetime.datetime.fromtimestamp(d["date"], datetime.timezone.utc).date(), float(d["amount"])))
        divs.sort()
        splits = []
        for sp in ((r.get("events") or {}).get("splits") or {}).values():
            try:
                splits.append((datetime.datetime.fromtimestamp(sp["date"], datetime.timezone.utc).date(), float(sp["numerator"]) / float(sp["denominator"])))
            except (KeyError, ZeroDivisionError, TypeError):
                pass
        splits.sort()
        if not fechos:
            return {"ticker": t, "erro": "sem preços"}
        return {
            "ticker": t, "nome": meta.get("longName") or meta.get("shortName") or t,
            "preco": float(meta.get("regularMarketPrice") or fechos[-1]),
            "atualizado": meta.get("regularMarketTime"),
            "datas": datas, "fechos": fechos, "volumes": vols, "dividendos": divs, "splits": splits, "erro": None,
        }
    except Exception as e:  # noqa: BLE001
        return {"ticker": t, "erro": str(e)}


def buscar_varios(tickers, trabalhadores=8):
    tickers = sorted({str(t).upper().strip() for t in tickers if str(t).strip()})
    with concurrent.futures.ThreadPoolExecutor(max_workers=trabalhadores) as ex:
        res = dict(zip(tickers, ex.map(buscar_historico, tickers)))
    # uma segunda chance (sem pressa) para falhas que não sejam "não existe"
    for t, h in list(res.items()):
        if h.get("erro") and "404" not in h["erro"]:
            time.sleep(0.5)
            res[t] = buscar_historico(t)
    return res


# ----------------------------------------------------------------------------
# Métricas e sinal
# ----------------------------------------------------------------------------
GRUPOS_CICLICOS = {"Petróleo e Gás", "Mineração", "Siderurgia e Metalurgia", "Papel e Celulose", "Agro"}


def _media(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def _fator_splits(splits, depois_de):
    """Fator acumulado dos desdobramentos/bonificações ocorridos APÓS `depois_de`
    (as ações da CVM de um exercício são anteriores a eles, o preço do Yahoo não)."""
    f = 1.0
    for d, razao in splits:
        if d > depois_de:
            f *= razao
    return f


def calcular_metricas(h, base=None, cfg=None):
    cfg = {**CONFIG_PADRAO, **(cfg or {})}
    if not h or h.get("erro"):
        return {"erro": (h or {}).get("erro") or "sem dados"}
    t = h["ticker"]
    tipo = tipo_do_ticker(t, base)
    emp = empresa_da_base(t, base)
    fechos, datas, vols = h["fechos"], h["datas"], h["volumes"]
    preco = h["preco"]
    hoje = datas[-1]
    m = {"ticker": t, "nome": h.get("nome"), "tipo": tipo, "preco": preco,
         "grupo": grupo_do_ticker(t, base, tipo), "erro": None, "suspeitos": []}

    anterior = fechos[-2] if len(fechos) > 1 else preco
    m["var_dia"] = (preco / anterior - 1) if anterior else None

    ult252 = fechos[-252:]
    m["alta_52s"], m["baixa_52s"] = max(ult252), min(ult252)
    m["pos_faixa_52s"] = (preco - m["baixa_52s"]) / (m["alta_52s"] - m["baixa_52s"]) if m["alta_52s"] > m["baixa_52s"] else None
    ma200 = _media(fechos[-200:]) if len(fechos) >= 100 else None
    m["ma200"] = ma200
    m["vs_ma200"] = (preco / ma200 - 1) if ma200 else None
    cinco = fechos[-1260:]
    m["percentil_5a"] = sum(1 for x in cinco if x <= preco) / len(cinco) if len(cinco) >= 250 else None
    m["liquidez_dia"] = _media([c * v for c, v in zip(fechos[-60:], vols[-60:])])

    # --- proventos --------------------------------------------------------
    um_ano = hoje - datetime.timedelta(days=365)
    d12 = sum(v for d, v in h["dividendos"] if d > um_ano)
    m["dy_12m"] = d12 / preco if preco else None
    anos_hist = (hoje - datas[0]).days / 365
    janelas = []
    if anos_hist >= 4.5:
        for i in range(5):
            fim = hoje - datetime.timedelta(days=365 * i)
            janelas.append(sum(v for d, v in h["dividendos"] if fim - datetime.timedelta(days=365) < d <= fim))
    mediana_j = statistics.median(janelas) if janelas else 0
    m["div_medio_ano"] = mediana_j if mediana_j > 0 else None
    # só vale como "teto" se ainda paga: as 2 janelas mais recentes precisam ser positivas
    m["pagando_recente"] = bool(janelas) and janelas[0] > 0 and janelas[1] > 0
    m["teto_bazin"] = m["div_medio_ano"] / (cfg["yield_alvo"] / 100) if m["div_medio_ano"] and m["pagando_recente"] else None
    anos_cal = {d.year for d, v in h["dividendos"] if v > 0 and hoje.year - 7 <= d.year < hoje.year}
    m["anos_com_dividendo"] = len(anos_cal)

    # --- fundamentos CVM (só ações; Unit/FII/ETF/BDR ficam de fora) --------
    m["streak_lucro"] = None
    m["pl_atual"] = m["pl_mediano"] = m["pl_vs_mediano"] = m["cagr_lucro"] = None
    m["lucros"] = None
    m["ciclica"] = m["grupo"] in GRUPOS_CICLICOS
    if emp and base:
        anos = base.get("anos") or []
        m["streak_lucro"] = anos_lucro_seguidos(emp, anos)
        m["lucros"] = {a: emp["l"].get(str(a)) for a in anos}
        if tipo == "Ação":
            splits = h.get("splits") or []
            eps = {}
            for a in anos:
                l, n = emp["l"].get(str(a)), (emp.get("a") or {}).get(str(a))
                if l is not None and n:
                    # ações do exercício `a` (balanço publicado ~mar/a+1) ajustadas pelos splits posteriores
                    eps[a] = l / (n * _fator_splits(splits, datetime.date(a + 1, 3, 31)))
            ultimo = eps.get(max(eps)) if eps else None
            if ultimo and ultimo > 0:
                # a CVM não padroniza a escala das ações (unidades x milhares):
                # escolhe o fator que dá um P/L plausível (entre 1 e 300).
                k = min((f for f in (1, 1000, 0.001) if 1 <= preco * f / ultimo <= 300), key=lambda f: abs(math.log(preco * f / ultimo / 15)), default=None)
                if k:
                    m["pl_atual"] = preco * k / ultimo
                    pls = []
                    for a, e in eps.items():
                        if e <= 0:
                            continue
                        precos_ano = [c for d, c in zip(datas, fechos) if d.year == a]
                        if len(precos_ano) >= 150:
                            pls.append(_media(precos_ano) * k / e)
                    if len(pls) >= 4:
                        m["pl_mediano"] = statistics.median(pls)
                        m["pl_vs_mediano"] = m["pl_atual"] / m["pl_mediano"] - 1
                    # dado implausível -> não pontua, só avisa
                    if m["pl_atual"] < 3 or (m["pl_mediano"] and not 2 <= m["pl_mediano"] <= 80):
                        m["suspeitos"].append(f"P/L {m['pl_atual']:.1f} (mediana {m['pl_mediano'] or 0:.1f}) parece incoerente — conferir lucro/quantidade de ações")
                        m["pl_vs_mediano"] = None
        ls = [emp["l"].get(str(a)) for a in anos]
        if len(ls) >= 2 and ls[0] and ls[-1] and ls[0] > 0 and ls[-1] > 0:
            m["cagr_lucro"] = (ls[-1] / ls[0]) ** (1 / (len(ls) - 1)) - 1
    return m


def avaliar(m, cfg=None):
    """Sinal por regras. Devolve {"score", "rotulo", "motivos", "criterios"}.
    Resultado numérico de critérios fixos — não é recomendação."""
    cfg = {**CONFIG_PADRAO, **(cfg or {})}
    if not m or m.get("erro"):
        return {"score": None, "rotulo": "⚪ Sem dados", "motivos": [(m or {}).get("erro") or "sem cotação"], "criterios": 0}
    tipo = m["tipo"]
    motivos, score, criterios = [], 0.0, 0
    p = m["preco"]
    dy = m.get("dy_12m")
    dy_suspeito = dy is not None and dy > 0.10

    # (1) renda: preço vs teto de dividendos — critério ÚNICO de proventos
    if tipo in ("Ação", "Unit") and m.get("teto_bazin"):
        criterios += 1
        teto = m["teto_bazin"]
        if p <= teto and not dy_suspeito:
            score += 2; motivos.append(f"✅ Preço R$ {p:.2f} ≤ preço de referência de renda R$ {teto:.2f} (mediana dos proventos anuais ÷ yield alvo {cfg['yield_alvo']:.0f}%)")
        elif p <= teto:
            motivos.append(f"➖ Preço abaixo do teto de renda (R$ {teto:.2f}), mas o DY 12m de {dy * 100:.0f}% parece provento extraordinário — não pontua; conferir")
        elif p <= teto * 1.15:
            motivos.append(f"➖ Preço até 15% acima do teto de renda (R$ {teto:.2f})")
        elif p > teto * 1.5:
            score -= 1; motivos.append(f"⚠️ Preço {(p / teto - 1) * 100:.0f}% acima do teto de renda (R$ {teto:.2f})")
        else:
            motivos.append(f"➖ Preço {(p / teto - 1) * 100:.0f}% acima do teto de renda (R$ {teto:.2f})")
    elif tipo in ("Ação", "Unit") and m.get("div_medio_ano") and not m.get("pagando_recente"):
        motivos.append("⚠️ Pagou proventos no passado mas não nos últimos 2 períodos de 12 meses — teto de renda não calculado")
    if dy is not None and tipo in ("Ação", "Unit"):
        motivos.append(f"ℹ️ Dividend yield 12m: {dy * 100:.1f}% (alvo {cfg['yield_alvo']:.0f}%)" + (" — alto demais, possível extraordinário" if dy_suspeito else ""))

    # (2) P/L vs mediana própria (não para cíclicas: lucro de pico dá P/L baixo)
    if m.get("pl_vs_mediano") is not None and not m.get("ciclica"):
        criterios += 1
        r = m["pl_vs_mediano"]
        txt = f"P/L {m['pl_atual']:.1f} vs mediana histórica {m['pl_mediano']:.1f}"
        if r <= -0.15:
            score += 1; motivos.append(f"✅ {txt} ({r * 100:.0f}%)")
        elif r >= 0.25:
            score -= 1; motivos.append(f"⚠️ {txt} (+{r * 100:.0f}%)")
        else:
            motivos.append(f"➖ {txt}")
    elif m.get("pl_atual") and m.get("ciclica"):
        motivos.append(f"ℹ️ P/L {m['pl_atual']:.1f} — setor cíclico ({m['grupo']}): P/L cru não pontua (lucro de pico parece barato, de fundo parece caro)")

    # (3) posição no histórico de preços
    if m.get("percentil_5a") is not None:
        criterios += 1
        pc = m["percentil_5a"]
        if pc <= 0.25:
            score += 1; motivos.append(f"✅ Preço no {pc * 100:.0f}º percentil dos últimos 5 anos (região baixa do próprio histórico)")
        elif pc >= 0.85:
            score -= 1; motivos.append(f"⚠️ Preço no {pc * 100:.0f}º percentil dos últimos 5 anos (região alta do próprio histórico)")
        else:
            motivos.append(f"➖ Preço no {pc * 100:.0f}º percentil dos últimos 5 anos")

    # contexto
    if m.get("streak_lucro") is not None and tipo in ("Ação", "Unit"):
        n = m["streak_lucro"]
        motivos.append(f"ℹ️ Lucro em {n} exercício(s) seguido(s)" + (" — abaixo do critério de 7 anos (não entraria no radar de perenes)" if n < 7 else " ✔ perene pelo critério de 7 anos"))
    if m.get("vs_ma200") is not None:
        motivos.append(f"ℹ️ {m['vs_ma200'] * 100:+.1f}% em relação à média de 200 dias")
    for s_ in m.get("suspeitos", []):
        motivos.append(f"🔎 Dado suspeito: {s_}")

    if tipo in ("ETF", "BDR", "Outro", "FII/Fundo") or criterios < 2:
        rotulo = "⚪ Sem análise de valor"
        if tipo in ("ETF", "BDR", "FII/Fundo"):
            motivos.insert(0, f"ℹ️ {tipo}: sem dados de lucro/P-VP para avaliar valor — só contexto de preço.")
        score = None
    else:
        # sem lucro no último exercício não pode ser tratada como "barata"
        if tipo in ("Ação", "Unit") and m.get("streak_lucro") == 0 and score > 1:
            score = 1
            motivos.append("⚠️ Último exercício sem lucro: a nota fica limitada a 1")
        rotulo = "🟢 Barata pelos critérios" if score >= 3 else ("🟡 Preço intermediário" if score >= 0 else "🔴 Cara pelos critérios")
    return {"score": score, "rotulo": rotulo, "motivos": motivos, "criterios": criterios}


def leitura_da_posicao(av, peso_pct, grupo_pct, cfg=None):
    """Texto descritivo (sem imperativo) + avisos de concentração, com os limites que o próprio usuário definiu."""
    cfg = {**CONFIG_PADRAO, **(cfg or {})}
    r = av.get("rotulo", "")
    if "Barata" in r:
        txt = "Pontuação alta nos critérios de valor."
    elif "intermediário" in r:
        txt = "Pontuação intermediária nos critérios de valor."
    elif "Cara" in r:
        txt = "Pontuação baixa nos critérios de valor."
    else:
        txt = "Sem pontuação de valor para este tipo de papel/dados."
    avisos = []
    if peso_pct is not None and peso_pct > cfg["limite_papel"]:
        avisos.append(f"⚠️ {peso_pct:.1f}% da carteira num só papel (limite que você definiu: {cfg['limite_papel']:.0f}%)")
    if grupo_pct is not None and grupo_pct > cfg["limite_grupo"]:
        avisos.append(f"⚠️ grupo com {grupo_pct:.1f}% da carteira (limite que você definiu: {cfg['limite_grupo']:.0f}%)")
    return txt, avisos


def simular_aporte(qtd, pm, preco, valor):
    """Efeito aritmético de comprar `valor` R$ ao preço atual: nova quantidade e novo preço médio."""
    if not preco or preco <= 0 or valor <= 0:
        return None
    novas = int(valor // preco)
    if novas <= 0:
        return None
    custo_atual = qtd * pm if pm and pm > 0 else None
    novo_pm = ((custo_atual + novas * preco) / (qtd + novas)) if custo_atual is not None else None
    return {"acoes": novas, "gasto": novas * preco, "nova_qtd": qtd + novas, "novo_pm": novo_pm}


# ----------------------------------------------------------------------------
# Carteira: leitura de texto / planilhas
# ----------------------------------------------------------------------------
def _num(txt):
    s = str(txt).strip().replace("R$", "").replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):  # "1.000" = mil, não 1,0
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def interpretar_texto(texto, corretora_padrao="Inter"):
    """Linhas tipo 'PETR4 245 28,90 Inter' (ticker, quantidade, preço médio,
    corretora opcional). Devolve (posicoes, linhas_ignoradas)."""
    pos, ignoradas = [], []
    for linha in str(texto or "").splitlines():
        partes = [p for p in re.split(r"[;\t ]+", linha.strip()) if p]
        if not partes:
            continue
        t = partes[0].upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9]{3}\d{1,2}[A-Z]?", t) or len(partes) < 2:
            ignoradas.append(linha)
            continue
        qtd = _num(partes[1])
        pm = _num(partes[2]) if len(partes) > 2 else None
        corr = partes[3] if len(partes) > 3 else corretora_padrao
        if qtd is None:
            ignoradas.append(linha)
            continue
        t = t[:-1] if re.fullmatch(r"[A-Z][A-Z0-9]{3}\d{1,2}F", t) else t  # fracionário
        pos.append({"ticker": t, "qtd": qtd, "pm": pm or 0.0, "corretora": corr, "alugada": 0, "grupo": ""})
    # mesmo ticker em várias linhas: soma quantidades e faz média ponderada do PM
    uni = {}
    for x in pos:
        k = (x["ticker"], x["corretora"])
        if k in uni:
            u = uni[k]
            tot = u["qtd"] + x["qtd"]
            u["pm"] = (u["pm"] * u["qtd"] + x["pm"] * x["qtd"]) / tot if u["pm"] and x["pm"] else (u["pm"] or x["pm"])
            u["qtd"] = tot
        else:
            uni[k] = dict(x)
    return list(uni.values()), ignoradas


def interpretar_planilha(df, corretora_padrao="B3"):
    """Procura as colunas de ticker/quantidade/preço médio em qualquer layout
    razoável (B3 Área do Investidor, XP, Inter). Devolve (posicoes, aviso)."""
    import unicodedata

    def n(s):
        s = unicodedata.normalize("NFD", str(s).lower())
        return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()
    cols = {n(c): c for c in df.columns}

    def achar(*chaves, exclui=()):
        for k, orig in cols.items():
            if any(c in k for c in chaves) and not any(e in k for e in exclui):
                return orig
        return None
    c_tick = achar("codigo de negociacao", "ticker", "codigo", "ativo", "papel", "produto")
    c_qtd = achar("quantidade disponivel", "quantidade", "qtd", exclui=("indisponivel", "alugada"))
    c_pm = achar("preco medio", "pm", "custo medio unit")
    c_corr = achar("instituicao", "corretora")
    if not c_tick or not c_qtd:
        return [], "Não encontrei colunas de código/ticker e quantidade nessa planilha."
    acum = {}
    for _, r in df.iterrows():
        bruto = str(r[c_tick]).upper()
        m = re.search(r"(?<![A-Z0-9])([A-Z][A-Z0-9]{3}[0-9]{1,2})F?(?![A-Z0-9])", bruto)  # MGLU3F = fracionario do MGLU3
        qtd = _num(r[c_qtd])
        if not m or not qtd:
            continue
        corr = str(r[c_corr]).strip() if c_corr and str(r[c_corr]) != "nan" else corretora_padrao
        for nome in ("XP", "Inter", "BTG", "Clear", "Rico", "Itaú", "Bradesco", "NuInvest"):
            if nome.lower() in corr.lower():
                corr = nome
                break
        chave = (m.group(1), corr)
        pm = (_num(r[c_pm]) if c_pm else None) or 0.0
        if chave in acum:
            ant = acum[chave]
            tot = ant["qtd"] + qtd
            ant["pm"] = (ant["pm"] * ant["qtd"] + pm * qtd) / tot if ant["pm"] and pm else (ant["pm"] or pm)
            ant["qtd"] = tot
        else:
            acum[chave] = {"ticker": m.group(1), "qtd": qtd, "pm": pm, "corretora": corr, "alugada": 0, "grupo": ""}
    pos = list(acum.values())
    aviso = "" if c_pm else "A planilha não traz preço médio (a B3 só informa o preço de fechamento) — o preço médio dos que já existem é mantido."
    return pos, aviso


def mesclar_carteira(atual, novas, substituir_corretora=None):
    """Atualiza por (ticker, corretora). `substituir_corretora`: remove antes
    todas as posições dessa corretora (quando a planilha é a posição completa)."""
    base = [p for p in atual if not (substituir_corretora and str(p.get("corretora")).lower() == substituir_corretora.lower())]
    idx = {(p["ticker"], str(p.get("corretora", "")).lower()): i for i, p in enumerate(base)}
    antigas = {(p["ticker"], str(p.get("corretora", "")).lower()): p for p in atual}
    for nvo in novas:
        chave = (nvo["ticker"], str(nvo.get("corretora", "")).lower())
        if chave in idx:
            ant = base[idx[chave]]
            nvo = {**nvo, "pm": nvo["pm"] or ant.get("pm", 0.0), "grupo": nvo.get("grupo") or ant.get("grupo", ""), "alugada": nvo.get("alugada") or ant.get("alugada", 0)}
            base[idx[chave]] = nvo
        else:
            ant = antigas.get(chave)
            if ant:
                nvo = {**nvo, "pm": nvo["pm"] or ant.get("pm", 0.0), "grupo": nvo.get("grupo") or ant.get("grupo", "")}
            base.append(nvo)
            idx[chave] = len(base) - 1
    return base


# ----------------------------------------------------------------------------
# Persistência (fin_configuracoes — sem migração de banco)
# ----------------------------------------------------------------------------
CHAVE_CARTEIRA = "acoes_carteira"
CHAVE_CONFIG = "acoes_config"


def _ler(sb, chave, padrao):
    """Levanta exceção em erro de rede/banco (NÃO devolve o padrão): ler vazio por
    engano e depois gravar apagaria a carteira."""
    r = sb.table("fin_configuracoes").select("valor1").eq("chave", chave).execute().data
    return json.loads(r[0]["valor1"]) if r and r[0].get("valor1") else padrao


def _gravar(sb, chave, valor):
    antigo = sb.table("fin_configuracoes").select("valor1").eq("chave", chave).execute().data
    if antigo and antigo[0].get("valor1"):  # backup da versão anterior
        sb.table("fin_configuracoes").delete().eq("chave", chave + "_bak").execute()
        sb.table("fin_configuracoes").insert({"chave": chave + "_bak", "valor1": antigo[0]["valor1"]}).execute()
    sb.table("fin_configuracoes").delete().eq("chave", chave).execute()
    try:
        sb.table("fin_configuracoes").insert({"chave": chave, "valor1": json.dumps(valor, ensure_ascii=False)}).execute()
    except Exception:
        if antigo:
            sb.table("fin_configuracoes").insert({"chave": chave, "valor1": antigo[0]["valor1"]}).execute()
        raise


def ler_carteira(sb):
    return _ler(sb, CHAVE_CARTEIRA, [])


def gravar_carteira(sb, carteira):
    _gravar(sb, CHAVE_CARTEIRA, carteira)


def ler_config(sb):
    return {**CONFIG_PADRAO, **_ler(sb, CHAVE_CONFIG, {})}


def gravar_config(sb, cfg):
    _gravar(sb, CHAVE_CONFIG, cfg)
