import streamlit as st
import pandas as pd
import datetime

@st.dialog("📅 Cronograma de Instalações", width="large")
def modal_cronograma(df_servicos, lista_instaladores):
    st.markdown("Organize a agenda da equipe. Apenas serviços **Em Andamento** são exibidos.")
    
    c1, c2 = st.columns([1, 1.5])
    filtro_inst = c1.selectbox("👷 Filtro por Instalador", ["TODOS"] + lista_instaladores)
    filtro_tempo = c2.radio("🗓️ Visão de Tempo", ["Todas as Datas", "Esta Semana", "Este Mês"], horizontal=True)
    
    # Filtra rigorosamente apenas o que está "Em Andamento"
    df_cron = df_servicos[df_servicos['status_projeto'] == 'Em Andamento'].copy()
    
    if df_cron.empty:
        st.info("🎉 Nenhum serviço com status 'Em Andamento' no momento.")
        return
        
    # Função para formatar a lista de itens vendidos com QUEBRA DE LINHA (\n)
    def formatar_equipamentos(itens):
        if not isinstance(itens, list): return ""
        arr = []
        for it in itens:
            qtd = float(it.get('Qtd', 0))
            nome = it.get('Item', '')
            if qtd > 0 and nome:
                arr.append(f"{int(qtd)}x {nome}")
        # O \n força o Streamlit a quebrar o texto em múltiplas linhas, aumentando a altura da célula
        return "\n".join(arr) 
        
    df_cron['Equipamentos'] = df_cron['detalhamento_itens'].apply(formatar_equipamentos)
    df_cron['Data Agendada'] = pd.to_datetime(df_cron['data_conclusao'], errors='coerce').dt.date
    
    # Puxa o valor da mão de obra salvo no serviço
    df_cron['Valor Instalação'] = pd.to_numeric(df_cron['custo_terceirizados'], errors='coerce').fillna(0.0)
    
    # Aplicação dos filtros do usuário
    if filtro_inst != "TODOS":
        df_cron = df_cron[df_cron['instalador'] == filtro_inst]
        
    hoje = datetime.date.today()
    if filtro_tempo == "Esta Semana":
        start_w = hoje - datetime.timedelta(days=hoje.weekday())
        end_w = start_w + datetime.timedelta(days=6)
        df_cron = df_cron[(df_cron['Data Agendada'] >= start_w) & (df_cron['Data Agendada'] <= end_w)]
    elif filtro_tempo == "Este Mês":
        df_cron = df_cron[pd.to_datetime(df_cron['Data Agendada']).dt.month == hoje.month]
        
    cols_mostrar = ['id', 'instalador', 'nome_cliente', 'Equipamentos', 'Valor Instalação', 'Data Agendada']
    df_edit = df_cron[cols_mostrar].sort_values('Data Agendada', na_position='last')
    
    if df_edit.empty:
        st.warning("Nenhum agendamento encontrado para os filtros selecionados.")
        return

    # Configuração visual das colunas da tabela editável
    cfg_colunas = {
        "id": None, # Esconde o ID do banco
        "instalador": st.column_config.SelectboxColumn("Instalador", options=lista_instaladores, width="medium"),
        "nome_cliente": st.column_config.TextColumn("Cliente", disabled=True, width="medium"),
        "Equipamentos": st.column_config.TextColumn("Equipamentos Vendidos", disabled=True, width="large"),
        "Valor Instalação": st.column_config.NumberColumn("Valor Instalação", format="R$ %.2f", disabled=True, width="small"),
        "Data Agendada": st.column_config.DateColumn("Data da Instalação", format="DD/MM/YYYY", width="medium")
    }
    
    st.markdown("---")
    df_final = st.data_editor(
        df_edit,
        column_config=cfg_colunas,
        use_container_width=True,
        hide_index=True,
        key="ed_cronograma_equipe"
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Gravar Novo Cronograma", type="primary", use_container_width=True):
        with st.spinner("Atualizando agenda..."):
            for idx, row in df_final.iterrows():
                id_bd = row['id']
                row_orig = df_edit[df_edit['id'] == id_bd].iloc[0]
                
                # Se mudou a data ou o instalador, disparamos a atualização no banco
                if row['Data Agendada'] != row_orig['Data Agendada'] or row['instalador'] != row_orig['instalador']:
                    payload = {}
                    if pd.notna(row['Data Agendada']):
                        payload['data_conclusao'] = row['Data Agendada'].strftime('%Y-%m-%d')
                    if str(row['instalador']).strip() and str(row['instalador']).lower() != 'nan':
                        payload['instalador'] = str(row['instalador'])
                        
                    st.session_state.supabase.table('servicos_andamento').update(payload).eq('id', int(id_bd)).execute()
            
            st.success("✅ Cronograma atualizado com sucesso!")
            st.rerun()
