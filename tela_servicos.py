import streamlit as st
import pandas as pd
import utils
from datetime import datetime

def renderizar():
    # Isso aqui serve para você ter certeza que o código novo carregou
    st.toast("Módulo de Serviços Carregado com Sucesso!", icon="🚀")
    st.markdown("## 🛠️ Gestão de Serviços e Orçamentos")
    
    supabase = st.session_state.supabase
    
    # 1. Carregar Dados de Serviços
    try:
        res = supabase.table('servicos_andamento').select('*').order('id', desc=True).execute()
        df_raw = pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Erro ao carregar dados do Supabase: {e}")
        return

    # 2. Carregar Catálogos (Equipamentos, Serviços, Terceirizados)
    # Forçamos o carregamento toda vez para garantir que os dados do banco venham
    try:
        p = utils.load_catalog('catalogo_produtos')
        s = utils.load_catalog('catalogo_servicos')
        o = utils.load_catalog('catalogo_outros')
        st.session_state.base_unificada = pd.concat([p, s, o], ignore_index=True)
    except Exception as e:
        st.error(f"Erro ao carregar catálogos de produtos: {e}")

    if df_raw.empty:
        st.info("Nenhum registro encontrado no banco de dados.")
        return

    # Filtro de Cancelados (50 dias)
    df_raw = df_raw[df_raw.apply(lambda r: not (r['status_projeto'] == 'Cancelado' and r['data_orcamento'] and (datetime.now().date() - pd.to_datetime(r['data_orcamento']).date()).days > 50), axis=1)]

    # Separação dos Grupos
    status_ativos = ['Em Andamento', 'Concluído PIX', 'Concluído CARTÃO']
    status_orcamentos = ['Orçamento Enviado', 'Em Negociação', 'Cancelado']

    df_ativos = df_raw[df_raw['status_projeto'].isin(status_ativos)].copy()
    df_orcamentos = df_raw[df_raw['status_projeto'].isin(status_orcamentos)].copy()

    col_cfg_v1 = {
        "nome_cliente": st.column_config.TextColumn("Cliente", width="medium"),
        "produtos_adquiridos": st.column_config.TextColumn("Resumo Itens", width="large"),
        "valor_venda_total": st.column_config.NumberColumn("Venda Total", format="R$ %,.2f"),
        "valor_custo_equipamentos": st.column_config.NumberColumn("Custo Total", format="R$ %,.2f"),
        "lucro_estimado": st.column_config.NumberColumn("Lucro Real", format="R$ %,.2f"),
        "instalador_responsavel": st.column_config.TextColumn("Instalador"),
    }

    # =========================================================================
    # PARTE SUPERIOR: SERVIÇOS EM ANDAMENTO
    # =========================================================================
    st.subheader("✅ Serviços em Andamento / Concluídos")
    if not df_ativos.empty:
        # Tabela Principal
        sel_ativo = st.dataframe(
            df_ativos[['nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 'valor_custo_equipamentos', 'lucro_estimado', 'instalador_responsavel']], 
            column_config=col_cfg_v1, 
            use_container_width=True, 
            hide_index=True, 
            on_select="rerun", 
            selection_mode="single-row"
        )
        
        # --- O SOMATÓRIO DE LUCRO QUE VOCÊ PEDIU ---
        lucro_total_ativos = df_ativos['lucro_estimado'].sum()
        st.markdown(f"""
            <div style="background-color: #e1effe; padding: 15px; border-radius: 10px; border-left: 5px solid #3f83f8; margin-top: 10px;">
                <span style="color: #1e429f; font-size: 1.1rem; font-weight: bold;">
                    💰 Lucro Estimado Acumulado (Serviços Ativos): {utils.to_br_currency(lucro_total_ativos)}
                </span>
            </div>
        """, unsafe_allow_html=True)
        
        if sel_ativo.selection.rows:
            exibir_detalhes_avancados(df_ativos.iloc[sel_ativo.selection.rows[0]], supabase)
    else: 
        st.write("_Sem serviços ativos._")

    st.markdown("<br><hr>", unsafe_allow_html=True)

    # =========================================================================
    # PARTE INFERIOR: ORÇAMENTOS
    # =========================================================================
    st.subheader("📝 Orçamentos e Negociações")
    if not df_orcamentos.empty:
        sel_orc = st.dataframe(
            df_orcamentos[['nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 'valor_custo_equipamentos', 'lucro_estimado', 'instalador_responsavel']], 
            column_config=col_cfg_v1, 
            use_container_width=True, 
            hide_index=True, 
            on_select="rerun", 
            selection_mode="single-row"
        )
        if sel_orc.selection.rows:
            exibir_detalhes_avancados(df_orcamentos.iloc[sel_orc.selection.rows[0]], supabase)
    else: 
        st.write("_Sem orçamentos pendentes._")

def exibir_detalhes_avancados(item, supabase):
    st.markdown(f"### 🔍 Detalhamento: {item['nome_cliente']}")
    
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            n_status = st.selectbox("Status Atual", 
                options=["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"],
                index=(["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"].index(item['status_projeto']) if item['status_projeto'] in ["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"] else 0)
            )
        with c2:
            n_inst = st.text_input("Instalador", value=item['instalador_responsavel'] if item['instalador_responsavel'] else "")
        with c3:
            n_v_inst = st.number_input("Pagamento Instalador (R$)", value=float(item['valor_pago_instalador'] if item['valor_pago_instalador'] else 0.0), format="%.2f")

        st.markdown("---")
        st.subheader("📋 Memória de Cálculo / Itens")

        # Dados para o editor
        if not item.get('detalhamento_itens') or item['detalhamento_itens'] == []:
            dados_itens = pd.DataFrame([
                {"Item": "OUTRO / MANUAL", "Descrição Manual": item['produtos_adquiridos'], "Qtd": 1, "Custo Un.": float(item['valor_custo_equipamentos']), "Venda Un.": float(item['valor_venda_total'])}
            ])
        else:
            dados_itens = pd.DataFrame(item['detalhamento_itens'])

        lista_opcoes = ["OUTRO / MANUAL"] + st.session_state.base_unificada['Item'].tolist()

        col_itens_cfg = {
            "Item": st.column_config.SelectboxColumn("Puxar do Banco", options=lista_opcoes, width="medium"),
            "Descrição Manual": st.column_config.TextColumn("Descrição (Livre)", width="large"),
            "Qtd": st.column_config.NumberColumn("Qtd", min_value=1, default=1),
            "Custo Un.": st.column_config.NumberColumn("Custo Un.", format="R$ %,.2f"),
            "Lucro Un.": st.column_config.NumberColumn("Lucro Un.", format="R$ %,.2f", disabled=True),
            "Venda Un.": st.column_config.NumberColumn("Venda Un.", format="R$ %,.2f"),
            "Lucro Total": st.column_config.NumberColumn("Lucro Total", format="R$ %,.2f", disabled=True),
        }

        # Editor de Itens
        df_edit = st.data_editor(dados_itens, column_config=col_itens_cfg, num_rows="dynamic", use_container_width=True, key=f"editor_{item['id']}")

        # Lógica de preenchimento automático
        for i in range(len(df_edit)):
            nome_sel = df_edit.iloc[i]['Item']
            if nome_sel != "OUTRO / MANUAL" and df_edit.iloc[i]['Custo Un.'] == 0:
                match = st.session_state.base_unificada[st.session_state.base_unificada['Item'] == nome_sel]
                if not match.empty:
                    df_edit.at[i, 'Custo Un.'] = float(match['Custo (R$)'].values[0])
                    df_edit.at[i, 'Venda Un.'] = float(match['Venda (R$)'].values[0])
                    st.rerun()

        # Cálculos de Lucro
        df_edit['Lucro Un.'] = df_edit['Venda Un.'] - df_edit['Custo Un.']
        df_edit['Lucro Total'] = df_edit['Lucro Un.'] * df_edit['Qtd']

        total_venda = (df_edit['Venda Un.'] * df_edit['Qtd']).sum()
        total_custo = (df_edit['Custo Un.'] * df_edit['Qtd']).sum()
        lucro_final = total_venda - (total_custo + n_v_inst)

        st.markdown("#### Resumo Financeiro")
        r1, r2, r3 = st.columns(3)
        r1.metric("Venda Total", utils.to_br_currency(total_venda))
        r2.metric("Custo (Mat+Inst)", utils.to_br_currency(total_custo + n_v_inst))
        r3.metric("LUCRO LÍQUIDO", utils.to_br_currency(lucro_final))

        if st.button("💾 SALVAR PROJETO", type="primary", use_container_width=True):
            try:
                resumo = ", ".join([f"{int(r['Qtd'])}x {r['Item'] if r['Item'] != 'OUTRO / MANUAL' else r['Descrição Manual']}" for _, r in df_edit.iterrows()])
                supabase.table('servicos_andamento').update({
                    "status_projeto": n_status, "instalador_responsavel": n_inst, "valor_pago_instalador": n_v_inst,
                    "valor_venda_total": float(total_venda), "valor_custo_equipamentos": float(total_custo),
                    "lucro_estimado": float(lucro_final), "produtos_adquiridos": resumo,
                    "detalhamento_itens": df_edit.to_dict('records')
                }).eq('id', item['id']).execute()
                st.success("Salvo com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
