import streamlit as st
import pandas as pd
import utils
from datetime import datetime

def renderizar():
    st.markdown("## 🛠️ Gestão de Serviços e Orçamentos")
    supabase = st.session_state.supabase
    agora = datetime.now()
    
    try:
        res = supabase.table('servicos_andamento').select('*').order('id', desc=True).execute()
        df_raw = pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Erro ao carregar dados do Supabase: {e}")
        return

    if df_raw.empty:
        st.info("Nenhum registro encontrado no banco de dados.")
        return

    # Tratamento de datas
    df_raw['data_orcamento'] = pd.to_datetime(df_raw['data_orcamento'], errors='coerce')
    df_raw['data_conclusao'] = pd.to_datetime(df_raw['data_conclusao'], errors='coerce')
    
    def determinar_aba(row):
        stt = row['status_projeto']
        if stt == 'Cancelado':
            if pd.notna(row['data_orcamento']) and (agora.date() - row['data_orcamento'].date()).days > 50: return 'Historico'
            return 'Ativo_Orcamento' 
        if stt in ['Concluído PIX', 'Concluído CARTÃO']:
            if pd.notna(row['data_conclusao']):
                if row['data_conclusao'].year < agora.year or (row['data_conclusao'].year == agora.year and row['data_conclusao'].month < agora.month): return 'Historico'
            return 'Ativo_Servico'
        if stt == 'Em Andamento': return 'Ativo_Servico'
        return 'Ativo_Orcamento'

    df_raw['Aba'] = df_raw.apply(determinar_aba, axis=1)

    df_ativos = df_raw[df_raw['Aba'] == 'Ativo_Servico'].copy()
    df_orcamentos = df_raw[df_raw['Aba'] == 'Ativo_Orcamento'].copy()
    df_historico = df_raw[df_raw['Aba'] == 'Historico'].copy()

    tab1, tab2 = st.tabs(["📊 Gestão Ativa", "📁 Histórico"])

    col_cfg_v1 = {
        "nome_cliente": "Cliente", 
        "produtos_adquiridos": "Resumo Itens", 
        "valor_venda_total": st.column_config.NumberColumn("Venda", format="R$ %,.2f"), 
        "lucro_estimado": st.column_config.NumberColumn("Lucro", format="R$ %,.2f"), 
        "status_projeto": "Status"
    }

    with tab1:
        st.subheader("✅ Serviços em Andamento / Concluídos (Mês)")
        if not df_ativos.empty:
            sel_ativo = st.dataframe(df_ativos[['nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 'lucro_estimado', 'status_projeto']], column_config=col_cfg_v1, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            if sel_ativo.selection.rows: exibir_detalhes_avancados(df_ativos.iloc[sel_ativo.selection.rows[0]], supabase)
        else: st.write("_Sem serviços ativos._")
        
        st.markdown("<br><hr>", unsafe_allow_html=True)

        st.subheader("📝 Orçamentos e Negociações")
        if not df_orcamentos.empty:
            sel_orc = st.dataframe(df_orcamentos[['nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 'lucro_estimado', 'status_projeto']], column_config=col_cfg_v1, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            if sel_orc.selection.rows: exibir_detalhes_avancados(df_orcamentos.iloc[sel_orc.selection.rows[0]], supabase)

    with tab2:
        st.subheader("📁 Histórico e Resultados")
        if not df_historico.empty:
            df_hist_concluidos = df_historico[df_historico['status_projeto'].isin(['Concluído PIX', 'Concluído CARTÃO'])].copy()
            if not df_hist_concluidos.empty:
                df_hist_concluidos['Mes_Ano'] = df_hist_concluidos['data_conclusao'].dt.strftime('%m/%Y')
                for mes in sorted(df_hist_concluidos['Mes_Ano'].unique(), reverse=True):
                    with st.expander(f"📅 Resultados de {mes}"):
                        df_mes = df_hist_concluidos[df_hist_concluidos['Mes_Ano'] == mes]
                        st.dataframe(df_mes[['nome_cliente', 'valor_venda_total', 'lucro_estimado']], use_container_width=True, hide_index=True)
                        st.markdown(f"#### 💰 Lucro Líquido: :green[{utils.to_br_currency(df_mes['lucro_estimado'].sum())}]")

def exibir_detalhes_avancados(item, supabase):
    st.markdown(f"---")
    st.markdown(f"### 🔍 Editando Projeto: {item['nome_cliente']}")
    
    # --- BUSCA TAXAS PARA CÁLCULOS ---
    if 'db_taxas' not in st.session_state:
        st.session_state.db_taxas = utils.load_taxas()
    taxas_df = st.session_state.db_taxas

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            n_status = st.selectbox("Status Atual", ["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"], index=["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"].index(item['status_projeto']), key=f"st_{item['id']}")
        with c2:
            n_inst = st.text_input("Instalador Responsável", value=item['instalador_responsavel'] or "", key=f"inst_{item['id']}")
        with c3:
            n_v_inst = st.number_input("Valor Pago Instalador (R$)", value=float(item['valor_pago_instalador'] or 0.0), format="%.2f", key=f"pago_{item['id']}")

        st.markdown("---")
        t1, t2, t3 = st.columns(3)
        
        # Lógica de Taxas e Pagamento
        opcoes_pagamento = ["Dinheiro / PIX (0.00%)"]
        mapa_pagamentos = {"Dinheiro / PIX (0.00%)": 0.0} 
        for _, row_taxa in taxas_df.iterrows():
            if "NF" not in str(row_taxa['Item']):
                desc = f"{row_taxa['Item']} ({float(row_taxa['Taxa (%)']):.2f}%)"
                opcoes_pagamento.append(desc)
                mapa_pagamentos[desc] = float(row_taxa['Taxa (%)'])
        
        metodo_salvo = item.get('metodo_pagamento') or 'Dinheiro / PIX'
        idx_pgto = next((i for i, opt in enumerate(opcoes_pagamento) if opt.startswith(metodo_salvo)), 0)
        
        with t1:
            n_pgto_sel = st.selectbox("Forma de Pagamento", options=opcoes_pagamento, index=idx_pgto, key=f"pgto_{item['id']}")
            taxa_cartao = mapa_pagamentos[n_pgto_sel]
            n_pgto_nome = n_pgto_sel.split(" (")[0]
        with t2:
            n_nf = st.radio("Emitir Nota Fiscal?", options=["Não", "Sim"], index=1 if item.get('nf_emitida') else 0, horizontal=True, key=f"nf_{item['id']}")
        with t3:
            n_comissao = st.number_input("Comissão de Repasse (%)", value=float(item.get('comissao_percentual') or 0.0), format="%.2f", key=f"com_{item['id']}")

        st.markdown("---")
        st.subheader("📋 Detalhamento dos Itens")

        # Gerencia o estado da tabela de itens
        key_state = f"dados_{item['id']}"
        if key_state not in st.session_state:
            if not item.get('detalhamento_itens'):
                st.session_state[key_state] = pd.DataFrame([{"Item": "Item do Orçamento", "Qtd": 1, "Custo Un.": float(item['valor_custo_equipamentos']), "Venda Un.": float(item['valor_venda_total'])}])
            else:
                st.session_state[key_state] = pd.DataFrame(item['detalhamento_itens'])
                
        df_edit = st.data_editor(st.session_state[key_state], num_rows="dynamic", use_container_width=True, key=f"ed_{item['id']}")

        # Cálculos Financeiros em Tempo Real
        df_edit['Venda Total'] = df_edit['Venda Un.'] * df_edit['Qtd']
        faturamento = df_edit['Venda Total'].sum()
        custo_materiais = (df_edit['Custo Un.'] * df_edit['Qtd']).sum()
        
        taxa_nf_val = float(taxas_df.loc[taxas_df['Item'].str.contains('NF', case=False), 'Taxa (%)'].values[0]) if n_nf == "Sim" else 0.0
        deducoes = faturamento * ((taxa_nf_val + taxa_cartao + n_comissao) / 100)
        lucro_liquido = faturamento - (custo_materiais + n_v_inst + deducoes)

        st.markdown("#### 📊 Resumo Financeiro do Projeto")
        r1, r2, r3 = st.columns(3)
        r1.metric("Faturamento Bruto", utils.to_br_currency(faturamento))
        r2.metric("Custos (Mat + Inst)", utils.to_br_currency(custo_materiais + n_v_inst))
        r3.metric("LUCRO LÍQUIDO", utils.to_br_currency(lucro_liquido))

        # --- BOTÕES DE AÇÃO ---
        st.markdown("<br>", unsafe_allow_html=True)
        col_btn_save, col_btn_del = st.columns([3, 1])

        with col_btn_save:
            if st.button("💾 SALVAR ALTERAÇÕES NO PROJETO", type="primary", use_container_width=True, key=f"sv_{item['id']}"):
                try:
                    # Resolve o problema do NaT e datas
                    dt_final = None
                    if n_status in ['Concluído PIX', 'Concluído CARTÃO']:
                        dt_final = datetime.now().date().isoformat()
                    
                    resumo = ", ".join([f"{int(r['Qtd'])}x {r['Item']}" for _, r in df_edit.iterrows()])
                    
                    supabase.table('servicos_andamento').update({
                        "status_projeto": n_status, 
                        "instalador_responsavel": n_inst, 
                        "valor_pago_instalador": n_v_inst,
                        "valor_venda_total": float(faturamento), 
                        "valor_custo_equipamentos": float(custo_materiais),
                        "lucro_estimado": float(lucro_liquido), 
                        "produtos_adquiridos": resumo,
                        "detalhamento_itens": df_edit.to_dict('records'),
                        "data_conclusao": dt_final,
                        "nf_emitida": True if n_nf == "Sim" else False,
                        "metodo_pagamento": n_pgto_nome,
                        "comissao_percentual": float(n_comissao)
                    }).eq('id', item['id']).execute()
                    
                    st.success("✅ Alterações salvas!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

        with col_btn_del:
            # BOTÃO DE EXCLUIR COM CONFIRMAÇÃO (POPOVER)
            with st.popover("🗑️ EXCLUIR", use_container_width=True):
                st.warning("Tem certeza? Esta ação não pode ser desfeita.")
                if st.button("CONFIRMAR EXCLUSÃO", type="primary", key=f"del_confirm_{item['id']}", use_container_width=True):
                    try:
                        supabase.table('servicos_andamento').delete().eq('id', item['id']).execute()
                        st.success("Projeto excluído com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao excluir: {e}")
