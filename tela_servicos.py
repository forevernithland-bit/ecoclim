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

    try:
        if 'base_unificada' not in st.session_state:
            st.session_state.base_unificada = pd.concat([utils.load_catalog('catalogo_produtos'), utils.load_catalog('catalogo_servicos'), utils.load_catalog('catalogo_outros')], ignore_index=True)
        if 'db_taxas' not in st.session_state:
            st.session_state.db_taxas = utils.load_taxas()
    except: pass

    if df_raw.empty:
        st.info("Nenhum registro encontrado no banco de dados.")
        return

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

    tab1, tab2 = st.tabs(["📊 Gestão Ativa", "📁 Histórico (Concluídos e Cancelados)"])

    col_cfg_v1 = {"nome_cliente": "Cliente", "produtos_adquiridos": "Resumo Itens", "valor_venda_total": st.column_config.NumberColumn("Venda", format="R$ %,.2f"), "lucro_estimado": st.column_config.NumberColumn("Lucro", format="R$ %,.2f"), "status_projeto": "Status"}

    with tab1:
        st.subheader("✅ Serviços em Andamento / Concluídos (Mês Atual)")
        if not df_ativos.empty:
            sel_ativo = st.dataframe(df_ativos[['nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 'lucro_estimado', 'status_projeto']], column_config=col_cfg_v1, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            st.markdown(f"**💰 Lucro Estimado Acumulado:** :blue[{utils.to_br_currency(df_ativos['lucro_estimado'].sum())}]")
            if sel_ativo.selection.rows: exibir_detalhes_avancados(df_ativos.iloc[sel_ativo.selection.rows[0]], supabase)
        
        st.markdown("<br><hr>", unsafe_allow_html=True)

        st.subheader("📝 Orçamentos e Negociações")
        if not df_orcamentos.empty:
            sel_orc = st.dataframe(df_orcamentos[['nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 'lucro_estimado', 'status_projeto']], column_config=col_cfg_v1, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            if sel_orc.selection.rows: exibir_detalhes_avancados(df_orcamentos.iloc[sel_orc.selection.rows[0]], supabase)

    with tab2:
        st.subheader("📁 Histórico e Lucro Mensal")
        if not df_historico.empty:
            df_hist_concluidos = df_historico[df_historico['status_projeto'].isin(['Concluído PIX', 'Concluído CARTÃO'])].copy()
            if not df_hist_concluidos.empty:
                df_hist_concluidos['Mes_Ano'] = df_hist_concluidos['data_conclusao'].dt.strftime('%m/%Y')
                for mes in sorted(df_hist_concluidos['Mes_Ano'].unique(), reverse=True):
                    with st.expander(f"📅 Resultados de {mes}"):
                        df_mes = df_hist_concluidos[df_hist_concluidos['Mes_Ano'] == mes]
                        st.dataframe(df_mes[['nome_cliente', 'valor_venda_total', 'lucro_estimado']], use_container_width=True, hide_index=True)
                        st.markdown(f"#### 💰 Lucro Líquido do Mês: :green[{utils.to_br_currency(df_mes['lucro_estimado'].sum())}]")

def exibir_detalhes_avancados(item, supabase):
    st.markdown(f"### 🔍 Projeto: {item['nome_cliente']}")
    
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            n_status = st.selectbox("Status Atual", ["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"], index=["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"].index(item['status_projeto']), key=f"st_{item['id']}")
        with c2:
            n_inst = st.text_input("Instalador", value=item['instalador_responsavel'] or "", key=f"inst_{item['id']}")
        with c3:
            n_v_inst = st.number_input("Pago ao Instalador (R$)", value=float(item['valor_pago_instalador'] or 0.0), format="%.2f", key=f"pago_{item['id']}")

        # --- NOVA SEÇÃO: IMPOSTOS E TAXAS ---
        st.markdown("---")
        t1, t2 = st.columns(2)
        
        # Opções de pagamento filtradas do banco de taxas (tirando a NF)
        taxas_df = st.session_state.db_taxas
        opcoes_pagamento = ["Dinheiro / PIX"] + [t for t in taxas_df['Item'].tolist() if "NF" not in t]
        
        with t1:
            n_pgto = st.selectbox("Forma de Pagamento", options=opcoes_pagamento, index=opcoes_pagamento.index(item.get('metodo_pagamento', 'Dinheiro / PIX')) if item.get('metodo_pagamento') in opcoes_pagamento else 0, key=f"pgto_{item['id']}")
        with t2:
            n_nf = st.radio("Emitir Nota Fiscal?", options=["Não", "Sim"], index=1 if item.get('nf_emitida') else 0, horizontal=True, key=f"nf_{item['id']}")

        st.markdown("---")
        st.subheader("📋 Memória de Cálculo / Itens Adquiridos")

        key_state = f"dados_{item['id']}"
        if key_state not in st.session_state:
            if not item.get('detalhamento_itens') or item['detalhamento_itens'] == []:
                st.session_state[key_state] = pd.DataFrame([{"Item": "OUTRO / MANUAL", "Descrição Manual": item['produtos_adquiridos'], "Qtd": 1, "Custo Un.": float(item['valor_custo_equipamentos']), "Venda Un.": float(item['valor_venda_total']), "Venda Total": float(item['valor_venda_total']), "Lucro Un.": 0.0, "Lucro Total": 0.0}])
            else:
                st.session_state[key_state] = pd.DataFrame(item['detalhamento_itens'])
                
        df_atual = st.session_state[key_state]
        for col in ["Venda Total", "Lucro Un.", "Lucro Total"]:
            if col not in df_atual.columns: df_atual[col] = 0.0

        col_itens_cfg = {
            "Item": st.column_config.SelectboxColumn("Puxar do Banco", options=["OUTRO / MANUAL"] + st.session_state.base_unificada['Item'].tolist(), width="medium"),
            "Descrição Manual": st.column_config.TextColumn("Descrição", width="medium"),
            "Qtd": st.column_config.NumberColumn("Qtd", min_value=1),
            "Custo Un.": st.column_config.NumberColumn("Custo Un.", format="R$ %,.2f"),
            "Venda Un.": st.column_config.NumberColumn("Venda Un.", format="R$ %,.2f"),
            "Venda Total": st.column_config.NumberColumn("Venda Total", format="R$ %,.2f", disabled=True),
            "Lucro Un.": st.column_config.NumberColumn("Lucro Un.", format="R$ %,.2f", disabled=True),
            "Lucro Total": st.column_config.NumberColumn("Lucro Total", format="R$ %,.2f", disabled=True),
        }

        df_edit = st.data_editor(df_atual, column_config=col_itens_cfg, num_rows="dynamic", use_container_width=True, key=f"ed_{item['id']}")

        # Cálculos de Linha (Com a Venda Total e Lucro Total arrumados)
        precisa_atualizar = False
        for i in range(len(df_edit)):
            if df_edit.iloc[i]['Item'] != "OUTRO / MANUAL" and df_edit.iloc[i]['Custo Un.'] == 0:
                match = st.session_state.base_unificada[st.session_state.base_unificada['Item'] == df_edit.iloc[i]['Item']]
                if not match.empty:
                    df_edit.at[i, 'Custo Un.'] = float(match['Custo (R$)'].values[0])
                    df_edit.at[i, 'Venda Un.'] = float(match['Venda (R$)'].values[0])
                    precisa_atualizar = True

        df_edit['Qtd'] = df_edit['Qtd'].astype(int)
        df_edit['Venda Total'] = df_edit['Venda Un.'] * df_edit['Qtd']
        df_edit['Lucro Un.'] = df_edit['Venda Un.'] - df_edit['Custo Un.']
        df_edit['Lucro Total'] = df_edit['Lucro Un.'] * df_edit['Qtd']

        if precisa_atualizar:
            st.session_state[key_state] = df_edit; st.rerun()

        st.session_state[key_state] = df_edit

        # --- CÁLCULOS FINANCEIROS FINAIS ---
        faturamento_bruto = df_edit['Venda Total'].sum()
        custo_materiais = (df_edit['Custo Un.'] * df_edit['Qtd']).sum()
        
        # 1. Calcular Imposto da NF
        taxa_nf_pct = 0.0
        if n_nf == "Sim":
            try: taxa_nf_pct = float(taxas_df.loc[taxas_df['Item'].str.contains('NF', case=False), 'Taxa (%)'].values[0])
            except: taxa_nf_pct = 6.0
        valor_nf = faturamento_bruto * (taxa_nf_pct / 100)
        
        # 2. Calcular Taxa do Cartão
        taxa_cartao_pct = 0.0
        if n_pgto != "Dinheiro / PIX":
            try: taxa_cartao_pct = float(taxas_df.loc[taxas_df['Item'] == n_pgto, 'Taxa (%)'].values[0])
            except: taxa_cartao_pct = 0.0
        valor_cartao = faturamento_bruto * (taxa_cartao_pct / 100)

        total_taxas = valor_nf + valor_cartao
        lucro_final_liquido = faturamento_bruto - (custo_materiais + n_v_inst + total_taxas)

        st.markdown("#### Resultado do Projeto")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Faturamento", utils.to_br_currency(faturamento_bruto))
        r2.metric("Materiais + Inst.", utils.to_br_currency(custo_materiais + n_v_inst))
        r3.metric(f"Taxas (NF + {n_pgto})", utils.to_br_currency(total_taxas))
        r4.metric("LUCRO LÍQUIDO", utils.to_br_currency(lucro_final_liquido))

        if st.button("💾 SALVAR PROJETO", type="primary", use_container_width=True, key=f"sv_{item['id']}"):
            try:
                resumo = ", ".join([f"{int(r['Qtd'])}x {r['Item'] if r['Item'] != 'OUTRO / MANUAL' else r['Descrição Manual']}" for _, r in df_edit.iterrows()])
                
                dt_conclusao = item['data_conclusao']
                if n_status in ['Concluído PIX', 'Concluído CARTÃO'] and item['status_projeto'] not in ['Concluído PIX', 'Concluído CARTÃO']:
                    dt_conclusao = datetime.now().date().isoformat()
                
                supabase.table('servicos_andamento').update({
                    "status_projeto": n_status, "instalador_responsavel": n_inst, "valor_pago_instalador": n_v_inst,
                    "valor_venda_total": float(faturamento_bruto), "valor_custo_equipamentos": float(custo_materiais),
                    "lucro_estimado": float(lucro_final_liquido), "produtos_adquiridos": resumo,
                    "detalhamento_itens": df_edit.to_dict('records'),
                    "data_conclusao": str(dt_conclusao) if dt_conclusao else None,
                    "nf_emitida": True if n_nf == "Sim" else False,
                    "metodo_pagamento": n_pgto,
                    "valor_taxas_impostos": float(total_taxas)
                }).eq('id', item['id']).execute()
                
                if key_state in st.session_state: del st.session_state[key_state]
                st.success("Salvo com sucesso!"); st.rerun()
            except Exception as e: st.error(f"Erro: {e}")
