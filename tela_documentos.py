import streamlit as st
import pandas as pd
import datetime
import utils
import emprestimos
import zipfile
import io
from googleapiclient.http import MediaIoBaseUpload

def formatar_tamanho(tamanho_bytes):
    try:
        tamanho = int(tamanho_bytes)
        if tamanho < 1024: 
            return f"{tamanho} B"
        elif tamanho < 1024 * 1024: 
            return f"{tamanho / 1024:.1f} KB"
        else: 
            return f"{tamanho / (1024 * 1024):.1f} MB"
    except: 
        return "Desconhecido"

def parse_drive_date(iso_str):
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        dt = dt - datetime.timedelta(hours=3) # Ajuste Brasil (GMT-3)
        return dt.replace(tzinfo=None)
    except:
        return pd.NaT

def mover_arquivo_drive(file_id, folder_path_list):
    try:
        service = utils.get_drive_service()
        if not service: return False
        file = service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents', []))
        new_folder_id = utils.get_or_create_nested_folder(service, utils.MAIN_DRIVE_FOLDER_ID, folder_path_list)
        service.files().update(
            fileId=file_id,
            addParents=new_folder_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        return True
    except:
        return False

def add_months(dt, months):
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, [31, 29 if year % 4 == 0 and not year % 100 == 0 or year % 400 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return dt.replace(year=year, month=month, day=day)

# =============================================================================
# MOTOR CIRÚRGICO DE UPLOAD E BUSCA DIRECTA POR IDs FIXOS
# =============================================================================
def upload_direto_gdrive(file_buffer, filename, mimetype, path_list):
    try:
        service = utils.get_drive_service()
        if not service: return False, "Falha na conexão global do motor OAuth."
        
        mapeamento_ids = {
            "Orçamentos": "1DySx6I2sMQ6OQNR74mwbTrAf2KuK2YI4",
            "Contratos": "1s1pIqZ2MhlxKOQzjwNZwTU8SE3K5WnKb",
            "Imagens": "1F8C5IH6AbscBc3DLoasP9Zjx2qrqgU8p",
            "Notas Fiscais": "1H8S-8mKS5TB8co7df2vMdqyKfTgDG0V2"
        }
        
        nome_principal = path_list[0]
        if nome_principal in mapeamento_ids:
            current_parent = mapeamento_ids[nome_principal]
            if len(path_list) > 1:
                for folder_name in path_list[1:]:
                    q = f"'{current_parent}' in parents and name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
                    res = service.files().list(q=q, fields="files(id)").execute()
                    files = res.get('files', [])
                    if files:
                        current_parent = files[0]['id']
                    else:
                        folder_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [current_parent]}
                        folder = service.files().create(body=folder_metadata, fields='id').execute()
                        current_parent = folder.get('id')
                        
            file_metadata = {'name': filename, 'parents': [current_parent]}
            file_stream = io.BytesIO(file_buffer.getvalue())
            media = MediaIoBaseUpload(file_stream, mimetype=mimetype, resumable=True)
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            return True, file.get('id')
        else:
            return utils.upload_to_drive(file_buffer, filename, mimetype, path_list)
    except Exception as e:
        return False, str(e)

@st.cache_data(ttl=60)
def listar_arquivos_pasta_gdrive(nome_principal, path_list):
    try:
        service = utils.get_drive_service()
        if not service: return [], "Falha na conexão global do motor OAuth."
        
        mapeamento_ids = {
            "Orçamentos": "1DySx6I2sMQ6OQNR74mwbTrAf2KuK2YI4",
            "Contratos": "1s1pIqZ2MhlxKOQzjwNZwTU8SE3K5WnKb",
            "Imagens": "1F8C5IH6AbscBc3DLoasP9Zjx2qrqgU8p",
            "Notas Fiscais": "1H8S-8mKS5TB8co7df2vMdqyKfTgDG0V2"
        }
        
        if nome_principal in mapeamento_ids:
            target_folder_id = mapeamento_ids[nome_principal]
            if len(path_list) > 1:
                for folder_name in path_list[1:]:
                    q = f"'{target_folder_id}' in parents and name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
                    res = service.files().list(q=q, fields="files(id)").execute()
                    files = res.get('files', [])
                    if not files:
                        return [], None
                    target_folder_id = files[0]['id']
            
            q_files = f"'{target_folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
            res_files = service.files().list(q=q_files, fields="files(id, name, createdTime, size, webViewLink)", pageSize=1000).execute()
            return res_files.get('files', []), None
        else:
            return utils.list_drive_files(path_list), None
    except Exception as e:
        return [], str(e)

def renderizar_aba(nome_principal, subpastas=None, is_imagens=False):
    path_atual = [nome_principal]
    
    st.markdown("""
        <style>
        div[data-testid="stExpander"] details summary { padding-top: 0.5rem; padding-bottom: 0.5rem; }
        div[data-testid="stNumberInputStepUp"], div[data-testid="stNumberInputStepDown"] { display: none !important; }
        input[type=number]::-webkit-inner-spin-button, input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none !important; margin: 0 !important; }
        input[type=number] { -moz-appearance: textfield !important; }
        @media screen and (max-width: 768px) {
            div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] { overflow-x: auto !important; }
            div[data-testid="column"] { width: 100% !important; min-width: 100% !important; display: block !important; margin-bottom: 0.8rem !important; }
            div.stButton > button { min-height: 48px !important; }
        }
        </style>
    """, unsafe_allow_html=True)

    if subpastas:
        c_sub, c_busca, c_data, c_sync, c_up = st.columns([1.2, 1.3, 1.2, 0.8, 1])
        with c_sub:
            mes_agora = datetime.date.today().month
            nome_mes_agora = utils.meses_pt[mes_agora - 1]
            default_idx = subpastas.index(nome_mes_agora) if nome_mes_agora in subpastas else 0
            sub_sel = st.selectbox("Selecione a Pasta / Mês:", subpastas, index=default_idx, key=f"combo_mes_{nome_principal}")
            path_atual.append(sub_sel)
            
        with c_busca:
            termo_busca = st.text_input("🔍 Buscar por Nome...", key=f"busca_{nome_principal}").lower()
            
        with c_data:
            filtro_tipo = st.selectbox("📅 Filtrar por Data", ["Todo o Período", "Hoje", "Últimos 30 dias", "Últimos 60 dias", "Últimos 90 dias", "Personalizado (Faixa)"], index=0, key=f"tipo_data_{nome_principal}")
            data_filtro = None
            if filtro_tipo == "Personalizado (Faixa)":
                data_filtro = st.date_input("Início e Fim:", value=[], key=f"data_pers_{nome_principal}")
        
        with c_sync:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            if st.button("🔄 Atualizar", key=f"sync_{nome_principal}", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
                
        with c_up:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            with st.expander("📤 Upload Arquivos"):
                arquivos_enviados = st.file_uploader("Selecione", accept_multiple_files=True, key=f"up_{nome_principal}", label_visibility="collapsed")
                if arquivos_enviados and st.button("🚀 Enviar", key=f"btn_env_{nome_principal}", type="primary", use_container_width=True):
                    with st.spinner("Enviando para o Drive..."):
                        todos_ok = True
                        for arq in arquivos_enviados: 
                            sucesso, msg = upload_direto_gdrive(arq, arq.name, arq.type, path_atual)
                            if not sucesso:
                                st.error(f"Erro do Google Drive ao enviar '{arq.name}': {msg}")
                                todos_ok = False
                                break
                        if todos_ok:
                            st.success("✅ Sucesso!")
                            st.cache_data.clear()
                            st.rerun()
    else:
        c_busca, c_data, c_sync, c_up = st.columns([1.8, 1.5, 0.8, 1])
        with c_busca:
            termo_busca = st.text_input("🔍 Buscar por Nome...", key=f"busca_{nome_principal}").lower()
            
        with c_data:
            filtro_tipo = st.selectbox("📅 Filtrar por Data", ["Todo o Período", "Hoje", "Últimos 30 dias", "Últimos 60 dias", "Últimos 90 dias", "Personalizado (Faixa)"], index=0, key=f"tipo_data_s_{nome_principal}")
            data_filtro = None
            if filtro_tipo == "Personalizado (Faixa)":
                data_filtro = st.date_input("Início e Fim:", value=[], key=f"data_pers_s_{nome_principal}")
        
        with c_sync:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            if st.button("🔄 Atualizar", key=f"sync_s_{nome_principal}", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
                
        with c_up:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            with st.expander("📤 Upload Arquivos"):
                arquivos_enviados = st.file_uploader("Selecione", accept_multiple_files=True, key=f"up_s_{nome_principal}", label_visibility="collapsed")
                if arquivos_enviados and st.button("🚀 Enviar", key=f"btn_env_s_{nome_principal}", type="primary", use_container_width=True):
                    with st.spinner("Enviando para o Drive..."):
                        todos_ok = True
                        for arq in arquivos_enviados: 
                            sucesso, msg = upload_direto_gdrive(arq, arq.name, arq.type, path_atual)
                            if not sucesso:
                                st.error(f"Erro do Google Drive ao enviar '{arq.name}': {msg}")
                                todos_ok = False
                                break
                        if todos_ok:
                            st.success("✅ Sucesso!")
                            st.cache_data.clear()
                            st.rerun()

    st.markdown("---")
    
    lista_categorias = ["Casa Airnb", "Ecoclim", "Consorbens", "Pessoal", "Outros"]

    if nome_principal == "Boletos":
        with st.expander("➕ Adicionar Lembrete / Conta Manual (Sem Arquivo)"):
            with st.form(f"form_manual_bol"):
                st.caption("Cadastre despesas manuais para centralizar os seus alertas.")
                c_mn, c_mcat, c_mv, c_md, c_mrec = st.columns([2.5, 1.5, 1.2, 1.2, 1])
                nome_man = c_mn.text_input("Descrição (Ex: Conta de Luz, Contador)")
                cat_man = c_mcat.selectbox("Categoria", lista_categorias, index=4)
                valor_man = c_mv.number_input("Valor (R$)", min_value=0.0, format="%.2f")
                venc_man = c_md.date_input("Vencimento", format="DD/MM/YYYY")
                rec_man = c_mrec.checkbox("Recorrente?")
                
                if st.form_submit_button("Salvar Lembrete", use_container_width=True):
                    if not nome_man:
                        st.error("Informe a descrição.")
                    else:
                        st.session_state.supabase.table('boletos_fornecedores').insert({
                            "cliente": nome_man, 
                            "categoria": cat_man,
                            "vencimento": venc_man.strftime("%Y-%m-%d"),
                            "valor": valor_man, 
                            "status": "Pendente", 
                            "is_recorrente": rec_man
                        }).execute()
                        
                        utils.sincronizar_boletos_com_calendar()
                        st.success("Lembrete salvo com sucesso!")
                        st.cache_data.clear()
                        st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

    arquivos_brutos, erro_api = listar_arquivos_pasta_gdrive(nome_principal, path_atual)
    
    if erro_api:
        st.error(f"⚠️ Erro de Permissão no Google Drive: {erro_api}")
        return

    df_db = pd.DataFrame()
    vencimentos_map = {}
    valores_map = {}
    db_id_map = {}
    is_rec_map = {}
    status_map = {}
    cat_map = {}

    if nome_principal == "Boletos":
        try:
            res_b = st.session_state.supabase.table('boletos_fornecedores').select('*').execute()
            if res_b.data:
                df_db = pd.DataFrame(res_b.data)
                for _, r in df_db.iterrows():
                    id_d = r.get('link_drive_id')
                    if id_d and not pd.isna(id_d):
                        db_id_map[id_d] = r['id']
                        valores_map[id_d] = float(r.get('valor', 0.0))
                        is_rec_map[id_d] = r.get('is_recorrente', False)
                        status_map[id_d] = r.get('status', 'Pendente')
                        cat_map[id_d] = r.get('categoria', 'Outros')
                        try: 
                            vencimentos_map[id_d] = datetime.datetime.strptime(str(r['vencimento']), "%Y-%m-%d").date()
                        except: 
                            vencimentos_map[id_d] = pd.NaT
        except: 
            pass

    dados_tabela = []
    processed_drive_ids = set()

    if nome_principal == "Boletos" and not df_db.empty:
        mes_sel_idx = utils.meses_pt.index(sub_sel) + 1 if sub_sel in utils.meses_pt else datetime.date.today().month
        for _, r in df_db.iterrows():
            try: 
                v_dt = datetime.datetime.strptime(str(r['vencimento']), "%Y-%m-%d").date()
            except: 
                v_dt = None
            
            if sub_sel == "PAGOS": 
                pertence = (r.get('status') == 'Pago')
            else: 
                pertence = (v_dt and v_dt.month == mes_sel_idx and r.get('status') != 'Pago')
            
            if pertence:
                val_link = r.get('link_drive_id')
                tem_drive = pd.notna(val_link) and str(val_link).strip().lower() not in ['nan', 'none', '']
                
                if tem_drive:
                    processed_drive_ids.add(val_link)
                    icone = "📄"
                    link_url = f"https://drive.google.com/file/d/{val_link}/view"
                else:
                    icone = "📝"
                    link_url = None
                
                v_dt_datetime = datetime.datetime.combine(v_dt, datetime.time()) if v_dt else pd.NaT
                
                dados_tabela.append({
                    "Excluir": False, 
                    "Pagar": False, 
                    "ID_Drive": val_link if tem_drive else None, 
                    "ID_DB": str(r['id']),
                    "ID": f"db_{r['id']}", 
                    "Nome": f"{icone} {r.get('cliente', 'Despesa')}",
                    "Data": v_dt_datetime, 
                    "Tamanho": "-", 
                    "Link": link_url,
                    "Vencimento": v_dt if v_dt else pd.NaT,
                    "Categoria": str(r.get('categoria', 'Outros')),
                    "Valor": float(r.get('valor', 0.0)), 
                    "Recorrente": "🔄 Sim" if r.get('is_recorrente', False) else "-",
                    "Status": str(r.get('status', 'Pendente'))
                })

    for a in arquivos_brutos:
        d_id = str(a.get('id', ''))
        
        if nome_principal == "Boletos" and d_id in processed_drive_ids:
            continue
            
        if nome_principal == "Boletos" and d_id in db_id_map:
            continue

        linha_arquivo = {
            "Excluir": False,
            "ID_Drive": d_id,
            "ID_DB": str(db_id_map.get(d_id, "")),
            "ID": d_id,
            "Nome": f"📄 {str(a.get('name', ''))}",
            "Data": parse_drive_date(a.get('createdTime', '')),
            "Tamanho": str(formatar_tamanho(a.get('size', 0))),
            "Link": a.get('webViewLink', f"https://drive.google.com/file/d/{d_id}/view")
        }
        
        if nome_principal == "Boletos":
            linha_arquivo["Pagar"] = False
            v_date = vencimentos_map.get(d_id)
            linha_arquivo["Vencimento"] = v_date if pd.notna(v_date) else pd.NaT
            linha_arquivo["Categoria"] = str(cat_map.get(d_id, "Outros"))
            linha_arquivo["Valor"] = float(valores_map.get(d_id, 0.0)) 
            linha_arquivo["Recorrente"] = "🔄 Sim" if is_rec_map.get(d_id, False) else "-"
            linha_arquivo["Status"] = str(status_map.get(d_id, "Pendente"))
        
        dados_tabela.append(linha_arquivo)

    df = pd.DataFrame(dados_tabela)

    if df.empty:
        st.info("Nenhum arquivo ou lembrete encontrado nesta pasta.")
        return

    if termo_busca: 
        df = df[df['Nome'].str.lower().str.contains(termo_busca)]
        
    hoje_filtro = datetime.date.today()
    if filtro_tipo == "Hoje": 
        df = df[df['Data'].dt.date == hoje_filtro]
    elif filtro_tipo == "Últimos 30 dias": 
        df = df[df['Data'].dt.date >= (hoje_filtro - datetime.timedelta(days=30))]
    elif filtro_tipo == "Últimos 60 dias": 
        df = df[df['Data'].dt.date >= (hoje_filtro - datetime.timedelta(days=60))]
    elif filtro_tipo == "Últimos 90 dias": 
        df = df[df['Data'].dt.date >= (hoje_filtro - datetime.timedelta(days=90))]
    elif filtro_tipo == "Personalizado (Faixa)" and data_filtro:
        if isinstance(data_filtro, (tuple, list)):
            if len(data_filtro) == 2: 
                df = df[(df['Data'].dt.date >= data_filtro[0]) & (df['Data'].dt.date <= data_filtro[1])]
            elif len(data_filtro) == 1: 
                df = df[df['Data'].dt.date == data_filtro[0]]
        else: 
            df = df[df['Data'].dt.date == data_filtro]

    if df.empty:
        st.warning("Nenhum item corresponde aos filtros selecionados.")
        return

    if nome_principal == "Boletos":
        hoje_ordem = datetime.date.today()
        
        def definir_prioridade(row):
            s = row.get('Status', '')
            v = row.get('Vencimento')
            
            if s == 'Pago':
                return 3
            elif s == 'Pendente':
                if pd.notna(v):
                    try:
                        v_dt = pd.to_datetime(v).date()
                        if v_dt < hoje_ordem:
                            return 1
                    except:
                        pass
                return 2
            return 4
            
        df['prioridade'] = df.apply(definir_prioridade, axis=1)
        df = df.sort_values(by=['prioridade', 'Vencimento']).drop(columns=['prioridade']).reset_index(drop=True)

    itens_por_pagina = 100
    total_paginas = (len(df) - 1) // itens_por_pagina + 1
    
    # -------------------------------------------------------------------------
    # TRUQUE DE LAYOUT: CONTAINERS PARA MOSTRAR A TABELA EM CIMA E PÁGINAS EMBAIXO
    # -------------------------------------------------------------------------
    container_tabela = st.container()
    st.markdown("<br>", unsafe_allow_html=True)
    container_paginacao = st.container()
    container_acoes = st.container()

    with container_paginacao:
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
    df_pagina = df.iloc[inicio : inicio + itens_por_pagina].copy()

    with container_tabela:
        if is_imagens and modo_visao == "Miniaturas":
            cols = st.columns(4)
            for i, row in df_pagina.reset_index(drop=True).iterrows():
                with cols[i % 4]:
                    img_url = f"https://drive.google.com/uc?export=view&id={row['ID']}"
                    st.markdown(f'''
                        <a href="{row['Link']}" target="_blank">
                            <div style="height: 180px; background-image: url('{img_url}'); background-size: cover; background-position: center; border-radius: 8px; border: 1px solid #ddd; margin-bottom: 5px; background-color: #f8f9fa;"></div>
                        </a>
                        <p style='font-size:0.8rem; text-align:center; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;' title='{row['Nome']}'><b>{row['Nome']}</b></p>
                    ''', unsafe_allow_html=True)
                    if st.button("🗑️ Excluir", key=f"del_img_{row['ID']}", use_container_width=True):
                        utils.delete_drive_file(row['ID'])
                        st.cache_data.clear()
                        st.rerun()
        else:
            config_colunas = {
                "Excluir": st.column_config.CheckboxColumn("🗑️", default=False, width="small"),
                "ID": None, 
                "ID_Drive": None, 
                "ID_DB": None,
                "Tamanho": None,    
                "Nome": st.column_config.TextColumn("Descrição", width="medium"), 
                "Link": st.column_config.LinkColumn("PDF", display_text="👁️ Abrir", width="small")
            }
            
            lista_desabilitados = ["Nome", "Data", "Tamanho", "Link"]
    
            if nome_principal == "Boletos":
                config_colunas["Data"] = None 
                config_colunas["Vencimento"] = st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY", width="small") 
                config_colunas["Categoria"] = st.column_config.SelectboxColumn("Categoria", options=lista_categorias, width="medium")
                config_colunas["Valor"] = st.column_config.NumberColumn("Valor (R$)", format="%.2f", width="small") 
                config_colunas["Recorrente"] = st.column_config.TextColumn("Recorrente", width="small")
                config_colunas["Pagar"] = st.column_config.CheckboxColumn("Pagar", default=False, width="small")
                config_colunas["Status"] = st.column_config.TextColumn("Status", width="small")
                
                lista_desabilitados.extend(["Vencimento", "Recorrente", "Status"])
                
                col_order = ["Excluir", "Nome", "Link", "Vencimento", "Categoria", "Valor", "Recorrente", "Pagar", "Status"]
            else:
                config_colunas["Data"] = st.column_config.DatetimeColumn("Data de Inclusão", format="DD/MM/YYYY - HH:mm")
                col_order = ["Excluir", "Nome", "Link", "Data"]
    
            todas_cols = col_order + [c for c in df_pagina.columns if c not in col_order]
            df_pagina = df_pagina[todas_cols].reset_index(drop=True)
    
            if nome_principal == "Boletos":
                def colorir_boletos(row):
                    s = row.get('Status', '')
                    v = row.get('Vencimento', pd.NaT)
                    hoje = datetime.date.today()
                    
                    if s == 'Pago':
                        cor = 'color: #008000; font-weight: 500;' 
                    elif s == 'Pendente':
                        if pd.notna(v) and v < hoje:
                            cor = 'color: #cc0000; font-weight: bold;' 
                        else:
                            cor = 'color: #004488; font-weight: 500;' 
                    else:
                        cor = ''
                    return [cor] * len(row)
    
                df_exibicao = df_pagina.style.apply(colorir_boletos, axis=1)
            else:
                df_exibicao = df_pagina
    
            df_editado = st.data_editor(
                df_exibicao, 
                column_config=config_colunas, 
                column_order=col_order, 
                disabled=lista_desabilitados,
                hide_index=True, 
                use_container_width=True, 
                key=f"editor_docs_v11_{nome_principal}" 
            )
    
            if df_editado is not None and not df_editado.empty:
                
                if "Valor" in df_editado.columns and "Categoria" in df_editado.columns and nome_principal == "Boletos":
                    diff_val = abs(pd.to_numeric(df_editado["Valor"], errors='coerce').fillna(0) - pd.to_numeric(df_pagina["Valor"], errors='coerce').fillna(0)) > 0.01
                    diff_cat = df_editado["Categoria"].fillna('Outros') != df_pagina["Categoria"].fillna('Outros')
                    
                    boletos_alterados = df_editado[diff_val | diff_cat]
                    
                    if not boletos_alterados.empty:
                        st.warning(f"⚠️ Você alterou dados de {len(boletos_alterados)} boleto(s). Confirme para salvar.")
                        if st.button("💾 Salvar Alterações", type="primary", use_container_width=True):
                            with st.spinner("Atualizando banco de dados..."):
                                for _, r_upd in boletos_alterados.iterrows():
                                    id_db = r_upd.get("ID_DB")
                                    if id_db and str(id_db).strip() not in ["none", "nan", ""]:
                                        st.session_state.supabase.table('boletos_fornecedores').update({
                                            'valor': float(r_upd['Valor']),
                                            'categoria': str(r_upd['Categoria'])
                                        }).eq('id', id_db).execute()
                            
                            utils.sincronizar_boletos_com_calendar()
                            st.success("✅ Atualizado com sucesso!")
                            st.rerun()
    
                if "Pagar" in df_editado.columns:
                    boletos_pagar = df_editado[(df_editado["Pagar"] == True) & (df_editado["Status"] != "Pago")]
                    
                    if not boletos_pagar.empty:
                        st.info(f"💡 Você marcou {len(boletos_pagar)} nova(s) despesa(s) para pagamento.")
                        if st.button("🚀 Confirmar Pagamentos", type="primary", use_container_width=True):
                            with st.spinner("Atualizando registros..."):
                                for _, r_pag in boletos_pagar.iterrows():
                                    id_db = r_pag.get("ID_DB")
                                    id_drive = r_pag.get("ID_Drive")
                                    
                                    if id_drive and not pd.isna(id_drive) and str(id_drive).strip().lower() not in ["none", "nan", ""]:
                                        mover_arquivo_drive(id_drive, ["Boletos", "PAGOS"])
                                        
                                    if id_db and not pd.isna(id_db) and str(id_db).strip() != "":
                                        st.session_state.supabase.table('boletos_fornecedores').update({'status': 'Pago'}).eq('id', id_db).execute()
                                        try:
                                            orig = st.session_state.supabase.table('boletos_fornecedores').select('*').eq('id', id_db).execute().data[0]
                                            if orig.get('is_recorrente'):
                                                venc_antigo = datetime.datetime.strptime(orig['vencimento'], "%Y-%m-%d").date()
                                                novo_venc = add_months(venc_antigo, 1)
                                                st.session_state.supabase.table('boletos_fornecedores').insert({
                                                    'cliente': orig.get('cliente'), 
                                                    'categoria': orig.get('categoria', 'Outros'),
                                                    "vencimento": novo_venc.strftime('%Y-%m-%d'),
                                                    'valor': orig.get('valor'), 
                                                    'status': 'Pendente', 
                                                    'is_recorrente': True
                                                }).execute()
                                        except: 
                                            pass
                            
                            utils.sincronizar_boletos_com_calendar()
                            st.success("✅ Tudo atualizado! Boletos pagos e próxima recorrência gerada (caso aplicável).")
                            st.cache_data.clear()
                            st.rerun()
                
                arquivos_para_apagar = df_editado[df_editado["Excluir"] == True]
                if not arquivos_para_apagar.empty:
                    st.error(f"⚠️ Selecionou {len(arquivos_para_apagar)} item(ns) para exclusão permanente.")
                    if st.button("🚨 Confirmar Exclusão", type="primary", key=f"conf_del_{nome_principal}"):
                        with st.spinner("Apagando..."):
                            for _, row_del in arquivos_para_apagar.iterrows():
                                id_dr = row_del.get("ID_Drive")
                                if id_dr and not pd.isna(id_dr) and str(id_dr).strip().lower() not in ["none", "nan", ""]:
                                    utils.delete_drive_file(id_dr)
                                id_bd = row_del.get("ID_DB")
                                if id_bd and not pd.isna(id_bd) and str(id_bd).strip() != "":
                                    st.session_state.supabase.table('boletos_fornecedores').delete().eq('id', id_bd).execute()
                        
                        utils.sincronizar_boletos_com_calendar()
                        st.success("Excluídos com sucesso!")
                        st.cache_data.clear()
                        st.rerun()

    with container_acoes:
        arquivos_reais_disponiveis = df_pagina[df_pagina["ID_Drive"].notna() & (~df_pagina["Nome"].str.startswith("📝 "))]
        
        if not arquivos_reais_disponiveis.empty:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("📦 **Download Multiplo de Documentos**")
                arquivos_selecionados = st.multiselect(
                    "Selecione na lista os documentos que deseja baixar juntos:",
                    options=arquivos_reais_disponiveis["Nome"].tolist(),
                    key=f"multiselect_down_{nome_principal}"
                )
                
                if arquivos_selecionados:
                    if st.button("📦 Preparar Pacote .ZIP para Baixar", key=f"btn_zip_gen_{nome_principal}", use_container_width=True):
                        with st.spinner("Buscando arquivos no Google Drive e compactando..."):
                            try:
                                service = utils.get_drive_service()
                                zip_buffer = io.BytesIO()
                                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                                    df_filtrado_down = arquivos_reais_disponiveis[arquivos_reais_disponiveis["Nome"].isin(arquivos_selecionados)]
                                    
                                    for _, row_down in df_filtrado_down.iterrows():
                                        file_id = row_down.get("ID_Drive")
                                        file_name = row_down.get("Nome")
                                        
                                        if file_id:
                                            try:
                                                file_content = service.files().get_media(fileId=file_id).execute()
                                                zip_file.writestr(file_name, file_content)
                                            except Exception:
                                                pass
                                zip_buffer.seek(0)
                                st.session_state[f"zip_bytes_{nome_principal}"] = zip_buffer.getvalue()
                            except Exception as e:
                                st.error(f"Erro ao conectar com o Drive: {e}")
                    
                    if f"zip_bytes_{nome_principal}" in st.session_state:
                        st.download_button(
                            label="📥 CLIQUE AQUI PARA BAIXAR O PACOTE (.ZIP)",
                            data=st.session_state[f"zip_bytes_{nome_principal}"],
                            file_name=f"Lote_{nome_principal}_{datetime.date.today().strftime('%d%m%Y')}.zip",
                            mime="application/zip",
                            use_container_width=True,
                            type="primary",
                            key=f"download_zip_final_{nome_principal}"
                        )
                else:
                    if f"zip_bytes_{nome_principal}" in st.session_state:
                        del st.session_state[f"zip_bytes_{nome_principal}"]

        if nome_principal == "Boletos" and not df.empty:
            st.markdown("---")
            st.markdown(f"#### 📊 Resumo do Mês ({sub_sel})")
            
            st.markdown("##### 🏷️ Despesas por Categoria")
            resumo_cat = df.groupby('Categoria')['Valor'].sum().reset_index()
            
            if not resumo_cat.empty:
                cols_cat = st.columns(len(resumo_cat))
                for i, r in resumo_cat.iterrows():
                    cols_cat[i % len(cols_cat)].metric(r['Categoria'], utils.to_br_currency(r['Valor']))
            else:
                st.info("Nenhuma despesa para categorizar neste período.")
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            total_pendente = df[df['Status'] != 'Pago']['Valor'].sum()

            # Pagos do mês vêm do banco (o df da tela mostra só pendentes agora).
            total_pago = 0.0
            try:
                mes_idx_resumo = utils.meses_pt.index(sub_sel) + 1 if sub_sel in utils.meses_pt else datetime.date.today().month
                if not df_db.empty:
                    for _, rb in df_db.iterrows():
                        if str(rb.get('status')) == 'Pago':
                            try:
                                vdt = datetime.datetime.strptime(str(rb['vencimento']), "%Y-%m-%d").date()
                            except Exception:
                                continue
                            if vdt.month == mes_idx_resumo:
                                total_pago += float(rb.get('valor', 0.0) or 0.0)
            except Exception:
                pass

            total_geral = total_pago + total_pendente

            c_res1, c_res2, c_res3 = st.columns(3)
            c_res1.metric("🔵 Pendentes a Pagar", utils.to_br_currency(total_pendente))
            c_res2.metric("🟢 Pagos no Mês", utils.to_br_currency(total_pago))
            c_res3.metric("💰 Total de Despesas do Mês", utils.to_br_currency(total_geral))

def _render_historico_pagos():
    """Parte 5: histórico de boletos pagos, agrupado mês a mês (oculto por padrão)."""
    try:
        res = st.session_state.supabase.table('boletos_fornecedores').select('*').eq('status', 'Pago').execute()
        pagos = res.data or []
    except Exception:
        pagos = []

    if not pagos:
        st.info("Nenhum boleto pago registrado ainda.")
        return

    df = pd.DataFrame(pagos)
    df['venc_dt'] = pd.to_datetime(df.get('vencimento'), errors='coerce')
    df = df.dropna(subset=['venc_dt']).sort_values('venc_dt', ascending=False)
    if df.empty:
        st.info("Nenhum boleto pago com data de vencimento válida.")
        return

    df['ano'] = df['venc_dt'].dt.year
    df['mes'] = df['venc_dt'].dt.month
    df['valor_num'] = pd.to_numeric(df.get('valor'), errors='coerce').fillna(0.0)

    total_geral = df['valor_num'].sum()
    st.caption(f"Total pago (histórico): **{utils.to_br_currency(total_geral)}** em {len(df)} boleto(s).")

    chaves = df[['ano', 'mes']].drop_duplicates().sort_values(['ano', 'mes'], ascending=False)
    for _, k in chaves.iterrows():
        ano, mes = int(k['ano']), int(k['mes'])
        grupo = df[(df['ano'] == ano) & (df['mes'] == mes)].reset_index(drop=True)
        total_mes = grupo['valor_num'].sum()
        nome_mes = utils.meses_pt[mes - 1] if 1 <= mes <= 12 else str(mes)

        with st.expander(f"🗓️ {nome_mes} / {ano}  —  {utils.to_br_currency(total_mes)}  ({len(grupo)} boleto(s))", expanded=False):
            def _coluna(nome_col, padrao=''):
                return grupo[nome_col] if nome_col in grupo.columns else pd.Series([padrao] * len(grupo))

            def _link(x):
                s = str(x).strip().lower()
                if x is not None and s not in ['nan', 'none', '']:
                    return f"https://drive.google.com/file/d/{x}/view"
                return None

            tabela = pd.DataFrame({
                "Fornecedor / Cliente": _coluna('cliente', 'Despesa'),
                "Categoria": _coluna('categoria', 'Outros'),
                "Vencimento": grupo['venc_dt'].dt.strftime('%d/%m/%Y'),
                "Valor": grupo['valor_num'].apply(utils.to_br_currency),
                "Arquivo": _coluna('link_drive_id', None).apply(_link),
            })
            st.dataframe(
                tabela, use_container_width=True, hide_index=True,
                column_config={"Arquivo": st.column_config.LinkColumn("Arquivo", display_text="📄 Abrir")},
            )


def renderizar():
    st.markdown("<br>", unsafe_allow_html=True)

    # Seletor de categoria guiado por session_state (substitui st.tabs, que não
    # permite selecionar aba por código). Assim o botão "Boletos" da Página
    # Inicial consegue abrir direto na categoria certa (Parte 4).
    categorias = [
        ("📝 Orçamentos", "Orçamentos"),
        ("🤝 Contratos", "Contratos"),
        ("🧾 Boletos", "Boletos"),
        # Fica ao lado de Boletos porque é onde se procura por "contas": um é o
        # que sai, outro é o que tem pra entrar. Os dados são separados, ver
        # emprestimos.py.
        ("💸 Empréstimos", "Empréstimos"),
        ("🖼️ Imagens", "Imagens"),
        ("📊 Notas Fiscais (NF)", "Notas Fiscais"),
    ]
    labels = [c[0] for c in categorias]
    valores = [c[1] for c in categorias]

    st.session_state.setdefault("doc_categoria_label", labels[0])
    alvo = st.session_state.pop("doc_ir_para", None)  # navegação externa (Home)
    if alvo in valores:
        st.session_state.doc_categoria_label = labels[valores.index(alvo)]

    escolha = st.radio(
        "Categoria de Documentos", labels, horizontal=True,
        key="doc_categoria_label", label_visibility="collapsed",
    )
    nome = valores[labels.index(escolha)]
    st.markdown("<div style='margin-top:4px;'></div>", unsafe_allow_html=True)

    if nome == "Orçamentos":
        renderizar_aba("Orçamentos")
    elif nome == "Contratos":
        renderizar_aba("Contratos")
    elif nome == "Boletos":
        # "PAGOS" saiu do seletor de mês: pagos ficam ocultos por padrão e são
        # exibidos no "Histórico de Pagos" (mês a mês) dentro da aba (Parte 5).
        renderizar_aba("Boletos", subpastas=utils.meses_pt)
        st.markdown("---")
        if st.toggle("📗 Ver Histórico de Pagos (mês a mês)", value=False, key="ver_hist_pagos"):
            _render_historico_pagos()
    elif nome == "Empréstimos":
        emprestimos.renderizar()
    elif nome == "Imagens":
        renderizar_aba("Imagens", subpastas=utils.meses_pt, is_imagens=True)
    elif nome == "Notas Fiscais":
        renderizar_aba("Notas Fiscais", subpastas=utils.meses_pt)
