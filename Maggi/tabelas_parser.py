#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le os PDFs de tabela de precos da pasta Maggi/tabelas/ e gera Maggi/tabelas.json.

- O grupo e identificado pelo numero presente no NOME do arquivo (mesmo que o
  mes mude, ex.: "Tabela de precos 2020 Jul_26.pdf" -> grupo 2020;
  "TABELA CONS GRUPO 634 ..." -> grupo 634).
- Extrai: prazos disponiveis (cada um com sua taxa de administracao),
  valores de credito disponiveis, fundo de reserva e seguro de vida.
- Tambem extrai a GRADE da tabela (campo "linhas": uma entrada por credito com
  parcela ideal, parcela reduzida, parcela apos a reducao e valor disponivel) e,
  nos grupos com PARCELA REDUZIDA, o campo "reduzida":
      {"meses": 60, "fator": 0.5, "pct_ideal": 0.7092, "pct_reduzida": 0.3546, "pct_apos": 0.9719}
  Regra: ate a parcela `meses` (ou ate a contemplacao) paga-se `fator` x a parcela
  ideal; depois a parcela passa a ser a do "apos" e dilui o restante do prazo.
  O simulador usa isso para oferecer "Parcela reduzida" ou "Parcela integral".
- Roda pela GitHub Action (instala pdfplumber). Robusto: se um PDF falhar,
  mantem o valor anterior daquele grupo (nao apaga dados bons).

Coloque os PDFs em Maggi/tabelas/ no repositorio.
"""
import pdfplumber, re, glob, os, json, datetime

SAIDA = os.path.join(os.path.dirname(__file__), "tabelas.json")

def achar_pdfs():
    """Procura PDFs em qualquer pasta chamada 'tabelas' (sem diferenciar
    maiusculas/minusculas), a partir da raiz do repositorio."""
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
    achados = []
    for dirpath, dirs, files in os.walk(raiz):
        if os.path.basename(dirpath).lower() == "tabelas":
            for f in files:
                if f.lower().endswith(".pdf"):
                    achados.append(os.path.join(dirpath, f))
    return achados

GRUPOS = ["2013", "2014", "2015", "2016", "2017", "2018", "2019", "2020", "634", "636", "644", "645", "755", "757", "8000"]
MES = r'(janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)'


def detectar_grupo(fname):
    base = os.path.basename(fname)
    for g in sorted(GRUPOS, key=len, reverse=True):
        if re.search(r'(?<!\d)' + g + r'(?!\d)', base):
            return g
    return None


def num(s):
    s = s.strip().replace('.', '').replace(',', '.')
    try:
        return float(s)
    except Exception:
        return None


def _pct(s):
    """'0,7092%' -> 0.7092 (em %). None se nao for percentual."""
    m = re.search(r'(\d+[.,]\d+)\s*%', str(s or ''))
    return num(m.group(1)) if m else None


def _valor(s):
    """'R$ 4.794,63' / '1.819,43' / '519.063' / 'R$ 9 0.317' -> float."""
    t = re.sub(r'[^\d.,]', '', str(s or '').replace(' ', ''))
    if not t:
        return None
    return num(t)


def parse_grade(path):
    """Le a grade da tabela (pdfplumber.extract_tables). Devolve (linhas, reduzida).
    linhas: [{"cod"?, "credito", "parcela", "parcela_sem_seguro"?, "reduzida"?, "apos"?, "disponivel"?}]
    reduzida: dict (ver docstring) ou None."""
    with pdfplumber.open(path) as pdf:
        tabs = pdf.pages[0].extract_tables()
    if not tabs:
        return [], None
    t = tabs[0]
    cab = [(c or '').replace('\n', ' ').strip() for c in t[0]]
    cabu = [c.upper() for c in cab]

    def col(*chaves, excluir=()):
        for i, c in enumerate(cabu):
            if any(k in c for k in chaves) and not any(e in c for e in excluir):
                return i
        return None

    i_cred = col('VALOR DO CR', 'CRÉDITO (R$)', 'CREDITO (R$)', 'CRÉDITO', 'CREDITO', excluir=('DESCRI', 'CREDITOS'))
    if i_cred is None:
        return [], None
    i_cod = col('CÓDIGO', 'CODIGO', 'CÓD')
    i_red = col('REDUZIDA')
    i_apos = col('APÓS', 'APOS')
    i_disp = col('DISPON')
    i_sem = col('SEM SEGURO')
    i_ideal = col('PARCELA IDEAL', 'PARCELA NORMAL COM SEGURO', 'COM SEGURO', 'PARCELA/M', 'PARCELA 4', 'MESES')
    if i_ideal is None or i_ideal in (i_red, i_apos, i_disp, i_cred, i_cod, i_sem):
        i_ideal = col('PARCELA IDEAL', 'PARCELA/M', 'PARCELA NORMAL', 'MESES')
    # Volvo: o titulo "reduzida" e mesclado sobre duas colunas (reduzida, apos); a 2a fica sem titulo
    if i_red is not None and i_apos is None and i_red + 1 < len(cab) and not cab[i_red + 1]:
        i_apos = i_red + 1

    # percentuais: linha logo abaixo do cabecalho (ou dentro do proprio titulo, como no 2013)
    pcts = {}
    for r in t[1:3]:
        for i, c in enumerate(r):
            v = _pct(c)
            if v is not None:
                pcts[i] = v
    for i, c in enumerate(cab):
        if i not in pcts and _pct(c) is not None:
            pcts[i] = _pct(c)

    linhas = []
    for r in t[1:]:
        cred = _valor(r[i_cred]) if i_cred < len(r) else None
        if not cred or cred < 1000:
            continue
        item = {"credito": int(round(cred))}
        if i_cod is not None and i_cod < len(r) and r[i_cod]:
            item["cod"] = str(r[i_cod]).strip()

        def pega(i, chave):
            if i is not None and i < len(r):
                v = _valor(r[i])
                if v is not None:
                    item[chave] = v
        pega(i_ideal, "parcela")
        pega(i_sem, "parcela_sem_seguro")
        pega(i_red, "reduzida")
        pega(i_apos, "apos")
        pega(i_disp, "disponivel")
        if "parcela" in item:
            linhas.append(item)

    reduzida = None
    if i_red is not None and i_apos is not None and i_ideal is not None:
        mm = re.search(r'(\d+)\s*MESES', cabu[i_red])
        meses = int(mm.group(1)) if mm else None
        pi, pr, pa = pcts.get(i_ideal), pcts.get(i_red), pcts.get(i_apos)
        if meses and pi and pr and pa:
            reduzida = {"meses": meses, "fator": round(pr / pi, 2), "pct_ideal": pi, "pct_reduzida": pr, "pct_apos": pa}
    return linhas, reduzida


def parse_pdf(path):
    with pdfplumber.open(path) as pdf:
        text = '\n'.join((p.extract_text() or '') for p in pdf.pages)
    lines = text.split('\n')

    rm = re.search(MES + r'\s+\d{4}', text, re.I)
    ref = rm.group(0) if rm else ''

    creditos = []
    for ln in lines:
        if re.match(r'\s*CR[ÉE]DITO', ln, re.I):
            vals = [num(n) for n in re.findall(r'\d[\d.]*,?\d*', ln)]
            vals = [v for v in vals if v and v >= 1000]
            if vals:
                creditos.append(int(max(vals)))

    tline = next((ln for ln in lines if re.search(r'TAXA DE ADMINIST', ln, re.I)), '')
    segs = re.findall(r'(\d+)\s*%\s*\(([^)]*)\)', tline)
    prazos = []
    if segs:
        for taxa, dentro in segs:
            for mm in re.findall(r'\d+', dentro):
                prazos.append({"meses": int(mm), "taxa": int(taxa)})
    else:
        # taxa: 1) "TAXA DE ADMINISTRACAO.: 21%"; 2) "TAXA 15+1" / "TAXA 15%"
        tm = re.search(r'ADMINISTRA[çc][ãa]O[.:\s]*(\d+)\s*%', tline, re.I)
        if not tm:
            tm = re.search(r'\bTAXA\b[.:\s]*(\d+)', text, re.I)
        taxa = int(tm.group(1)) if tm else None
        pm = re.search(r'PLANO\s*(\d+)\s*PRESTA', text, re.I)
        if pm:
            meses = int(pm.group(1))
        else:
            hm = re.findall(r'(\d+)\s*MESES', text.upper())
            meses = int(hm[0]) if hm else None
        if meses and taxa:
            prazos = [{"meses": meses, "taxa": taxa}]

    fm = re.search(r'Fundo de [Rr]eserva[\s=:.]*([\d,]+)\s*%', text, re.I)
    fundo = num(fm.group(1)) if fm else 1.0
    sm = re.search(r'Seguro de [Vv]ida[\s=:.]*([\d,]+)\s*%', text, re.I)
    seguro = num(sm.group(1)) if sm else None

    # Datas de assembleia e vencimento (guardadas em ISO aaaa-mm-dd)
    am = re.search(r'(?:Data\s*[Aa]ssembleia|Assembleia)[^\d]*(\d{2})[./](\d{2})[./](\d{4})', text)
    assembleia = "{}-{}-{}".format(am.group(3), am.group(2), am.group(1)) if am else None
    vm = re.search(r'Vencimento[^\d]*(\d{2})[./](\d{2})[./](\d{4})', text)
    vencimento = "{}-{}-{}".format(vm.group(3), vm.group(2), vm.group(1)) if vm else None

    saida = {"ref": ref, "prazos": prazos, "fundo": fundo, "seguro": seguro,
             "creditos": creditos, "assembleia": assembleia, "vencimento": vencimento}
    try:
        linhas, reduzida = parse_grade(path)
        if linhas:
            saida["linhas"] = linhas
        if reduzida:
            saida["reduzida"] = reduzida
    except Exception as e:  # a grade e extra: se falhar, os campos antigos continuam valendo
        print("  (grade nao lida em {}: {})".format(os.path.basename(path), e))
    return saida


def carregar_antigo():
    try:
        with open(SAIDA, encoding="utf-8") as f:
            return json.load(f).get("grupos", {})
    except Exception:
        return {}


def main():
    antigo = carregar_antigo()
    grupos = dict(antigo)  # comeca com os valores anteriores (preserva)
    pdfs = achar_pdfs()
    print("PDFs encontrados:", len(pdfs))
    achou = 0
    for f in pdfs:
        g = detectar_grupo(f)
        if not g:
            print("  sem grupo no nome:", os.path.basename(f))
            continue
        try:
            d = parse_pdf(f)
            if d["prazos"] and d["creditos"]:
                grupos[g] = d
                achou += 1
                print("  grupo {}: {} prazos, {} creditos".format(g, len(d["prazos"]), len(d["creditos"])))
            else:
                print("  grupo {}: dados incompletos, mantido anterior".format(g))
        except Exception as e:
            print("  erro em", os.path.basename(f), ":", e)

    if achou == 0 and antigo:
        print("Nenhuma tabela lida. Mantendo tabelas.json anterior.")
        return

    saida = {
        "atualizado_em": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "fonte": "Tabelas de precos Maggi (PDF)",
        "grupos": grupos,
    }
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)
    print("tabelas.json atualizado ({} grupos).".format(len(grupos)))


if __name__ == "__main__":
    main()
