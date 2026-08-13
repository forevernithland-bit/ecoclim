#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le os PDFs de tabela de precos da pasta Maggi/tabelas/ e gera Maggi/tabelas.json.

- O grupo e identificado pelo numero presente no NOME do arquivo (mesmo que o
  mes mude, ex.: "Tabela de precos 2020 Jul_26.pdf" -> grupo 2020;
  "TABELA CONS GRUPO 634 ..." -> grupo 634).
- Extrai: prazos disponiveis (cada um com sua taxa de administracao),
  valores de credito disponiveis, fundo de reserva e seguro de vida.
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

    return {"ref": ref, "prazos": prazos, "fundo": fundo, "seguro": seguro,
            "creditos": creditos, "assembleia": assembleia, "vencimento": vencimento}


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
