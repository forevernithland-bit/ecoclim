import streamlit as st
import pandas as pd
import urllib.parse
import utils

STATUS_NF_LABELS = {"nao_precisa": "Não precisa", "pendente": "⏳ Pendente", "emitida": "✅ Emitida"}
STATUS_NF_OPCOES = ["nao_precisa", "pendente", "emitida"]


def _carregar_catalogo(supabase):
    try:
        res = supabase.table('materiais_padrao').select('*').order('categoria').order('ordem').execute()
        return res.data or []
    except Exception:
        return []


def _itens_abaixo_minimo(catalogo):
    return [
        c for c in catalogo
        if float(c.get('estoque_minimo') or 0) > 0 and float(c.get('estoque_atual') or 0) < float(c.get('estoque_minimo') or 0)
    ]


def _texto_lista_compra(itens_compra):
    """Mesmo agrupamento por categoria do gerar_texto_lista_materiais, só que
    com título de compra pro fornecedor em vez de lista pro cliente."""
    por_categoria = {}
    for it in itens_compra:
        cat = it.get('categoria') if it.get('categoria') in utils.ORDEM_CATEGORIAS_MATERIAL else 'geral_hidraulico'
        por_categoria.setdefault(cat, []).append(it)
    blocos = []
    for cat in utils.ORDEM_CATEGORIAS_MATERIAL:
        lista = por_categoria.get(cat)
        if not lista:
            continue
        titulo = utils.NOMES_CATEGORIA_MATERIAL.get(cat, "Outros")
        ordenados = sorted(lista, key=lambda it: str(it.get('item', '')).lower())
        linhas = [f"{it.get('qtd', 1)} {it.get('item', '')}" for it in ordenados]
        blocos.append(f"*{titulo}*\n" + "\n".join(linhas))
    return "\n\n".join(["*Lista de Compras - Fornecedor*"] + blocos)


def _aba_catalogo(supabase, catalogo):
    st.caption("Preço de custo, margem, venda e estoque mínimo de cada material — o estoque mínimo é o que dispara o alerta de compra na aba 🛒 Compras.")
    if not catalogo:
        st.info("Catálogo vazio.")
        return

    df = pd.DataFrame(catalogo)
    cols = ['id', 'categoria', 'item', 'unidade', 'custo', 'margem_percentual', 'venda', 'estoque_minimo']
    for c in cols:
        if c not in df.columns:
            df[c] = 0
    df = df[cols]

    cfg = {
        "id": None,
        "categoria": st.column_config.TextColumn("Categoria", disabled=True),
        "item": st.column_config.TextColumn("Item", disabled=True),
        "unidade": st.column_config.TextColumn("Un.", disabled=True),
        "custo": st.column_config.NumberColumn("Custo", format="R$ %.2f"),
        "margem_percentual": st.column_config.NumberColumn("Margem %", format="%.1f %%"),
        "venda": st.column_config.NumberColumn("Venda", format="R$ %.2f"),
        "estoque_minimo": st.column_config.NumberColumn("Estoque Mínimo"),
    }
    df_edit = st.data_editor(df, column_config=cfg, hide_index=True, use_container_width=True, key="editor_catalogo_materiais")

    if st.button("💾 Salvar Catálogo", type="primary", key="btn_salvar_catalogo_materiais"):
        try:
            for _, row in df_edit.iterrows():
                supabase.table('materiais_padrao').update({
                    "custo": float(row['custo'] or 0),
                    "margem_percentual": float(row['margem_percentual'] or 0),
                    "venda": float(row['venda'] or 0),
                    "estoque_minimo": float(row['estoque_minimo'] or 0),
                }).eq('id', int(row['id'])).execute()
            st.success("Catálogo atualizado!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")


def _aba_estoque(catalogo):
    st.caption("Saldo atual de cada material — os itens abaixo do mínimo aparecem destacados aqui e na lista de compras automática.")
    if not catalogo:
        st.info("Catálogo vazio.")
        return

    abaixo = _itens_abaixo_minimo(catalogo)
    if abaixo:
        st.warning(f"⚠️ {len(abaixo)} item(ns) abaixo do estoque mínimo — veja a aba 🛒 Compras pra gerar o pedido.")
        df_abaixo = pd.DataFrame(abaixo)[['categoria', 'item', 'unidade', 'estoque_atual', 'estoque_minimo']]
        st.dataframe(df_abaixo, use_container_width=True, hide_index=True)
        st.markdown("---")

    st.markdown("##### Todos os itens")
    df_todos = pd.DataFrame(catalogo)[['categoria', 'item', 'unidade', 'estoque_atual', 'estoque_minimo']].sort_values(['categoria', 'item'])
    st.dataframe(df_todos, use_container_width=True, hide_index=True)


def _aba_compras(supabase, catalogo):
    st.markdown("##### 🛒 Lista de compras automática (estoque abaixo do mínimo)")
    abaixo = _itens_abaixo_minimo(catalogo)
    if abaixo:
        sugestoes = [{
            "item": c['item'],
            "qtd": max(float(c.get('estoque_minimo') or 0) - float(c.get('estoque_atual') or 0), 1),
        } for c in abaixo]
        df_sug = pd.DataFrame(sugestoes)[['item', 'qtd']]
        df_sug_edit = st.data_editor(df_sug, num_rows="dynamic", use_container_width=True, key="editor_lista_compra_auto")
        if st.button("📋 Gerar texto pro fornecedor", key="btn_gerar_texto_compra"):
            mapa_cat = {c['item']: c.get('categoria') for c in catalogo}
            itens_texto = [
                {"item": r['item'], "qtd": r['qtd'], "categoria": mapa_cat.get(r['item'])}
                for _, r in df_sug_edit.iterrows() if str(r['item']).strip()
            ]
            texto = _texto_lista_compra(itens_texto)
            st.code(texto, language=None)
            url_wa = "https://wa.me/?text=" + urllib.parse.quote(texto)
            st.markdown(f"[📤 Abrir no WhatsApp]({url_wa})")
    else:
        st.info("Nenhum item abaixo do estoque mínimo no momento.")

    st.markdown("---")
    st.markdown("##### 📥 Registrar Compra do Fornecedor")
    st.caption("Atualiza o custo, recalcula o preço de venda pela margem configurada (se houver) e soma a quantidade comprada ao estoque. Também é como você cadastra o estoque inicial real, quando for fazer isso.")

    fornecedor = st.text_input("Fornecedor", key="compra_fornecedor")
    opcoes_item = {f"{c['item']} ({c.get('categoria', '')})": c for c in catalogo}
    _itens_compra_key = "itens_compra_materiais"
    if _itens_compra_key not in st.session_state:
        st.session_state[_itens_compra_key] = []

    col_sel, col_add = st.columns([3, 1])
    item_sel = col_sel.selectbox("Adicionar item", ["-- escolher --"] + list(opcoes_item.keys()), key="sel_item_compra")
    if col_add.button("➕ Adicionar", key="btn_add_item_compra", disabled=(item_sel == "-- escolher --")):
        c = opcoes_item[item_sel]
        st.session_state[_itens_compra_key].append({
            "item": c['item'], "qtd": 1, "custo_unitario_novo": float(c.get('custo') or 0),
        })
        st.rerun()

    if st.session_state[_itens_compra_key]:
        df_compra = pd.DataFrame(st.session_state[_itens_compra_key])
        df_compra_edit = st.data_editor(
            df_compra, num_rows="dynamic", use_container_width=True,
            key=f"editor_compra_materiais_{len(st.session_state[_itens_compra_key])}",
        )
        observacao = st.text_area("Observação (opcional)", key="compra_observacao")
        if st.button("💾 Registrar Compra", type="primary", key="btn_registrar_compra"):
            itens_final = df_compra_edit.dropna(subset=['item']).to_dict('records')
            if not itens_final:
                st.warning("Adicione pelo menos um item.")
            else:
                try:
                    mapa_material = {c['item']: c for c in catalogo}
                    custo_total_compra = 0.0
                    compra_itens_registro = []
                    for it in itens_final:
                        mat = mapa_material.get(it['item'])
                        qtd = float(it.get('qtd') or 0)
                        if not mat or qtd <= 0:
                            continue
                        novo_custo = float(it.get('custo_unitario_novo') or 0)
                        margem = float(mat.get('margem_percentual') or 0)
                        nova_venda = round(novo_custo * (1 + margem / 100), 2) if margem > 0 else float(mat.get('venda') or 0)
                        novo_estoque = float(mat.get('estoque_atual') or 0) + qtd
                        supabase.table('materiais_padrao').update({
                            "custo": novo_custo, "venda": nova_venda, "estoque_atual": novo_estoque,
                        }).eq('id', mat['id']).execute()
                        custo_total_compra += novo_custo * qtd
                        compra_itens_registro.append({"item": it['item'], "qtd": qtd, "custo_unitario_novo": novo_custo, "_material_id": mat['id']})

                    res_compra = supabase.table('compras_materiais').insert({
                        "fornecedor": fornecedor.strip() or None,
                        "itens": [{k: v for k, v in i.items() if k != "_material_id"} for i in compra_itens_registro],
                        "custo_total": custo_total_compra,
                        "observacao": observacao.strip() or None,
                    }).execute()
                    compra_id = res_compra.data[0]['id']

                    for it in compra_itens_registro:
                        supabase.table('estoque_movimentos').insert({
                            "material_id": it['_material_id'], "tipo": "entrada_compra",
                            "quantidade": it['qtd'], "custo_unitario_na_epoca": it['custo_unitario_novo'],
                            "referencia_id": compra_id,
                        }).execute()

                    st.success("Compra registrada! Custo, venda e estoque atualizados.")
                    st.session_state[_itens_compra_key] = []
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao registrar compra: {e}")
    else:
        st.caption("Nenhum item adicionado ainda.")


def _aba_vendas(supabase):
    st.caption("Histórico de materiais vendidos aos clientes (via botão \"💰 Adquirir materiais com a Ecoclim\" dentro do serviço em andamento).")
    try:
        res = supabase.table('vendas_materiais').select('*').order('criado_em', desc=True).execute()
        vendas = res.data or []
    except Exception:
        vendas = []

    if not vendas:
        st.info("Nenhuma venda de material registrada ainda.")
        return

    total_venda = sum(float(v.get('venda_total') or 0) for v in vendas)
    total_custo = sum(float(v.get('custo_total') or 0) for v in vendas)
    total_lucro = sum(float(v.get('lucro_total') or 0) for v in vendas)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Vendido", utils.to_br_currency(total_venda))
    c2.metric("Total Custo", utils.to_br_currency(total_custo))
    c3.metric("Lucro Total", utils.to_br_currency(total_lucro))
    st.markdown("---")

    for v in vendas:
        with st.container(border=True):
            data_fmt = ""
            try:
                data_fmt = pd.to_datetime(v.get('criado_em')).strftime('%d/%m/%Y %H:%M')
            except Exception:
                pass
            st.markdown(f"**{v.get('cliente_nome') or 'Sem nome'}** — {data_fmt}")

            itens_v = v.get('itens') or []
            if itens_v:
                df_v = pd.DataFrame(itens_v)
                cols_v = [c for c in ['item', 'qtd', 'custo_unitario', 'venda_unitario', 'estoque_insuficiente'] if c in df_v.columns]
                st.dataframe(df_v[cols_v] if cols_v else df_v, use_container_width=True, hide_index=True)

            cc1, cc2, cc3 = st.columns(3)
            cc1.metric("Venda", utils.to_br_currency(v.get('venda_total')))
            cc2.metric("Custo", utils.to_br_currency(v.get('custo_total')))
            cc3.metric("Lucro", utils.to_br_currency(v.get('lucro_total')))

            status_atual = v.get('status_nf', 'nao_precisa')
            status_novo = st.selectbox(
                "Nota Fiscal", STATUS_NF_OPCOES,
                index=STATUS_NF_OPCOES.index(status_atual) if status_atual in STATUS_NF_OPCOES else 0,
                format_func=lambda s: STATUS_NF_LABELS[s],
                key=f"status_nf_{v['id']}",
            )
            if status_novo != status_atual:
                try:
                    supabase.table('vendas_materiais').update({"status_nf": status_novo}).eq('id', v['id']).execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

            with st.expander("📋 Copiar dados pra Nota Fiscal"):
                linhas_nf = [
                    f"{it.get('qtd')}x {it.get('item')} — {utils.to_br_currency(it.get('venda_unitario'))} un. — total {utils.to_br_currency((it.get('qtd') or 0) * (it.get('venda_unitario') or 0))}"
                    for it in itens_v
                ]
                texto_nf = (
                    f"Venda de materiais — {v.get('cliente_nome') or 'Sem nome'}\n"
                    + "\n".join(linhas_nf)
                    + f"\n\nTotal: {utils.to_br_currency(v.get('venda_total'))}"
                )
                st.code(texto_nf, language=None)


def renderizar():
    st.markdown("## 📦 Estoque de Materiais")
    st.caption("Preço, estoque e vendas de materiais hidráulicos — separado da lista simples que só é enviada pro cliente/depósito sem custo pra Ecoclim.")

    supabase = st.session_state.supabase
    catalogo = _carregar_catalogo(supabase)

    aba_cat, aba_estoque, aba_compras, aba_vendas = st.tabs(["📋 Catálogo & Preços", "📦 Estoque Atual", "🛒 Compras", "💰 Vendas de Materiais"])
    with aba_cat:
        _aba_catalogo(supabase, catalogo)
    with aba_estoque:
        _aba_estoque(catalogo)
    with aba_compras:
        _aba_compras(supabase, catalogo)
    with aba_vendas:
        _aba_vendas(supabase)
