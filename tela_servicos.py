import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar():
    st.markdown("## 📋 Gestão de Serviços em Andamento (CRM)")
    
    supabase = st.session_state.supabase
    
    # ==========================================
    # 1. CARREGAMENTO DOS DADOS E TAXAS
    # ==========================================
    try:
        res_servicos = supabase.table('servicos_andamento').select("*").order("id", desc=True).execute()
        df_projetos = pd.DataFrame(res_servicos.data)
    except Exception as e:
        st.error(f"Erro ao carregar serviços: {e}")
        return

    if df_projetos.empty:
        st.info("Nenhum orçamento ou serviço encontrado no banco de dados.")
        return

    # Carrega as taxas cadastradas lá na tela de Configurações
    df_taxas = utils.load_taxas()

    # ==========================================
    # 2. SEPARAÇÃO DAS TABELAS
    # ==========================================
    status_ativos = ["Em Andamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO"]
    
    # Filtra quem está ativo e quem ainda é orçamento pendente/cancelado
    df_ativos = df_projetos[df_projetos['status_projeto'].isin(status_ativos)].reset_index(drop=True)
    df_orcamentos = df_projetos[~df_projetos['status_projeto'].isin(status_ativos)].reset_index(drop=True)

    colunas_exibicao = ['id', 'numero_orcamento', 'nome_cliente', 'status_projeto', 'valor_venda_total', 'data_conclusao']

    st.markdown("### 🚀 Serviços Ativos")
    st.caption("Projetos aprovados e em execução.")
    sel_ativos = st.dataframe(
        df_ativos[[c for c in colunas_exibicao if c in df_ativos.columns]],
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        key="tab_ativos"
    )

    st.markdown("---")
    st.markdown("### 📝 Orçamentos Pendentes")
    st.caption("Orçamentos enviados aguardando fechamento.")
    sel_orcamentos = st.dataframe(
        df_orcamentos[[c for c in colunas_exibicao if c in df_orcamentos.columns]],
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        key="tab_orcamentos"
    )

    # Identifica de qual tabela o usuário clicou na linha
    linha_sel = None
    if sel_ativos.selection.rows:
        linha_sel = df_ativos.iloc[sel_ativos.selection.rows[0]]
    elif sel_orcamentos.selection.rows:
        linha_sel = df_orcamentos.iloc[sel_orcamentos.selection.rows[0]]

    # ==========================================
    # 3. PAINEL DE FECHAMENTO
    # ==========================================
    if linha_sel is not None:
        st.markdown("---")
        st.markdown(f"### ⚙️ Fechamento do Projeto: **{linha_sel.get('nome_cliente', 'Cliente')}**")
        
        # --- MUDANÇA DE STATUS E DATA (BLINDADA) ---
        c1, c2 = st.columns(2)
        status_atual = linha_sel.get('status_projeto', 'Orçamento Enviado')
        opcoes_status = ["Orçamento Enviado", "Em Andamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO", "Cancelado"]
        
        novo_status = c1.selectbox("Status (Muda o projeto de tabela)", opcoes_status, index=opcoes_status.index(status_atual) if status_atual in opcoes_status else 0)
        
        # AQUI FOI CORRIGIDO O ERRO DE DATA (VALUEERROR):
        try:
            data_db = linha_sel.get('data_conclusao')
            data_ini = pd.to_datetime(data_db).date()
            if pd.isna(data_ini):
                data_ini = datetime.date.today()
        except:
            data_ini = datetime.date.today()
            
        nova_data = c2.date_input("Data de Conclusão", value=data_ini)

        # --- CÁLCULO DE CUSTO DOS PRODUTOS ---
        itens_json = linha_sel.get('detalhamento_itens', [])
        if isinstance(itens_json, list) and len(itens_json) > 0:
            df_itens = pd.DataFrame(itens_json)
        else:
            df_itens = pd.DataFrame(columns=['Item', 'Qtd', 'Venda Un.', 'Custo Un.'])
            
        # Garante as colunas para não dar erro
        for col in ['Custo Un.', 'Qtd', 'Venda Un.']:
            if col not in df_itens.columns:
                df_itens[col] = 0.0

        # Pega o custo dos equipamentos que foram salvos no orçamento
        df_itens['Custo Un.'] = pd.to_numeric(df_itens['Custo Un.'], errors='coerce').fillna(0.0)
        df_itens['Qtd'] = pd.to_numeric(df_itens['Qtd'], errors='coerce').fillna(0)
        custo_total_produtos = (df_itens['Custo Un.'] * df_itens['Qtd']).sum()

        st.info(f"📦 **Custo de Fábrica dos Equipamentos:** {utils.to_br_currency(custo_total_produtos)}")

        # --- SIMULADOR DE ABATIMENTO DE TAXAS ---
        st.markdown("#### 🧮 Abatimentos e Lucro Real")
        with st.container(border=True):
            # O Valor fechado já vem pronto do orçamento
            valor_venda = float(linha_sel.get('valor_venda_total', 0.0))
            
            # MARGEM INICIAL (Venda - Custo Equipamentos)
            margem_inicial
