import streamlit as st
import pandas as pd
import utils
from datetime import datetime

def renderizar():
    st.markdown("## 🛠️ Gestão de Serviços e Orçamentos")
    
    supabase = st.session_state.supabase
    
    # 1. Carregar Dados de Serviços
    try:
        res = supabase.table('servicos_andamento').select('*').order('id', desc=True).execute()
        df_raw = pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    # 2. Carregar Catálogos para busca (Equipamentos, Serviços, Terceirizados)
    if 'db_p_serv' not in st.session_state:
        p = utils.load_catalog('catalogo_produtos')
        s = utils.load_catalog('catalogo_servicos')
        o = utils.load_catalog('catalogo_outros')
        # Criamos uma base unificada para consulta de preços e custos
        st.session_state.base_unificada = pd.concat([p, s, o], ignore_index=True)

    if df_raw.empty:
        st.info("Nenhum registro encontrado.")
        return

    # Filtro de Cancelados (50 dias)
    df_raw = df_raw[df_raw.apply(lambda r: not (r['status_projeto'] == 'Cancelado' and r['data_orcamento'] and (datetime.now().date() - pd.to_datetime(r['data_orcamento']).date()).days > 50), axis=1)]

    # Separação dos Grupos
    status_ativos = ['Em Andamento', 'Concluído PIX', 'Concluído CARTÃO']
    status_orcamentos = ['Orçamento Enviado', 'Em Negociação', 'Cancelado']

    df_ativos = df_raw[df_raw['status_projeto'].isin(status_ativos)].copy()
    df_orcamentos = df_raw[df_raw['status_projeto'].isin(status_orcamentos)].copy()

    colunas_rapidas = ['nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 'valor_custo_equipamentos', 'lucro_estimado', 'instalador_responsavel']
    
    col_cfg = {
        "nome_cliente": st.column_config.TextColumn("Cliente", width="medium"),
        "produtos_adquiridos": st.column_config.TextColumn("Resumo Itens", width="medium"),
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
        sel_ativo = st.dataframe(df_ativos[colunas_rapidas], column_config=col_cfg, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        
        # Métrica de Lucro Estimado de Serviços Ativos (Soma apenas dos ativos)
        lucro_total_ativos = df_ativos['lucro_estimado'].sum()
        st.markdown(f"**💰 Lucro Estimado Acumulado (Serviços Ativos):** :blue[{utils.to_br_currency(lucro_total_ativos)}]")
        
        if sel_ativo.selection.rows:
            exibir_detalhes_avancados(df_ativos.iloc[sel_ativo.selection.rows[0]], supabase)
    else: st.write("_Sem serviços ativos._")

    st.markdown("<br><hr>", unsafe_allow_html=True)

    # =========================================================================
    # PARTE INFERIOR: ORÇAMENTOS
    # =========================================================================
    st.subheader("📝 Orçamentos e Negociações")
    if not df_orcamentos.empty:
        sel_orc = st.dataframe(df_orcamentos[colunas_rapidas], column_config=col_cfg, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if sel_orc.selection.rows:
            exibir_detalhes_avancados(df_orcamentos.iloc[sel_orc.selection.rows[0]], supabase)
    else: st.write("_Sem orçamentos pendentes._")

def exibir_detalhes_avancados(item, supabase):
    st.markdown(f"### 🔍 Gerenciar Projeto: {item['nome_cliente']}")
    
    with st.container(border=True):
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            n_status = st.selectbox("Status Atual", 
                options=["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"],
                index=(["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"].index(item['status_projeto']) if item['status_projeto'] in ["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"] else 0)
            )
        with c2:
            n_inst = st.text_input("Técnico / Instalador", value=item['instalador_responsavel'] if item['instalador_responsavel'] else "")
        with c3:
            n_v_inst = st.number_input("Valor Pago ao Instalador (R$)", value=float(item['valor_pago_instalador'] if item['valor_pago_instalador'] else 0.0), format="%.2f")

        st.markdown("---")
        st.subheader("📋 Composição e Memória de Cálculo")

        # Preparar dados para o editor
        if not item.get('detalhamento_itens') or item['detalhamento_itens'] == []:
            dados_itens = pd.DataFrame([
                {"Item": "OUTRO / MANUAL", "Descrição Manual": item['produtos_adquiridos'], "Qtd": 1, "Custo Un.": float(item['valor_custo_equipamentos']), "Venda Un.": float(item['valor_venda_total'])}
            ])
        else:
            dados_itens = pd.DataFrame(item['detalhamento_itens'])

        # Lista de itens do banco para o selectbox
        lista_opcoes = ["OUTRO / MANUAL"] + st.session_state.base_unificada['Item'].tolist()

        col_itens_cfg = {
            "Item": st.column_config.SelectboxColumn("Puxar do Banco", options=lista_opcoes, width="medium"),
            "Descrição Manual": st.column_config.TextColumn("Descrição/Aditivo (Se 'OUTRO')", width="large"),
            "Qtd": st.column_config.NumberColumn("Qtd", min_value=1, default=1, width="small"),
            "Custo Un.": st.column_config.NumberColumn("Custo Un.", format="R$ %,.2f"),
            "Lucro Un.": st.column_config.NumberColumn("Lucro Un.", format="R$ %,.2f", disabled=True),
            "Venda Un.": st.column_config.NumberColumn("Venda Un.", format="R$ %,.2f"),
            "Lucro Total": st.column_config.NumberColumn("Lucro Total", format="R$ %,.2f", disabled=True),
        }

        df_itens_edit = st.data_editor(dados_itens, column_config=col_itens_cfg, num_rows="dynamic", use_container_width=True, key=f"ed_v2_{item['id']}")

        # --- LÓGICA DE AUTO-PREENCHIMENTO E CÁLCULO DE LUCRO ---
        for i in range(len(df_itens_edit)):
            linha = df_itens_edit.iloc[i]
            nome_sel = linha['Item']
            
            # Se selecionou algo do banco e os valores estão zerados, puxamos os dados
            if nome_sel != "OUTRO / MANUAL" and linha['Custo Un.'] == 0:
                match = st.session_state.base_unificada[st.session_state.base_unificada['Item'] == nome_sel]
                if not match.empty:
                    df_itens_edit.at[i, 'Custo Un.'] = float(match['Custo (R$)'].values[0])
                    df_itens_edit.at[i, 'Venda Un.'] = float(match['Venda (R$)'].values[0])
                    st.rerun()

        # Cálculos de Lucro por Linha
        df_itens_edit['Lucro Un.'] = df_itens_edit['Venda Un.'] - df_itens_edit['Custo Un.']
        df_itens_edit['Lucro Total'] = df_itens_edit['Lucro Un.'] * df_itens_edit['Qtd']

        # Totais Gerais do Serviço
        total_venda = (df_itens_edit['Venda Un.'] * df_itens_edit['Qtd']).sum()
        total_custo_mat = (df_itens_edit['Custo Un.'] * df_itens_edit['Qtd']).sum()
        lucro_projeto = total_venda - (total_custo_mat + n_v_inst)

        st.markdown("#### Resumo do Serviço")
        res1, res2, res3 = st.columns(3)
        res1.metric("Faturamento", utils.to_br_currency(total_venda))
        res2.metric("Custo Total", utils.to_br_currency(total_custo_mat + n_v_inst))
        res3.metric("LUCRO LÍQUIDO", utils.to_br_currency(lucro_projeto))

        if st.button("💾 SALVAR PROJETO", type="primary", use_container_width=True):
            try:
                # Gera resumo para a tabela principal
                resumo = []
                for _, r in df_itens_edit.iterrows():
                    desc = r['Item'] if r['Item'] != "OUTRO / MANUAL" else r['Descrição Manual']
                    resumo.append(f"{int(r['Qtd'])}x {desc}")
                
                supabase.table('servicos_andamento').update({
                    "status_projeto": n_status,
                    "instalador_responsavel": n_inst,
                    "valor_pago_instalador": n_v_inst,
                    "valor_venda_total": float(total_venda),
                    "valor_custo_equipamentos": float(total_custo_mat),
                    "lucro_estimado": float(lucro_projeto),
                    "produtos_adquiridos": ", ".join(resumo),
                    "detalhamento_itens": df_itens_edit.to_dict('records')
                }).eq('id', item['id']).execute()
                
                st.success("Salvo!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")
