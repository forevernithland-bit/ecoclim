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

    # Tratamento de datas com erro 'coerce' para evitar falhas de formato
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
        else: st.write("_Sem serviços ativos._")
        
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

        st.markdown("---")
        t1, t2, t3 = st.columns(3)
        
        taxas_df = st.session_state.db_taxas
        opcoes_pagamento_com_taxa = ["Dinheiro / PIX (0.00%)"]
        mapa_pagamentos = {"Dinheiro / PIX (0.00%)": 0.0} 
        
        for _, row_taxa in taxas_df.iterrows():
            if "NF" not in str(row_taxa['Item']):
                desc_taxa = f"{row_taxa['Item']} ({float(row_taxa['Taxa (%)']):.2f}%)"
                opcoes_pagamento_com_taxa.append(desc_taxa)
                mapa_pagamentos[desc_taxa] = float(row_taxa['Taxa (%)'])
        
        metodo_salvo = item.get('metodo_pagamento') or 'Dinheiro / PIX'
        idx_pgto = 0
        for i, opt in enumerate(opcoes_pagamento_com_taxa):
            if opt.startswith(metodo_salvo):
                idx_pgto = i
                break
        
        with t1:
            n_pgto_selecionado = st.selectbox("Forma de Pagamento", options=opcoes_pagamento_com_taxa, index=idx_pgto, key=f"pgto_{item['id']}")
            n_pgto = n_pgto_selecionado.split(" (")[0] 
            taxa_cartao_pct = mapa_pagamentos[n_pgto_selecionado]
        with t2:
            n_nf = st.radio("Emitir Nota Fiscal?", options=["Não", "Sim"], index=1 if item.get('nf_emitida') else 0, horizontal=True, key=f"nf_{item['id']}")
        with t3:
            n_comissao = st.number_input("Comissão Repasse (%)", value=float(item.get('comissao_percentual') or 0.0), format="%.2f", key=f"com_{item['id']}")

        st.markdown("---")
        st.subheader("📋 Memória de Cálculo / Itens Adquiridos")

        key_state = f"dados_{item['id']}"
        if key_state not in st.session_state:
            if not item.get('detalhamento_itens') or item['detalhamento_itens'] == []:
                st.session_state[key_state] = pd.DataFrame([{"Item": "OUTRO / MANUAL", "Descrição Manual": item['produtos_adquiridos'], "Qtd": 1, "Custo Un.": float(item['valor_custo_equipamentos']), "Venda Un.": float(item['valor_venda_total']), "Venda Total": float(item['valor_venda_total']), "Lucro Un.": 0.0, "Lucro Total": 0.0}])
            else:
                st.session_state[key_state] = pd.DataFrame(item['detalhamento_itens'])
                
        df_edit = st.data_editor(st.session_state[key_state], num_rows="dynamic", use_container_width=True, key=f"ed_{item['id']}")

        # Lógica de preenchimento e cálculos
        df_edit['Qtd'] = pd.to_numeric(df_edit['Qtd'], errors='coerce').fillna(1).astype(int)
        df_edit['Custo Un.'] = pd.to_numeric(df_edit['Custo Un.'], errors='coerce').fillna(0.0).astype(float)
        df_edit['Venda Un.'] = pd.to_numeric(df_edit['Venda Un.'], errors='coerce').fillna(0.0).astype(float)
        
        # ... cálculos de lucro por linha ...
        df_edit['Venda Total'] = df_edit['Venda Un.'] * df_edit['Qtd']
        df_edit['Lucro Un.'] = df_edit['Venda Un.'] - df_edit['Custo Un.']
        df_edit['Lucro Total'] = df_edit['Lucro Un.'] * df_edit['Qtd']

        # Totais gerais
        faturamento_bruto = df_edit['Venda Total'].sum()
        custo_materiais = (df_edit['Custo Un.'] * df_edit['Qtd']).sum()
        
        # Impostos e Taxas
        taxa_nf_pct = float(taxas_df.loc[taxas_df['Item'].str.contains('NF', case=False), 'Taxa (%)'].values[0]) if n_nf == "Sim" else 0.0
        valor_nf = faturamento_bruto * (taxa_nf_pct / 100)
        valor_cartao = faturamento_bruto * (taxa_cartao_pct / 100)
        valor_comissao = faturamento_bruto * (n_comissao / 100)
        total_deducoes = valor_nf + valor_cartao + valor_comissao
        lucro_final_liquido = faturamento_bruto - (custo_materiais + n_v_inst + total_deducoes)

        st.markdown("#### 📊 Resultado Detalhado do Projeto")
        r1, r2, r3 = st.columns(3)
        r1.metric("Faturamento", utils.to_br_currency(faturamento_bruto))
        r2.metric("Materiais + Serviço", utils.to_br_currency(custo_materiais + n_v_inst))
        r3.metric("LUCRO LÍQUIDO", utils.to_br_currency(lucro_final_liquido))

        if st.button("💾 SALVAR DADOS DO PROJETO", type="primary", use_container_width=True, key=f"sv_{item['id']}"):
            try:
                resumo = ", ".join([f"{int(r['Qtd'])}x {r['Item'] if r['Item'] != 'OUTRO / MANUAL' else r['Descrição Manual']}" for _, r in df_edit.iterrows()])
                
                # --- CORREÇÃO DO ERRO NaT ---
                # Pegamos a data atual do banco
                data_concl_db = item['data_conclusao']
                
                # Se mudou para concluído agora e antes não era, bota data de hoje
                if n_status in ['Concluído PIX', 'Concluído CARTÃO'] and item['status_projeto'] not in ['Concluído PIX', 'Concluído CARTÃO']:
                    dt_final = datetime.now().date().isoformat()
                # Se já era concluído, mantém a data que estava (evitando NaT)
                elif n_status in ['Concluído PIX', 'Concluído CARTÃO'] and pd.notna(data_concl_db):
                    dt_final = pd.to_datetime(data_concl_db).date().isoformat()
                # Caso contrário, nulo
                else:
                    dt_final = None

                supabase.table('servicos_andamento').update({
                    "status_projeto": n_status, 
                    "instalador_responsavel": n_inst, 
                    "valor_pago_instalador": n_v_inst,
                    "valor_venda_total": float(faturamento_bruto), 
                    "valor_custo_equipamentos": float(custo_materiais),
                    "lucro_estimado": float(lucro_final_liquido), 
                    "produtos_adquiridos": resumo,
                    "detalhamento_itens": df_edit.to_dict('records'),
                    "data_conclusao": dt_final, # Enviando dt_final limpo
                    "nf_emitida": True if n_nf == "Sim" else False,
                    "metodo_pagamento": n_pgto,
                    "valor_taxas_impostos": float(total_deducoes),
                    "comissao_percentual": float(n_comissao)
                }).eq('id', item['id']).execute()
                
                if key_state in st.session_state: del st.session_state[key_state]
                st.success("Salvo com sucesso!"); st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")
