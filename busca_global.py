"""🔎 Busca global — um campo na barra lateral que acha qualquer coisa do
sistema: clientes/serviços/orçamentos, contas a pagar (boletos), empréstimos,
produtos (equipamentos) e materiais hidráulicos.

Usa a mesma busca inteligente do resto do ERP (busca_inteligente.py): palavras
em qualquer ordem, sem acento, começo de palavra, plural, erro leve de
digitação, telefone/CPF por dígitos. Ex.: "20 tubos", "flavio 9212",
"boiler 600", "cx quebra".

Clicar num cliente abre a tela Serviços já na aba certa, com o painel dele
aberto (ou a tela de Orçamentos, se for rascunho). Boletos e empréstimos abrem
em Documentos. Produtos e materiais mostram o preço ali mesmo.

Só leitura: nada aqui grava no banco.
"""
import datetime
import re

import streamlit as st

import busca_inteligente as bi
import utils

ATIVOS = ["Em Andamento", "Aguardando Pagamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO"]
MAX_POR_GRUPO = 6


def _digitos(t):
    return re.sub(r"\D", "", str(t or ""))


def _bate(termo, *campos):
    if bi.termo_bate(termo, *campos):
        return True
    d = _digitos(termo)
    if len(d) >= 4:  # telefone/CPF/CNPJ/código por dígitos
        return any(d in _digitos(c) for c in campos if c)
    return False


def _pontos(termo, texto):
    try:
        return bi._pontuar(termo, texto)[0]
    except Exception:
        return 0.0


def _eh_fv(dc):
    try:
        import servicos_fotovoltaico
        return servicos_fotovoltaico.eh_fv(dc)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Navegação (callbacks — rodam antes da próxima execução da tela)
# ---------------------------------------------------------------------------
def _ir_servico(reg):
    s = st.session_state
    status = str(reg.get("status_projeto") or "")
    sid = int(reg["id"])
    fv = _eh_fv(reg.get("dados_contrato"))
    if status in ("Rascunho", "Rascunho Rápido"):
        s.menu_option = "Orçamentos"
        st.toast("Rascunhos ficam em Orçamentos → Orçamento Personalizado / Rápido.", icon="📝")
        return
    s.menu_option = "Serviços em Andamento"
    # fecha qualquer outro painel que estivesse aberto (só o cliente buscado fica aberto)
    for k in [k for k in list(s.keys()) if str(k).startswith("painel_id_")]:
        s[k] = None
    if status in ("Concluído PIX", "Concluído CARTÃO"):
        dt = None
        try:
            dt = datetime.date.fromisoformat(str(reg.get("data_conclusao") or "")[:10])
        except Exception:
            pass
        dt = dt or datetime.date.today()
        s["serv_abas"] = "✅ Finalizados"
        s["filtro_ano_fin"] = dt.year
        s["filtro_mes_fin"] = utils.meses_pt[dt.month - 1]
        pref = f"fin_{dt.year}_{dt.month}"
        s[f"painel_id_{pref}"] = sid
        s[f"painel_linhas_{pref}"] = []
    elif status in ATIVOS:
        s["serv_abas"] = "🚀 Em Andamento"
        s["busca_termo_atv"] = ""
        pref = "atv_fv" if fv else "atv_aq"
        outro = "atv_aq" if fv else "atv_fv"
        s[f"painel_id_{pref}"] = sid
        s[f"painel_linhas_{pref}"] = []
        s[f"painel_id_{outro}"] = None
        s["_atv_foco"] = "fv" if fv else "aq"
    elif fv:
        s["serv_abas"] = "☀️ Fotovoltaico"
        st.toast("Cliente de indicação fotovoltaica — está na aba ☀️ Fotovoltaico.", icon="☀️")
    else:
        s["serv_abas"] = "📝 Orçamentos"
        s["busca_termo_orc"] = ""
        s["painel_id_orc"] = sid
        s["painel_linhas_orc"] = []
    s["busca_global_q"] = ""


def _ir_documentos(categoria):
    st.session_state.menu_option = "Documentos"
    st.session_state.doc_ir_para = categoria
    st.session_state["busca_global_q"] = ""


# ---------------------------------------------------------------------------
# Busca
# ---------------------------------------------------------------------------
def buscar(sb, termo):
    termo = (termo or "").strip()
    res = {"servicos": [], "boletos": [], "emprestimos": [], "produtos": [], "materiais": []}
    if len(bi.normalizar(termo)) < 2:
        return res
    try:
        linhas = sb.table("servicos_andamento").select(
            "id,nome_cliente,telefone_cliente,numero_orcamento,bairro_cliente,cpf_cnpj_cliente,"
            "status_projeto,valor_venda_total,data_conclusao,dados_contrato").execute().data or []
        achados = [r for r in linhas if _bate(termo, r.get("nome_cliente"), r.get("telefone_cliente"),
                                              r.get("numero_orcamento"), r.get("bairro_cliente"), r.get("cpf_cnpj_cliente"))]
        achados.sort(key=lambda r: (-_pontos(termo, r.get("nome_cliente") or ""),
                                    0 if r.get("status_projeto") in ATIVOS else 1))
        res["servicos"] = achados[:MAX_POR_GRUPO]
    except Exception:
        pass
    try:
        bol = sb.table("boletos_fornecedores").select("id,cliente,vencimento,valor,status").eq("status", "Pendente").execute().data or []
        res["boletos"] = [b for b in bol if _bate(termo, b.get("cliente"))][:MAX_POR_GRUPO]
    except Exception:
        pass
    try:
        emp = sb.table("emprestimos").select("id,pessoa,vencimento,valor_parcela,status,parcela_num,total_parcelas").eq("status", "Pendente").execute().data or []
        vistos, lst = set(), []
        for e in sorted(emp, key=lambda x: str(x.get("vencimento") or "")):
            if _bate(termo, e.get("pessoa")) and e.get("pessoa") not in vistos:
                vistos.add(e.get("pessoa"))
                lst.append(e)
        res["emprestimos"] = lst[:MAX_POR_GRUPO]
    except Exception:
        pass
    try:
        prods = sb.table("catalogo_produtos").select("item,venda,custo").execute().data or []
        import catalogo_ajustes
        nomes = catalogo_ajustes.visiveis(sb, [p["item"] for p in prods if p.get("item")])
        top, _aprox = bi.buscar(termo, nomes, limite=MAX_POR_GRUPO)
        mapa = {p["item"]: p for p in prods}
        res["produtos"] = [mapa[n] for n in top if n in mapa] if not _aprox else []
    except Exception:
        pass
    try:
        mats = sb.table("materiais_padrao").select("item,venda,unidade").execute().data or []
        melhor = {}
        for m in mats:
            v = float(m.get("venda") or 0)
            if m.get("item") and v > 0 and (m["item"] not in melhor or v < melhor[m["item"]]["venda"]):
                melhor[m["item"]] = {"item": m["item"], "venda": v, "unidade": m.get("unidade") or "un"}
        top, _aprox = bi.buscar(termo, list(melhor), limite=MAX_POR_GRUPO)
        res["materiais"] = [melhor[n] for n in top] if not _aprox else []
    except Exception:
        pass
    return res


def _rotulo_status(st_txt):
    return {"Em Andamento": "🚀", "Aguardando Pagamento": "⏳", "Concluído PIX": "✅", "Concluído CARTÃO": "✅",
            "Orçamento Enviado": "📝", "Orçamento Cancelado": "✖️", "Rascunho": "✏️", "Rascunho Rápido": "✏️"}.get(st_txt, "•")


def render_sidebar(sb):
    termo = st.text_input("🔎 Buscar no sistema", key="busca_global_q",
                          placeholder="cliente, telefone, produto, boleto…",
                          help="Procura em clientes, orçamentos, contas a pagar, empréstimos, produtos e materiais. "
                               "Palavras em qualquer ordem, sem acento (ex.: 20t · mod 20t · flavio 9212 · cx quebra).")
    if not termo or len(bi.normalizar(termo)) < 2:
        return
    r = buscar(sb, termo)
    total = sum(len(v) for v in r.values())
    if not total:
        st.caption("Nada encontrado. Tente menos palavras ou só o começo delas.")
        return
    if r["servicos"]:
        st.caption("👤 Clientes e orçamentos")
        for reg in r["servicos"]:
            st.button(f"{_rotulo_status(reg.get('status_projeto'))} {reg.get('nome_cliente') or 'Sem nome'} · {utils.to_br_currency(reg.get('valor_venda_total') or 0)}",
                      key=f"bg_s_{reg['id']}", use_container_width=True, on_click=_ir_servico, args=(reg,),
                      help=f"{reg.get('status_projeto')} · {reg.get('telefone_cliente') or ''}")
    if r["boletos"]:
        st.caption("🧾 Contas a pagar")
        for b in r["boletos"]:
            try:
                venc = datetime.date.fromisoformat(str(b.get("vencimento"))[:10]).strftime("%d/%m")
            except Exception:
                venc = ""
            st.button(f"{b.get('cliente')} · {venc} · {utils.to_br_currency(b.get('valor') or 0)}",
                      key=f"bg_b_{b['id']}", use_container_width=True, on_click=_ir_documentos, args=("Boletos",))
    if r["emprestimos"]:
        st.caption("💸 Empréstimos a receber")
        for e in r["emprestimos"]:
            st.button(f"{e.get('pessoa')} · próx. {utils.to_br_currency(e.get('valor_parcela') or 0)}",
                      key=f"bg_e_{e['id']}", use_container_width=True, on_click=_ir_documentos, args=("Empréstimos",))
    if r["produtos"]:
        st.caption("☀️ Produtos (venda)")
        for p in r["produtos"]:
            st.markdown(f"<div class='eco-busca-item'>{p['item']}<b>{utils.to_br_currency(p.get('venda') or 0)}</b></div>",
                        unsafe_allow_html=True)
    if r["materiais"]:
        st.caption("🔧 Materiais (venda)")
        for m in r["materiais"]:
            st.markdown(f"<div class='eco-busca-item'>{m['item']}<b>{utils.to_br_currency(m['venda'])}/{m['unidade']}</b></div>",
                        unsafe_allow_html=True)
