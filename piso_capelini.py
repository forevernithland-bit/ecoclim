"""Piso de preço Capelini — regra do Breno (2026-10-06).

O preço de VENDA de um material comprado na Tambasa NUNCA pode ficar abaixo do
preço de venda do MESMO material da Capelini. Motivo: a Tambasa é o fornecedor
barato do dia a dia, mas quando falta peça a compra cai na Capelini (custo
maior). Se a venda do item ficou calculada em cima do custo Tambasa e ficar
abaixo do que a Capelini cobra da Ecoclim + a margem padrão dela, a Ecoclim
vende esse item com prejuízo (ou margem menor que a mínima) sempre que a peça
vier da Capelini — e a lista de materiais pro cliente usa o menor preço entre
as opções do mesmo nome.

Regra:
  * "Mesmo material" = mesmo nome de item (sem acento/caixa) em linhas de
    fornecedores diferentes em `materiais_padrao`.
  * Piso = o MAIOR entre (custo Capelini x 1,15) e (venda cadastrada da Capelini).
    1,15 = 15% acima do valor que a Capelini vende pra Ecoclim.
  * As margens da Tambasa ficam como estão. Só se a venda de um item Tambasa
    ficar abaixo do piso é que ELE (e só ele) é reajustado: venda = piso e
    `margem_percentual` recalculada em cima do custo Tambasa.
  * Item Tambasa sem custo ainda (0) é ignorado — não tem preço pra corrigir.

Módulo puro (sem Streamlit): é chamado pelo ERP (estoque_materiais.py), pelos
scripts da skill (atualizar_precos, importar_tambasa) e pode rodar sozinho:
    python piso_capelini.py             # só mostra o que ajustaria
    python piso_capelini.py --confirmar # aplica
"""
import re
import sys
import unicodedata
from decimal import Decimal, ROUND_HALF_UP

MARGEM_PISO_PCT = Decimal("15")
_CENT = Decimal("0.01")


def _norm(texto):
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


# Equivalências ENTRE NOMES diferentes (mesmo material, nome diferente em cada
# fornecedor). Vazio de propósito: só entra aqui o que o Breno confirmar —
# ex.: {"fita veda rosca 18mm x 50m": "veda rosca grande"} (nome normalizado
# da Capelini -> nome normalizado da Tambasa). Sem isso, só nome IGUAL conta.
EQUIVALENCIAS = {}


def _chave(item):
    n = _norm(item)
    return EQUIVALENCIAS.get(n, n)


def _forn(linha):
    return str(linha.get("fornecedor") or "").strip().upper()


def _dec(valor):
    try:
        d = Decimal(str(valor if valor is not None else 0))
    except Exception:
        return Decimal("0")
    return d if d.is_finite() else Decimal("0")  # NaN/inf viram 0 (sem piso, sem ajuste)


def _q(valor):
    return valor.quantize(_CENT, rounding=ROUND_HALF_UP)


def calcular_ajustes(linhas):
    """Recebe as linhas de `materiais_padrao` (dicts) e devolve a lista de
    ajustes necessários — não grava nada."""
    grupos = {}
    for r in linhas:
        grupos.setdefault(_chave(r.get("item")), []).append(r)

    ajustes = []
    for _nome, grupo in grupos.items():
        capelini = [r for r in grupo if _forn(r) == "CAPELINI" and _dec(r.get("custo")) > 0]
        if not capelini:
            continue
        # referência = a linha Capelini mais cara (a que mais pesa se a compra cair nela)
        ref = max(capelini, key=lambda r: max(_dec(r["custo"]) * (1 + MARGEM_PISO_PCT / 100), _dec(r.get("venda"))))
        piso = _q(max(_dec(ref["custo"]) * (1 + MARGEM_PISO_PCT / 100), _dec(ref.get("venda"))))
        for r in grupo:
            if _forn(r) != "TAMBASA":
                continue
            custo, venda = _dec(r.get("custo")), _dec(r.get("venda"))
            if custo <= 0 or venda >= piso:
                continue
            ajustes.append({
                "id": r["id"], "item": r.get("item"), "fabricante": r.get("fabricante"),
                "custo": custo, "venda_antiga": venda, "venda_nova": piso,
                "margem_antiga": _q((venda / custo - 1) * 100),
                "margem_nova": _q((piso / custo - 1) * 100),
                "linha": r,  # linha original completa (codigo_externo, estoque, ncm...) — quem sincroniza com o Gestão Click precisa dela
                "ref_id": ref["id"], "ref_custo": _dec(ref["custo"]), "ref_venda": _dec(ref.get("venda")),
            })
    return ajustes


def aplicar(sb, linhas=None, gravar=True):
    """Calcula (e, se `gravar`, grava) os ajustes. Devolve a lista de ajustes
    — cada um já traz tudo que quem chamou precisa pra avisar o usuário ou
    sincronizar com o Gestão Click."""
    if linhas is None:
        linhas = sb.table("materiais_padrao").select("*").execute().data or []
    ajustes = calcular_ajustes(linhas)
    if gravar:
        for a in ajustes:
            sb.table("materiais_padrao").update({
                "venda": float(a["venda_nova"]), "margem_percentual": float(a["margem_nova"]),
            }).eq("id", a["id"]).execute()
    return ajustes


def descrever(ajustes):
    return [
        f"{a['item']} [{a.get('fabricante') or '-'}]: venda R$ {a['venda_antiga']} -> R$ {a['venda_nova']} "
        f"(margem {a['margem_antiga']}% -> {a['margem_nova']}%) — piso: Capelini #{a['ref_id']} "
        f"(custo R$ {a['ref_custo']} x 1,15)"
        for a in ajustes
    ]


if __name__ == "__main__":
    sys.path.insert(0, r"C:\Users\desta\.claude\skills\erp-ecoclim\scripts")
    from ecoclim_db import supabase
    sb = supabase()
    confirmar = "--confirmar" in sys.argv
    res = aplicar(sb, gravar=confirmar)
    if not res:
        print("Nenhum item Tambasa abaixo do piso Capelini.")
    for linha in descrever(res):
        print(("APLICADO  " if confirmar else "AJUSTARIA  ") + linha)
    if res and not confirmar:
        print("\nPREVIEW — rode com --confirmar pra aplicar.")
