import streamlit as st
import pandas as pd
import utils
from datetime import datetime

def renderizar():
    st.markdown("## 🛠️ Gestão de Serviços e Orçamentos")
    
    supabase = st.session_state.supabase
    agora = datetime.now()
    
    # 1. Carregar Dados do Banco
    try:
        res = supabase.table('servicos_andamento').select('*').order('id', desc=True).execute()
        df_raw = pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Erro ao carregar dados do Supabase: {e}")
        return

    # 2. Carregar Catálogos de Produtos
    try:
        if 'base_unificada' not in st.session_state:
            p = utils.load_catalog('catalogo_produtos')
            s = utils.load_catalog('catalogo_servicos')
            o = utils.load_catalog('catalogo_outros')
            st.session_state.base_unificada = pd.concat([p, s, o], ignore_index=True)
    except Exception as e:
        st.warning("Aviso: Base de produtos não pôde ser carregada.")

    if df_raw.empty:
        st.info("Nenhum registro encontrado no banco de dados.")
        return

    # Tratamento de Datas para a Lógica de Abas
    df_raw['data_orcamento'] = pd.to_datetime(df_raw['data_orcamento'], errors='coerce')
    df_raw['data_conclusao'] = pd.to_datetime(df_raw['data_conclusao'], errors='coerce')
    
    # --- LÓGICA DE SEPARAÇÃO (ATIVA vs HISTÓRICO) ---
    def determinar_aba(row):
        status = row['status_projeto']
        
        # 1. Cancelados com mais de 50 dias vão para o Histórico
        if status == 'Cancelado':
            if pd.notna(row['data_orcamento']) and (agora.date() - row['data_orcamento'].date()).days > 50:
                return 'Historico'
            return 'Ativo_Orcamento' 
            
        # 2. Concluídos: Só vão pro Histórico se o mês/ano atual for maior que o mês/ano da conclusão
        if status in ['Concluído PIX', 'Concluído CARTÃO']:
            if pd.notna(row['data_conclusao']):
                if row['data_conclusao'].year < agora.year or (row['data_conclusao'].year == agora.year and row['data_conclusao'].month < agora.month):
                    return 'Historico'
            return 'Ativo_Servico'
            
        # 3. Em Andamento (Ficam sempre na Gestão Ativa)
        if status == 'Em Andamento':
            return 'Ativo_Servico'
            
        # 4. Orçamentos pendentes
        return 'Ativo_Orcamento'

    df_raw['Aba'] = df_raw.apply(determinar_aba, axis=1)

    df_ativos = df_raw[df_raw['Aba'] == 'Ativo_Servico'].copy()
    df_orcamentos = df_raw[df_raw['Aba'] == 'Ativo_Orcamento'].copy()
    df_historico = df_raw[df_raw['Aba'] == 'Historico'].copy()

    # --- ESTRUTURA VISUAL DE ABAS ---
    tab1, tab2 = st.tabs(["📊 Gestão Ativa", "📁 Histórico (Concluídos e Cancelados)"])

    col_cfg_v1 = {
        "nome_cliente": st.column_config.TextColumn("Cliente", width="medium"),
        "produtos_adquiridos": st.column_config.TextColumn("Resumo Itens", width="large"),
        "valor_venda_total": st.column_config.NumberColumn("Venda Total", format="R$ %,.2f"),
        "valor_custo_equipamentos": st.column_config.NumberColumn("Custo Total", format="R$ %,.2f"),
        "lucro_estimado": st.column_config.NumberColumn("Lucro Real", format="R$ %,.2f"),
        "instalador_responsavel": st.column_config.TextColumn("Instalador"),
    }

    # ==========================================
    # ABA 1: GESTÃO ATIVA (DIA A DIA)
    # ==========================================
    with tab1:
        st.subheader("✅ Serviços em Andamento / Concluídos (Mês Atual)")
        if not df_ativos.empty:
            sel_ativo = st.dataframe(
                df_ativos[['nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 'valor_custo_equipamentos', 'lucro_estimado', 'instalador_responsavel']], 
                column_config=col_cfg_v1, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row"
            )
            
            lucro_total_ativos = df_ativos['lucro_estimado'].sum()
            st.markdown(f"**💰 Lucro Estimado Acumulado (Serviços Ativos):** :blue[{utils.to_br_currency(lucro_total_ativos)}]")
            
            if sel_ativo.selection.rows:
                exibir_detalhes_avancados(df_ativos.iloc[sel_ativo.selection.rows[0]], supabase)
        else: 
            st.write("_Sem serviços ativos neste momento._")

        st.markdown("<br><hr>", unsafe_allow_html=True)

        st.subheader("📝 Orçamentos e Negociações")
        if not df_orcamentos.empty:
            sel_orc = st.dataframe(
                df_orcamentos[['nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 'valor_custo_equipamentos', 'lucro_estimado', 'instalador_responsavel']], 
                column_config=col_cfg_v1, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row"
            )
            if sel_orc.selection.rows:
                exibir_detalhes_avancados(df_orcamentos.iloc[sel_orc.selection.rows[0]], supabase)
        else: 
            st.write("_Sem orçamentos pendentes._")

    # ==========================================
    # ABA 2: HISTÓRICO E CONTROLE FINANCEIRO
    # ==========================================
    with tab2:
        st.subheader("📁 Histórico de Serviços e Controle de Lucro Mensal")
        
        if df_historico.empty:
            st.info("Nenhum serviço antigo concluído ou orçamento cancelado (com mais de 50 dias) para exibir.")
        else:
            df_hist_concluidos = df_historico[df_historico['status_projeto'].isin(['Concluído PIX', 'Concluído CARTÃO'])].copy()
            df_hist_cancelados = df_historico[df_historico['status_projeto'] == 'Cancelado'].copy()
            
            if not df_hist_concluidos.empty:
                st.markdown("### 🏆 Lucro Consolidado por Mês")
                df_hist_concluidos['Mes_Ano'] = df_hist_concluidos['data_conclusao'].dt.strftime('%m/%Y')
                
                meses = df_hist_concluidos['Mes_Ano'].unique()
                # Mostra o mês mais recente primeiro
                for mes in sorted(meses, reverse=True):
                    with st.expander(f"📅 Resultados de {mes}", expanded=True):
                        df_mes = df_hist_concluidos[df_hist_concluidos['Mes_Ano'] == mes]
                        st.dataframe(
                            df_mes[['nome_cliente', 'produtos_adquiridos', 'valor_venda_total', 'lucro_estimado']],
                            column_config=col_cfg_v1, use_container_width=True, hide_index=True
                        )
                        lucro_mes = df_mes['lucro_estimado'].sum()
                        st.markdown(f"#### 💰 Lucro Líquido do Mês: :green[{utils.to_br_currency(lucro_mes)}]")
            
            if not df_hist_cancelados.empty:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("### 🚫 Orçamentos Cancelados (+50 dias)")
                with st.expander("Ver Lista de Cancelados"):
                    st.dataframe(
                        df_hist_cancelados[['nome_cliente', 'produtos_adquiridos', 'valor_venda_total']],
                        use_container_width=True, hide_index=True
                    )

def exibir_detalhes_avancados(item, supabase):
    st.markdown(f"### 🔍 Detalhamento: {item['nome_cliente']}")
    
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            n_status = st.selectbox("Status Atual", 
                options=["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"],
                index=(["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"].index(item['status_projeto']) if item['status_projeto'] in ["Orçamento Enviado", "Em Negociação", "Em Andamento", "Concluído PIX", "Concluído CARTÃO", "Cancelado"] else 0),
                key=f"status_{item['id']}"
            )
        with c2:
            n_inst = st.text_input("Instalador", value=item['instalador_responsavel'] if item['instalador_responsavel'] else "", key=f"inst_{item['id']}")
        with c3:
            n_v_inst = st.number_input("Pagamento Instalador (R$)", value=float(item['valor_pago_instalador'] if item['valor_pago_instalador'] else 0.0), format="%.2f", key=f"pago_inst_{item['id']}")

        st.markdown("---")
        st.subheader("📋 Memória de Cálculo / Itens Adquiridos")

        # Gerencia o estado local dos itens para cálculos em tempo real
        key_state = f"dados_itens_{item['id']}"
        if key_state not in st.session_state:
            if not item.get('detalhamento_itens') or item['detalhamento_itens'] == []:
                st.session_state[key_state] = pd.DataFrame([
                    {"Item": "OUTRO / MANUAL", "Descrição Manual": item['produtos_adquiridos'], "Qtd": 1, "Custo Un.": float(item['valor_custo_equipamentos']), "Venda Un.": float(item['valor_venda_total']), "Lucro Un.": 0.0, "Lucro Total": 0.0}
                ])
            else:
                st.session_state[key_state] = pd.DataFrame(item['detalhamento_itens'])
                
        df_atual = st.session_state[key_state]
        
        # Garante as colunas novas
        for col in ["Lucro Un.", "Lucro Total"]:
            if col not in df_atual.columns:
                df_atual[col] = 0.0

        lista_opcoes = ["OUTRO / MANUAL"] + st.session_state.base_unificada['Item'].tolist()

        col_itens_cfg = {
            "Item": st.column_config.SelectboxColumn("Puxar do Banco", options=lista_opcoes, width="medium"),
            "Descrição Manual": st.column_config.TextColumn("Descrição", width="medium"),
            "Qtd": st.column_config.NumberColumn("Qtd", min_value=1),
            "Custo Un.": st.column_config.NumberColumn("Custo Un. (R$)", format="R$ %,.2f"),
            "Venda Un.": st.column_config.NumberColumn("Venda Un. (R$)", format="R$ %,.2f"),
            "Lucro Un.": st.column_config.NumberColumn("Lucro Un. (R$)", format="R$ %,.2f", disabled=True),
            "Lucro Total": st.column_config.NumberColumn("Lucro Total (R$)", format="R$ %,.2f", disabled=True),
        }

        # O Editor Dataframe
        df_edit = st.data_editor(df_atual, column_config=col_itens_cfg, num_rows="dynamic", use_container_width=True, key=f"editor_{item['id']}")

        # Lógica de Preenchimento Automático e Cálculo de Lucro
        precisa_atualizar = False
        for i in range(len(df_edit)):
            nome_sel = df_edit.iloc[i]['Item']
            # Se selecionou algo do banco e os preços estão vazios
            if nome_sel != "OUTRO / MANUAL" and df_edit.iloc[i]['Custo Un.'] == 0 and df_edit.iloc[i]['Venda Un.'] == 0:
                match = st.session_state.base_unificada[st.session_state.base_unificada['Item'] == nome_sel]
                if not match.empty:
                    df_edit.at[i, 'Custo Un.'] = float(match['Custo (R$)'].values[0])
                    df_edit.at[i, 'Venda Un.'] = float(match['Venda (R$)'].values[0])
                    precisa_atualizar = True

        # Cálculos de Lucro das colunas invisíveis
        df_edit['Custo Un.'] = df_edit['Custo Un.'].astype(float)
        df_edit['Venda Un.'] = df_edit['Venda Un.'].astype(float)
        df_edit['Qtd'] = df_edit['Qtd'].astype(int)
        
        df_edit['Lucro Un.'] = df_edit['Venda Un.'] - df_edit['Custo Un.']
        df_edit['Lucro Total'] = df_edit['Lucro Un.'] * df_edit['Qtd']

        # Se puxou do banco, força a tela a piscar para mostrar os preços
        if precisa_atualizar:
            st.session_state[key_state] = df_edit
            st.rerun()

        # Atualiza a memória
        st.session_state[key_state] = df_edit

        # Totais para os botões e painel
        total_venda = df_edit['Venda Un.'].multiply(df_edit['Qtd']).sum()
        total_custo = df_edit['Custo Un.'].multiply(df_edit['Qtd']).sum()
        lucro_final = total_venda - (total_custo + n_v_inst)

        st.markdown("#### Resumo Financeiro do Projeto")
        r1, r2, r3 = st.columns(3)
        r1.metric("Venda Total", utils.to_br_currency(total_venda))
        r2.metric("Custo (Material + Instalador)", utils.to_br_currency(total_custo + n_v_inst))
        r3.metric("LUCRO LÍQUIDO FINAL", utils.to_br_currency(lucro_final))

        # Botão de Salvar
        if st.button("💾 SALVAR PROJETO", type="primary", use_container_width=True, key=f"btn_salvar_{item['id']}"):
            try:
                # 1. Monta o resumo dos produtos vendidos
                resumo = ", ".join([f"{int(r['Qtd'])}x {r['Item'] if r['Item'] != 'OUTRO / MANUAL' else r['Descrição Manual']}" for _, r in df_edit.iterrows()])
                
                # 2. Controla a Data de Conclusão para a Virada de Mês
                data_conclusao = item['data_conclusao']
                if n_status in ['Concluído PIX', 'Concluído CARTÃO'] and item['status_projeto'] not in ['Concluído PIX', 'Concluído CARTÃO']:
                    # Se foi marcado hoje, registra a data de hoje!
                    data_conclusao = datetime.now().date().isoformat()
                elif n_status not in ['Concluído PIX', 'Concluído CARTÃO']:
                    data_conclusao = None
                
                update_data = {
                    "status_projeto": n_status, 
                    "instalador_responsavel": n_inst, 
                    "valor_pago_instalador": n_v_inst,
                    "valor_venda_total": float(total_venda), 
                    "valor_custo_equipamentos": float(total_custo),
                    "lucro_estimado": float(lucro_final), 
                    "produtos_adquiridos": resumo,
                    "detalhamento_itens": df_edit.to_dict('records')
                }
                
                if data_conclusao:
                    update_data["data_conclusao"] = data_conclusao
                elif data_conclusao is None and pd.notna(item.get('data_conclusao')):
                    update_data["data_conclusao"] = None
                    
                supabase.table('servicos_andamento').update(update_data).eq('id', item['id']).execute()
                
                # Limpa o cache local para atualizar
                if key_state in st.session_state:
                    del st.session_state[key_state]
                    
                st.success("Salvo com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
