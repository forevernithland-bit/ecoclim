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

def renderizar_aba(nome_principal, subpastas=None):
    path_atual = [nome_principal]
    
    # ==========================================
    # 1. CABEÇALHO DE FILTROS E UPLOAD
    # ==========================================
    col_pesquisa, col_data, col_up = st.columns([1.5, 1.5, 1])
    
    with col_pesquisa:
        if subpastas:
            sub_sel = st.selectbox("Selecione a Pasta / Mês:", subpastas, key=f"sel_{nome_principal}")
            path_atual.append(sub_sel)
        
        termo_busca = st.text_input(f"🔍 Buscar por Nome em {nome_principal}...", key=f"busca_{nome_principal}").lower()

    with col_data:
        # Espaçamento para alinhar caso não tenha o selectbox de subpastas
        if not subpastas: st.markdown("<br>", unsafe_allow_html=True)
        data_filtro = st.date_input("📅 Filtrar por Data de Inclusão", value=None, key=f"data_{nome_principal}", help="Selecione um dia ou um intervalo de datas")

    with col_up:
        if subpastas: st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("📤 Upload de Arquivos"):
            arquivos_enviados = st.file_uploader("Selecione os arquivos", accept_multiple_files=True, key=f"up_{nome_principal}", label_visibility="collapsed")
            if arquivos_enviados and st.button("🚀 Enviar", key=f"btn_env_{nome_principal}", type="primary", use_container_width=True):
                with st.spinner("Enviando para o Drive..."):
                    for arq in arquivos_enviados:
                        utils.upload_to_drive(arq, arq.name, arq.type, path_atual)
                st.success("✅ Arquivos enviados com sucesso!")
                st.rerun()

    st.markdown("---")
    
    # ==========================================
    # 2. BUSCA DE DADOS NO DRIVE E PREPARAÇÃO
    # ==========================================
    arquivos_brutos = utils.list_drive_files(path_atual)
    
    if not arquivos_brutos:
        st.info("Nenhum arquivo encontrado nesta pasta.")
        return

    # Converte os dados brutos para uma tabela (DataFrame)
    dados_tabela = []
    for a in arquivos_brutos:
        dados_tabela.append({
            "Excluir": False,  # Caixinha de seleção para excluir
            "ID": a['id'],     # ID oculto
            "Nome": a['name'],
            "Data": parse_drive_date(a.get('createdTime', '')),
            "Tamanho": formatar_tamanho(a.get('size', 0)),
            "Link": a.get('webViewLink', '#')
        })
    
    df = pd.DataFrame(dados_tabela)

    # ==========================================
    # 3. APLICAÇÃO DOS FILTROS (NOME E DATA)
    # ==========================================
    if termo_busca:
        df = df[df['Nome'].str.lower().str.contains(termo_busca)]
        
    if data_filtro:
        if isinstance(data_filtro, tuple):
            if len(data_filtro) == 2:
                # Intervalo de datas
                start_date, end_date = data_filtro
                df = df[(df['Data'].dt.date >= start_date) & (df['Data'].dt.date <= end_date)]
            elif len(data_filtro) == 1:
                # Apenas um dia selecionado
                df = df[df['Data'].dt.date == data_filtro[0]]
        else:
            # Caso a API retorne um único date
            df = df[df['Data'].dt.date == data_filtro]

    if df.empty:
        st.warning("Nenhum arquivo corresponde aos filtros selecionados.")
        return

    # ==========================================
    # 4. PAGINAÇÃO (MÁXIMO 100 POR PÁGINA)
    # ==========================================
    itens_por_pagina = 100
    total_paginas = (len(df) - 1) // itens_por_pagina + 1
    
    # Só mostra o controle de página se tiver mais de 100 arquivos
    if total_paginas > 1:
        col_vazia, col_pag = st.columns([8, 2])
        with col_pag:
            pagina_atual = st.number_input("Página", min_value=1, max_value=total_paginas, value=1, key=f"pag_{nome_principal}")
    else:
        pagina_atual = 1

    inicio = (pagina_atual - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina
    df_pagina = df.iloc[inicio:fim].copy()

    # ==========================================
    # 5. RENDERIZAÇÃO DA TABELA DINÂMICA
    # ==========================================
    # Exibe a tabela interativa onde apenas a coluna "Excluir" pode ser editada
    df_editado = st.data_editor(
        df_pagina,
        column_config={
            "Excluir": st.column_config.CheckboxColumn("🗑️ Excluir", default=False, help="Marque para excluir o arquivo"),
            "ID": None, # Esconde a coluna ID da visão do utilizador
            "Nome": st.column_config.TextColumn("Nome do Arquivo", width="large"),
            "Data": st.column_config.DatetimeColumn("Data de Inclusão", format="DD/MM/YYYY - HH:mm"),
            "Tamanho": st.column_config.TextColumn("Tamanho", width="small"),
            "Link": st.column_config.LinkColumn("Acesso Rápido", display_text="👁️ Abrir PDF")
        },
        disabled=["Nome", "Data", "Tamanho", "Link"],
        hide_index=True,
        use_container_width=True,
        key=f"editor_{nome_principal}"
    )

    # ==========================================
    # 6. LÓGICA DE EXCLUSÃO EM MASSA
    # ==========================================
    if df_editado is not None and not df_editado.empty:
        # Filtra os arquivos que o utilizador marcou com a caixinha "Excluir"
        arquivos_para_apagar = df_editado[df_editado["Excluir"] == True]
        
        if not arquivos_para_apagar.empty:
            st.error(f"⚠️ Atenção: Você marcou {len(arquivos_para_apagar)} arquivo(s) para exclusão.")
            if st.button("🚨 Confirmar Exclusão Definitiva", type="primary", key=f"conf_del_{nome_principal}"):
                with st.spinner("Apagando arquivos do Drive..."):
                    for id_apagar in arquivos_para_apagar["ID"]:
                        utils.delete_drive_file(id_apagar)
                st.success("Arquivos apagados com sucesso!")
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
        renderizar_aba("Imagens", subpastas=utils.meses_pt)
        
    with abas[4]: 
        renderizar_aba("Notas Fiscais", subpastas=utils.meses_pt)
