import streamlit as st
import pandas as pd
import datetime
import utils

def formatar_tamanho(tamanho_bytes):
    try:
        tamanho = int(tamanho_bytes)
        if tamanho < 1024: return f"{tamanho} B"
        elif tamanho < 1024 * 1024: return f"{tamanho / 1024:.1f} KB"
        else: return f"{tamanho / (1024 * 1024):.1f} MB"
    except: return "Desconhecido"

def parse_drive_date(iso_str):
    """Converte a data do Google Drive para o fuso horário do Brasil"""
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        dt = dt - datetime.timedelta(hours=3) # Ajuste GMT-3 (Brasil)
        return dt.replace(tzinfo=None)
    except:
        return pd.NaT

def renderizar_aba(nome_principal, subpastas=None, is_imagens=False):
    path_atual = [nome_principal]
    
    # ==========================================
    # 1. CABEÇALHO DE FILTROS ALINHADO
    # ==========================================
    st.markdown("""
        <style>
        div[data-testid="stExpander"] details summary { padding-top: 0.5rem; padding-bottom: 0.5rem; }
        </style>
    """, unsafe_allow_html=True)

    if subpastas:
        c_sub, c_busca, c_data, c_up = st.columns([1.2, 1.5, 1.2, 1])
        with c_sub:
            # Pegamos o mês de hoje dinamicamente
            mes_agora = datetime.date.today().month
            nome_mes_agora = utils.meses_pt[mes_agora - 1]
            default_idx = subpastas.index(nome_mes_agora) if nome_mes_agora in subpastas else 0
            
            sub_sel = st.selectbox("Selecione a Pasta / Mês:", subpastas, index=default_idx, key=f"combo_mes_{nome_principal}")
            path_atual.append(sub_sel)
            
        with c_busca:
            termo_busca = st.text_input("🔍 Buscar por Nome...", key=f"busca_{nome_principal}").lower()
            
        with c_data:
            # --- NOVO SISTEMA DE FILTRO DE DATA ---
            filtro_tipo = st.selectbox("📅 Filtrar por Data", ["Todo o Período", "Hoje", "Últimos 30 dias", "Últimos 60 dias", "Últimos 90 dias", "Personalizado (Faixa)"], key=f"tipo_data_{nome_principal}")
            data_filtro = None
            if filtro_tipo == "Personalizado (Faixa)":
                # Inicializar com [] habilita a seleção de período (Início - Fim) nativamente
                data_filtro = st.date_input("Início e Fim:", value=[], key=f"data_pers_{nome_principal}")
                
        with c_up:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            with st.expander("📤 Upload Arquivos"):
                arquivos_enviados = st.file_uploader("Selecione", accept_multiple_files=True, key=f"up_{nome_principal}", label_visibility="collapsed")
                if arquivos_enviados and st.button("🚀 Enviar", key=f"btn_env_{nome_principal}", type="primary", use_container_width=True):
                    with st.spinner("Enviando para o Drive..."):
                        for arq in arquivos_enviados:
                            utils.upload_to_drive(arq, arq.name, arq.type, path_atual)
                    st.success("✅ Sucesso!")
                    st.rerun()
    else:
        c_busca, c_data, c_up = st.columns([2, 1.5, 1])
        with c_busca:
            termo_busca = st.text_input("🔍 Buscar por Nome...", key=f"busca_{nome_principal}").lower()
            
        with c_data:
            # --- NOVO SISTEMA DE FILTRO DE DATA ---
            filtro_tipo = st.selectbox("📅 Filtrar por Data", ["Todo o Período", "Hoje", "Últimos 30 dias", "Últimos 60 dias", "Últimos 90 dias", "Personalizado (Faixa)"], key=f"tipo_data_s_{nome_principal}")
            data_filtro = None
            if filtro_tipo == "Personalizado (Faixa)":
                data_filtro = st.date_input("Início e Fim:", value=[], key=f"data_pers_s_{nome_principal}")
                
        with c_up:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            with st.expander("📤 Upload Arquivos"):
                arquivos_enviados = st.file_uploader("Selecione", accept_multiple_files=True, key=f"up_s_{nome_principal}", label_visibility="collapsed")
                if arquivos_enviados and st.button("🚀 Enviar", key=f"btn_env_s_{nome_principal}", type="primary", use_container_width=True):
                    with st.spinner("Enviando para o Drive..."):
                        for arq in arquivos_enviados:
                            utils.upload_to_drive(arq, arq.name, arq.type, path_atual)
                    st.success("✅ Sucesso!")
                    st.rerun()

    st.markdown("---")
    
    # ==========================================
    # 2. BUSCA DE DADOS NO DRIVE E PREPARAÇÃO
    # ==========================================
    arquivos_brutos = utils.list_drive_files(path_atual)
    
    if not arquivos_brutos:
        st.info("Nenhum arquivo encontrado nesta pasta.")
        return

    dados_tabela = []
    for a in arquivos_brutos:
        dados_tabela.append({
            "Excluir": False,
            "ID": a['id'],
            "Nome": a['name'],
            "Data": parse_drive_date(a.get('createdTime', '')),
            "Tamanho": formatar_tamanho(a.get('size', 0)),
            "Link": a.get('webViewLink', '#')
        })
    
    df = pd.DataFrame(dados_tabela)

    # ==========================================
    # 3. APLICAÇÃO DOS FILTROS
    # ==========================================
    if termo_busca:
        df = df[df['Nome'].str.lower().str.contains(termo_busca)]
        
    # --- LÓGICA DE FILTRAGEM POR DATA ATUALIZADA ---
    hoje_filtro = datetime.date.today()
    if filtro_tipo == "Hoje":
        df = df[df['Data'].dt.date == hoje_filtro]
    elif filtro_tipo == "Últimos 30 dias":
        limite = hoje_filtro - datetime.timedelta(days=30)
        df = df[df['Data'].dt.date >= limite]
    elif filtro_tipo == "Últimos 60 dias":
        limite = hoje_filtro - datetime.timedelta(days=60)
        df = df[df['Data'].dt.date >= limite]
    elif filtro_tipo == "Últimos 90 dias":
        limite = hoje_filtro - datetime.timedelta(days=90)
        df = df[df['Data'].dt.date >= limite]
    elif filtro_tipo == "Personalizado (Faixa)" and data_filtro:
        if isinstance(data_filtro, (tuple, list)):
            if len(data_filtro) == 2:
                start_date, end_date = data_filtro
                df = df[(df['Data'].dt.date >= start_date) & (df['Data'].dt.date <= end_date)]
            elif len(data_filtro) == 1:
                df = df[df['Data'].dt.date == data_filtro[0]]
        else:
            df = df[df['Data'].dt.date == data_filtro]

    if df.empty:
        st.warning("Nenhum arquivo corresponde aos filtros selecionados.")
        return

    # ==========================================
    # 4. PAGINAÇÃO E CONTROLES
    # ==========================================
    itens_por_pagina = 100
    total_paginas = (len(df) - 1) // itens_por_pagina + 1
    
    col_view, col_pag = st.columns([7, 3])
    with col_view:
        modo_visao = "Lista"
        if is_imagens:
            modo_visao = st.radio("Visualização:", ["Lista", "Miniaturas"], horizontal=True, key=f"view_{nome_principal}", label_visibility="collapsed")
            
    with col_pag:
        if total_paginas > 1:
            pagina_atual = st.number_input("Página", min_value=1, max_value=total_paginas, value=1, key=f"pag_{nome_principal}")
        else:
            pagina_atual = 1

    inicio = (pagina_atual - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina
    df_pagina = df.iloc[inicio:fim].copy()

    # ==========================================
    # 5. RENDERIZAÇÃO DA TABELA / GALERIA
    # ==========================================
    
    if is_imagens and modo_visao == "Miniaturas":
        cols = st.columns(4)
        for i, row in df_pagina.reset_index(drop=True).iterrows():
            with cols[i % 4]:
                img_url = f"https://drive.google.com/uc?export=view&id={row['ID']}"
                
                st.markdown(f'''
                    <a href="{row['Link']}" target="_blank">
                        <div style="
                            height: 180px; 
                            background-image: url('{img_url}');
                            background-size: cover;
                            background-position: center;
                            border-radius: 8px;
                            border: 1px solid #ddd;
                            margin-bottom: 5px;
                            background-color: #f8f9fa;
                        "></div>
                    </a>
                    <p style='font-size:0.8rem; text-align:center; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;' title='{row['Nome']}'><b>{row['Nome']}</b></p>
                ''', unsafe_allow_html=True)
                
                if st.button("🗑️ Excluir", key=f"del_img_{row['ID']}", use_container_width=True):
                    utils.delete_drive_file(row['ID'])
                    st.rerun()
    else:
        df_editado = st.data_editor(
            df_pagina,
            column_config={
                "Excluir": st.column_config.CheckboxColumn("🗑️ Excluir", default=False),
                "ID": None, 
                "Nome": st.column_config.TextColumn("Nome do Arquivo", width="large"),
                "Data": st.column_config.DatetimeColumn("Data de Inclusão", format="DD/MM/YYYY - HH:mm"),
                "Tamanho": st.column_config.TextColumn("Tamanho", width="small"),
                "Link": st.column_config.LinkColumn("Acesso Rápido", display_text="👁️ Visualizar")
            },
            disabled=["Nome", "Data", "Tamanho", "Link"],
            hide_index=True,
            use_container_width=True,
            key=f"editor_{nome_principal}"
        )

        if df_editado is not None and not df_editado.empty:
            arquivos_para_apagar = df_editado[df_editado["Excluir"] == True]
            if not arquivos_para_apagar.empty:
                st.error(f"⚠️ Selecionou {len(arquivos_para_apagar)} arquivo(s) para excluir.")
                if st.button("🚨 Confirmar Exclusão", type="primary", key=f"conf_del_{nome_principal}"):
                    with st.spinner("Apagando..."):
                        for id_apagar in arquivos_para_apagar["ID"]:
                            utils.delete_drive_file(id_apagar)
                    st.success("Apagados com sucesso!")
                    st.rerun()

def renderizar():
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    abas = st.tabs(["📝 Orçamentos", "🤝 Contratos", "🧾 Boletos", "🖼️ Imagens", "📊 Notas Fiscais (NF)"])
    
    with abas[0]: 
        renderizar_aba("Orçamentos")
        
    with abas[1]: 
        renderizar_aba("Contratos")
        
    with abas[2]: 
        meses_boletos = utils.meses_pt + ["PAGOS"]
        renderizar_aba("Boletos", subpastas=meses_boletos)
        
    with abas[3]: 
        renderizar_aba("Imagens", subpastas=utils.meses_pt, is_imagens=True)
        
    with abas[4]: 
        renderizar_aba("Notas Fiscais", subpastas=utils.meses_pt)
