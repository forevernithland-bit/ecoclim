"""🧾 Preparar NF do cliente — direto do painel de Serviços (aba Fiscal/Boletos).

Monta uma Nota Fiscal de produto no Gestão Click com os EQUIPAMENTOS do
serviço (detalhamento_itens salvo no banco), sempre em RASCUNHO
(envio_automatico 0 — ver gestao_click.criar_nota_fiscal_rascunho). Emitir é
um passo separado, com confirmação explícita.

Travas (regra combinada com o Breno — nunca chutar dado fiscal):
* item sem NCM no catálogo → bloqueia (preencher em Configurações/Catálogo);
* sem CPF/CNPJ, CEP ou número → bloqueia (a API recusa NF sem destinatário);
* item que não está no catálogo de produtos → avisa e só segue se a pessoa
  marcar que entendeu que ele fica de fora.

Materiais hidráulicos vendidos (vendas_materiais) NÃO entram aqui — eles têm a
NF própria em Estoque de Materiais → Vendas, pra nunca sair nota duplicada.

O id da NF fica em dados_contrato["nf_gc_id"] (merge, nunca sobrescreve o
resto do dados_contrato, que o contrato e o orçamento também usam).
"""
import unicodedata

import pandas as pd
import streamlit as st

import gestao_click
import utils


def _norm(t):
    t = unicodedata.normalize("NFD", str(t or "").strip().lower())
    return " ".join("".join(c for c in t if unicodedata.category(c) != "Mn").split())


def _f(v):
    try:
        x = float(v)
        return 0.0 if pd.isna(x) else x
    except Exception:
        return 0.0


def _digitos(t):
    return "".join(c for c in str(t or "") if c.isdigit())


def _gravar_dc(supabase, sid, novos):
    """Merge em dados_contrato (relê do banco na hora pra não perder nada)."""
    atual = (supabase.table("servicos_andamento").select("dados_contrato").eq("id", sid).execute().data or [{}])[0]
    dc = atual.get("dados_contrato") if isinstance(atual.get("dados_contrato"), dict) else {}
    dc = {**dc, **novos}
    for k, v in list(dc.items()):
        if v is None and k in novos:
            dc.pop(k, None)
    supabase.table("servicos_andamento").update({"dados_contrato": dc}).eq("id", sid).execute()


def _distribuir(itens, total_alvo):
    """Escala os valores unitários pra soma bater com total_alvo (2 casas).
    O resto de centavos é acertado mexendo poucos centavos no unitário de 1 ou
    2 itens (busca a combinação exata: qtd_a*Δa + qtd_b*Δb = resto)."""
    soma = sum(i["qtd"] * i["venda"] for i in itens)
    if soma <= 0:
        return itens
    fator = total_alvo / soma
    novos = [{**i, "venda": round(i["venda"] * fator, 2)} for i in itens]
    resto = round((total_alvo - sum(i["qtd"] * i["venda"] for i in novos)) * 100)
    if not resto:
        return novos
    qtds = [int(i["qtd"]) if float(i["qtd"]).is_integer() else 0 for i in novos]
    melhor = None
    for a in range(len(novos)):
        if qtds[a] and resto % qtds[a] == 0 and abs(resto // qtds[a]) <= 200:
            melhor = ((a, resto // qtds[a]),)
            break
    if not melhor:
        for a in range(len(novos)):
            for b in range(len(novos)):
                if a == b or not qtds[a] or not qtds[b]:
                    continue
                for da in range(-200, 201):
                    r = resto - qtds[a] * da
                    if r % qtds[b] == 0 and abs(r // qtds[b]) <= 200:
                        cand = ((a, da), (b, r // qtds[b]))
                        if not melhor or abs(da) + abs(r // qtds[b]) < sum(abs(d) for _, d in melhor):
                            melhor = cand
    for k, d in melhor or ():
        novos[k]["venda"] = round(novos[k]["venda"] + d / 100, 2)
    return novos


def _bloco_nf_existente(supabase, proj, nf_id, pk):
    chave_sit = f"nfsrv_sit_{nf_id}"
    if chave_sit not in st.session_state:
        try:
            st.session_state[chave_sit] = gestao_click.consultar_nota_fiscal(nf_id) or {}
        except gestao_click.GestaoClickError as e:
            st.session_state[chave_sit] = {"_erro": str(e)}
    d = st.session_state[chave_sit]
    situacao = d.get("situacao_nf") or ("?" if d.get("_erro") else "Em aberto")
    numero = d.get("numero_nf") or ""
    total = d.get("valor_total_nf")
    txt = f"🧾 **NF no Gestão Click** — ID {nf_id}"
    if numero:
        txt += f" · nº {numero}"
    if total:
        txt += f" · {utils.to_br_currency(_f(total))}"
    txt += f" · situação: **{situacao}**"
    (st.success if situacao == "Aprovada" else st.info)(txt)
    if d.get("_erro"):
        st.caption(f"Não consegui consultar a situação agora: {d['_erro']}")

    c1, c2, c3 = st.columns(3)
    if c1.button("🔄 Ver situação de novo", key=f"nfsrv_ref_{pk}", use_container_width=True):
        st.session_state.pop(chave_sit, None)
        st.rerun()
    if situacao != "Aprovada":
        with c2.popover("🚀 Emitir NF", use_container_width=True):
            st.warning("Emitir manda a nota pra SEFAZ — não dá pra desfazer (só cancelar depois). "
                       "Confira o rascunho no Gestão Click antes.")
            ok = st.checkbox("Conferi a nota no Gestão Click e quero emitir agora", key=f"nfsrv_okemit_{pk}")
            if st.button("Emitir de verdade", type="primary", disabled=not ok, key=f"nfsrv_emit_{pk}"):
                try:
                    gestao_click.emitir_nota_fiscal(nf_id)
                    st.session_state.pop(chave_sit, None)
                    st.success("Nota fiscal emitida!")
                    st.rerun()
                except gestao_click.GestaoClickError as e:
                    st.error(str(e))
        with c3.popover("↩️ Desvincular", use_container_width=True):
            st.caption("Use se você apagou esse rascunho lá no Gestão Click e quer preparar outro. "
                       "Não apaga nada no Gestão Click.")
            if st.button("Desvincular esta NF", key=f"nfsrv_desv_{pk}"):
                _gravar_dc(supabase, proj["id"], {"nf_gc_id": None})
                st.session_state.pop(chave_sit, None)
                st.rerun()


def render(supabase, projeto, prefix_key):
    sid = projeto.get("id")
    if not sid:
        return
    pk = f"{prefix_key}_{sid}"
    with st.container(border=True):
        st.markdown("##### 🧾 Nota Fiscal do cliente (Gestão Click)")
        # sempre do banco: o que vale é o que está SALVO, não a grade em edição
        reg = (supabase.table("servicos_andamento")
               .select("id,nome_cliente,telefone_cliente,cpf_cnpj_cliente,valor_venda_total,detalhamento_itens,dados_contrato")
               .eq("id", sid).execute().data or [{}])[0]
        dc = reg.get("dados_contrato") if isinstance(reg.get("dados_contrato"), dict) else {}

        if dc.get("nf_gc_id"):
            _bloco_nf_existente(supabase, reg, str(dc["nf_gc_id"]), pk)
            return

        chave_aberto = f"nfsrv_aberto_{pk}"
        if not st.session_state.get(chave_aberto):
            st.caption("Cria a NF dos equipamentos deste cliente como **rascunho** no Gestão Click "
                       "(nada é emitido sem você confirmar depois).")
            if st.button("🧾 Preparar NF", key=f"nfsrv_abrir_{pk}"):
                st.session_state[chave_aberto] = True
                st.rerun()
            return

        # ---- itens do serviço x catálogo -----------------------------------
        catalogo = supabase.table("catalogo_produtos").select("id,item,custo,venda,ncm,codigo_externo,codigo_barra").execute().data or []
        por_nome = {_norm(c["item"]): c for c in catalogo if c.get("item")}
        import catalogo_ajustes  # orçamento antigo com nome antigo do reservatório
        for _antigo, _novo in catalogo_ajustes.ALIAS_NOMES_ANTIGOS.items():
            if _norm(_novo) in por_nome:
                por_nome.setdefault(_antigo, por_nome[_norm(_novo)])
        itens, fora, sem_ncm = [], [], []
        for linha in reg.get("detalhamento_itens") or []:
            nome = str(linha.get("Item") or "").strip()
            qtd = _f(linha.get("Qtd"))
            if not nome or nome.lower() == "nan" or qtd <= 0:
                continue
            prod = por_nome.get(_norm(nome))
            if not prod:
                fora.append(nome)
                continue
            ncm = str(prod.get("ncm") or "").strip()
            if not ncm:
                sem_ncm.append(nome)
            itens.append({"prod": prod, "item": prod["item"], "qtd": qtd,
                          "venda": round(_f(linha.get("Venda Un.")), 2), "custo": round(_f(linha.get("Custo Un.")), 2), "ncm": ncm})

        if not itens and not fora:
            st.warning("Este serviço não tem equipamentos salvos (aba 🛠️ Equipamento/Serviços). Salve os itens primeiro.")
        soma_itens = round(sum(i["qtd"] * i["venda"] for i in itens), 2)
        total_venda = round(_f(reg.get("valor_venda_total")), 2)

        modo = "orc"
        if itens and total_venda > 0 and abs(total_venda - soma_itens) >= 0.01:
            escolha = st.radio(
                "Valores dos produtos na NF",
                [f"Como no orçamento (soma dos produtos: {utils.to_br_currency(soma_itens)})",
                 f"Distribuir o Valor da Venda total ({utils.to_br_currency(total_venda)}) nos produtos"],
                key=f"nfsrv_modo_{pk}",
                help="A segunda opção aumenta (ou diminui) o valor unitário de cada produto na mesma proporção, "
                     "pra a nota fechar no valor total do contrato.")
            modo = "orc" if escolha.startswith("Como") else "total"
        itens_nf = _distribuir(itens, total_venda) if modo == "total" else itens

        if itens_nf:
            st.dataframe(pd.DataFrame([{
                "Produto": i["item"], "Qtd": i["qtd"], "Valor un.": utils.to_br_currency(i["venda"]),
                "Total": utils.to_br_currency(i["qtd"] * i["venda"]), "NCM": i["ncm"] or "⚠️ falta",
            } for i in itens_nf]), use_container_width=True, hide_index=True)
            st.markdown(f"**Total da NF: {utils.to_br_currency(sum(i['qtd'] * i['venda'] for i in itens_nf))}**")

        aceitou_fora = True
        if fora:
            st.warning("Estes itens **não estão no Catálogo de Produtos** e ficariam FORA da NF: " + ", ".join(fora))
            aceitou_fora = st.checkbox("Entendi, preparar a NF sem esses itens", key=f"nfsrv_fora_{pk}")
        if sem_ncm:
            st.error("Sem NCM cadastrado — preencha em Configurações → Catálogo de Produtos antes (não chutamos NCM): "
                     + ", ".join(sem_ncm))

        # ---- destinatário ---------------------------------------------------
        st.markdown("**Destinatário**")
        c1, c2, c3 = st.columns([2, 1.2, 0.8])
        cpf = c1.text_input("CPF/CNPJ", value=str(dc.get("cpf") or reg.get("cpf_cnpj_cliente") or ""), key=f"nfsrv_cpf_{pk}")
        cep = c2.text_input("CEP", value=str(dc.get("cep") or ""), key=f"nfsrv_cep_{pk}")
        num = c3.text_input("Número", value=str(dc.get("num") or ""), key=f"nfsrv_num_{pk}")
        nome = str(dc.get("nome") or reg.get("nome_cliente") or "").strip()
        st.caption(f"Nome na nota: {nome or '—'} (vem dos dados do contrato / cadastro).")

        faltando = []
        if len(_digitos(cpf)) not in (11, 14):
            faltando.append("CPF/CNPJ válido")
        if len(_digitos(cep)) != 8:
            faltando.append("CEP")
        if not num.strip():
            faltando.append("número do endereço")
        if faltando:
            st.warning("Falta: " + ", ".join(faltando) + ".")

        bloqueado = bool(not itens_nf or sem_ncm or faltando or not aceitou_fora)
        b1, b2 = st.columns(2)
        if b1.button("✅ Criar rascunho no Gestão Click", type="primary", disabled=bloqueado,
                     key=f"nfsrv_criar_{pk}", use_container_width=True):
            try:
                with st.spinner("Preparando a nota no Gestão Click..."):
                    loja_id = gestao_click.buscar_loja_id()
                    cliente = gestao_click.buscar_cliente_por_cpf(cpf)
                    if not cliente:
                        cliente = gestao_click.criar_cliente(nome or "Sem nome", cpf.strip(), reg.get("telefone_cliente") or "")
                    gestao_click.atualizar_endereco_cliente(cliente["id"], cep, num.strip())
                    itens_api = []
                    for i in itens_nf:
                        produto_id = i["prod"].get("codigo_externo") or gestao_click.garantir_produto(
                            supabase, i["prod"], "catalogo_produtos")
                        itens_api.append({"produto_id": produto_id, "quantidade": i["qtd"], "valor_venda": i["venda"],
                                          "valor_custo": i["custo"], "ncm": i["ncm"]})
                    nf_id = gestao_click.criar_nota_fiscal_rascunho(loja_id, cliente["id"], itens_api)
                if not nf_id:
                    st.error("O Gestão Click não devolveu o número do rascunho — confira lá antes de tentar de novo.")
                else:
                    novos = {"nf_gc_id": str(nf_id)}
                    if not dc.get("cpf"):
                        novos["cpf"] = cpf.strip()
                    if not dc.get("cep"):
                        novos["cep"] = cep.strip()
                    if not dc.get("num"):
                        novos["num"] = num.strip()
                    _gravar_dc(supabase, sid, novos)
                    if not reg.get("cpf_cnpj_cliente"):
                        supabase.table("servicos_andamento").update({"cpf_cnpj_cliente": cpf.strip()}).eq("id", sid).execute()
                    st.session_state[chave_aberto] = False
                    st.success(f"Rascunho criado no Gestão Click (ID {nf_id}). Confira lá em Notas Fiscais → NF-e.")
                    st.rerun()
            except gestao_click.GestaoClickError as e:
                st.error(str(e))
        if b2.button("Cancelar", key=f"nfsrv_canc_{pk}", use_container_width=True):
            st.session_state[chave_aberto] = False
            st.rerun()
