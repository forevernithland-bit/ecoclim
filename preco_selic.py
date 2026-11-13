"""Preço de venda dos EQUIPAMENTOS (catalogo_produtos) amarrado à Selic.

Regra do Breno (2026-11-13): a margem LÍQUIDA de cada venda tem que ser a
Selic atual + 1,5 ponto percentual (hoje 13,75% + 1,5 = 15,25%), pra render
mais que a Selic. Se a Selic mudar, a margem muda junto; se o custo do
equipamento mudar (tabela do fornecedor atualizada), o preço é recalculado.

"Margem líquida" = lucro depois de TUDO que sai da venda:
  * imposto da NF  (linha "Imposto NF (%)" da tabela de taxas — hoje 6%)
  * taxa do cartão (linha "Crédito 3x" da tabela de taxas — hoje 5,10%; é o
    pior caso aceito, vendas em até 3x ficam com no mínimo a margem-alvo)
  * instalação (mão de obra do instalador, vendida ao cliente pelo próprio
    custo — catalogo_servicos)
  * custo do equipamento

Conta (V = venda total do cliente = equipamento + instalação):
    líquido = V·(1 − NF − cartão) − custo − instalação  ≥  alvo · V
    V = (custo + instalação) / (1 − NF − cartão − alvo)
    venda do equipamento = V − instalação
Equipamento sem instalação casada (bomba, válvula, kit...) usa instalação = 0.

NÃO mexe em materiais hidráulicos (materiais_padrao) — só em catalogo_produtos.
Fora da regra: itens com custo 0 e itens espelhados com a lista de materiais
(Caixa de Quebra de Pressão, preço fixo — ver itens_espelhados.py), mais os
nomes em `excecoes` da configuração.

Configuração em fin_configuracoes, chave `precificacao_selic` (JSON em valor1):
    {"selic": 13.75, "spread": 1.5, "cartao": "Crédito 3x",
     "excecoes": [], "atualizado_em": "...", "selic_data": "..."}

Módulo puro (sem Streamlit): recebe o cliente do Supabase por parâmetro, serve
ao ERP, aos scripts da skill e roda sozinho:
    python preco_selic.py             # só mostra o que mudaria
    python preco_selic.py --confirmar # aplica
"""
import datetime
import json
import re
import sys
import urllib.request

CHAVE = "precificacao_selic"
SPREAD_PADRAO = 1.5
CARTAO_PADRAO = "Crédito 3x"
NF_PADRAO = 6.0
URL_SELIC = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json"


# ----------------------------------------------------------------- config
def ler_config(sb):
    try:
        r = sb.table("fin_configuracoes").select("valor1").eq("chave", CHAVE).execute().data or []
        cfg = json.loads(r[0]["valor1"]) if r else {}
    except Exception:
        cfg = {}
    cfg.setdefault("spread", SPREAD_PADRAO)
    cfg.setdefault("cartao", CARTAO_PADRAO)
    cfg.setdefault("excecoes", [])
    return cfg


def gravar_config(sb, cfg):
    blob = json.dumps(cfg, ensure_ascii=False)
    try:
        existe = sb.table("fin_configuracoes").select("id").eq("chave", CHAVE).execute().data or []
        if existe:
            sb.table("fin_configuracoes").update({"valor1": blob}).eq("chave", CHAVE).execute()
        else:
            sb.table("fin_configuracoes").insert({"chave": CHAVE, "valor1": blob}).execute()
    except Exception:
        pass


def buscar_selic():
    """Meta Selic vigente (% a.a.) na API do Banco Central (série 432).
    Retorna (valor, data) ou (None, None) se a API não responder."""
    try:
        with urllib.request.urlopen(URL_SELIC, timeout=10) as resp:
            d = json.loads(resp.read().decode("utf-8"))[-1]
        return float(d["valor"]), d["data"]
    except Exception:
        return None, None


# --------------------------------------------------------------- parâmetros
def _taxas(sb, cfg):
    nf, cartao = NF_PADRAO, None
    for t in sb.table("catalogo_taxas").select("item,taxa_percentual").execute().data or []:
        nome = str(t.get("item") or "")
        if nome.strip().lower() == cfg["cartao"].strip().lower():
            cartao = float(t["taxa_percentual"])
        if "nf" in nome.lower() and "imposto" in nome.lower():
            nf = float(t["taxa_percentual"])
    if cartao is None:
        raise RuntimeError(f"Taxa '{cfg['cartao']}' não encontrada na tabela de taxas.")
    return nf, cartao


def _mo_instalacao(nome, servicos):
    """Custo de instalação casado ao equipamento (ou None)."""
    n = nome.upper()
    m = re.search(r"ACOPLADO (\d+) TUBOS", n)
    if m:
        return servicos.get(f"INSTALAÇÃO ACOPLADO {m.group(1)} TUBOS")
    m = re.search(r"BOILER (\d+) LITROS .* - (TRADICIONAL|METALIC)", n)
    if m:
        litros = {1050: 1000}.get(int(m.group(1)), int(m.group(1)))
        tipo = "TRADICIONAL" if m.group(2) == "TRADICIONAL" else "MODULAR"
        return servicos.get(f"INSTALAÇÃO {tipo} {litros} LITROS")
    return None


def _norm(t):
    return re.sub(r"\s+", " ", str(t or "")).strip().casefold()


# ------------------------------------------------------------------ cálculo
def calcular(sb, selic=None, cfg=None):
    """Lista de ajustes {linha, venda_nova, margem_nova, lucro_novo, ...} para
    os equipamentos cujo preço difere do que a regra manda. Não grava nada."""
    cfg = cfg or ler_config(sb)
    if selic is None:
        selic = cfg.get("selic")
    if not selic:
        raise RuntimeError("Selic não informada e não consegui buscar no Banco Central.")
    alvo = (float(selic) + float(cfg["spread"])) / 100
    nf, cartao = _taxas(sb, cfg)
    d = 1 - nf / 100 - cartao / 100 - alvo
    if d <= 0:
        raise RuntimeError("Imposto + cartão + margem-alvo passam de 100% da venda.")
    servicos = {x["item"]: float(x["custo"] or 0)
                for x in sb.table("catalogo_servicos").select("item,custo").execute().data or []}
    try:
        import itens_espelhados
        espelhados = {_norm(x) for x in itens_espelhados.ITENS_ESPELHADOS}
    except Exception:
        espelhados = {_norm("Caixa Auxiliar de Quebra de Pressão")}
    excecoes = {_norm(x) for x in cfg.get("excecoes", [])}

    ajustes = []
    for p in sb.table("catalogo_produtos").select("*").execute().data or []:
        custo = float(p.get("custo") or 0)
        nome = str(p.get("item") or "")
        if custo <= 0 or _norm(nome) in espelhados or _norm(nome) in excecoes:
            continue
        mo = _mo_instalacao(nome, servicos) or 0.0
        venda = round((custo + mo) / d - mo, 2)
        atual = float(p.get("venda") or 0)
        if abs(venda - atual) < 0.005:
            continue
        if venda < atual:
            # Preço só DESCE se foi esta regra que o colocou lá (Selic caiu ou
            # custo baixou). Preço maior posto à mão pelo Breno é respeitado.
            guardado = cfg.get("gerenciados", {}).get(_norm(nome))
            if guardado is None or abs(float(guardado) - atual) > 0.01:
                continue
        ajustes.append({
            "linha": p, "item": nome, "custo": custo, "mo": mo,
            "venda_antiga": float(p.get("venda") or 0), "venda_nova": venda,
            "margem_nova": round((venda - custo) / custo * 100, 2),
            "lucro_novo": round(venda - custo, 2),
        })
    return ajustes, {"selic": float(selic), "alvo_pct": round(alvo * 100, 2), "nf": nf, "cartao": cartao}


def aplicar(sb, ajustes, sync=None):
    """Grava os ajustes. `sync(linha_completa)` (opcional) manda o preço novo
    pro Gestão Click; erro de sync não desfaz o preço gravado aqui."""
    erros = []
    for a in ajustes:
        dados = {"venda": a["venda_nova"], "margem": a["margem_nova"], "lucro": a["lucro_novo"]}
        sb.table("catalogo_produtos").update(dados).eq("id", a["linha"]["id"]).execute()
        if sync and a["linha"].get("codigo_externo"):
            try:
                sync({**a["linha"], **dados})
            except Exception as e:  # noqa: BLE001
                erros.append(f"{a['item']}: {str(e)[:80]}")
    return erros


def reajustar(sb, sync=None, confirmar=True, forcar_selic=True):
    """Passo completo: busca a Selic, recalcula e (se confirmar) grava.
    Retorna (ajustes, info, erros_sync)."""
    cfg = ler_config(sb)
    selic, data = buscar_selic() if forcar_selic else (None, None)
    if selic is None:
        selic = cfg.get("selic")
    else:
        cfg["selic"], cfg["selic_data"] = selic, data
    ajustes, info = calcular(sb, selic, cfg)
    erros = []
    if confirmar:
        erros = aplicar(sb, ajustes, sync)
        cfg["atualizado_em"] = datetime.datetime.now().isoformat(timespec="seconds")
        cfg["ultimo_ajuste_itens"] = len(ajustes)
        ger = cfg.setdefault("gerenciados", {})
        for a in ajustes:
            ger[_norm(a["item"])] = a["venda_nova"]
        gravar_config(sb, cfg)
    return ajustes, info, erros


def descrever(ajustes, info):
    linhas = [f"Selic {info['selic']:g}% + spread → margem líquida-alvo {info['alvo_pct']:g}% "
              f"(NF {info['nf']:g}% + cartão {info['cartao']:g}%)"]
    for a in ajustes:
        linhas.append(f"{a['item']}: R$ {a['venda_antiga']:.2f} -> R$ {a['venda_nova']:.2f}")
    return linhas


if __name__ == "__main__":
    sys.path.insert(0, r"C:/Users/desta/.claude/skills/erp-ecoclim/scripts")
    import ecoclim_db as _e
    _sb = _e.supabase()
    _aj, _info, _er = reajustar(_sb, sync=lambda l: _e.sincronizar_produto(_sb, l, "catalogo_produtos"),
                                confirmar="--confirmar" in sys.argv)
    print("\n".join(descrever(_aj, _info)))
    print(f"\n{len(_aj)} item(ns) {'ajustado(s)' if '--confirmar' in sys.argv else 'a ajustar (PREVIEW)'}")
    for e in _er:
        print("  sync falhou:", e)
