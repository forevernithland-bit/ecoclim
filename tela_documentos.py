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
    """Converte a data do Google Drive para o fuso horário do Brasil (retorna Datetime)"""
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        dt = dt - datetime.timedelta(hours=3) # Ajuste GMT-3 (Brasil)
        return dt.replace(tzinfo=None)
    except:
        return pd.NaT

def mover_arquivo_drive(file_id, folder_path_list):
    """Move um arquivo no Google Drive para uma nova pasta"""
    try:
        service = utils.get_drive_service()
        # Pega as pastas atuais do arquivo para remover
        file = service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents', []))
        # Identifica o ID da pasta de destino
        new_folder_id = utils.get_or_create_nested_folder(service, utils.MAIN_DRIVE_FOLDER_ID, folder_path_list)
        # Move o arquivo
        service.files().update(
            fileId=file_id,
            addParents=new_folder_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        return True
    except Exception as e:
        return False

def add_one_month(dt):
    """Soma 1 mês exato na data de vencimento (inteligente com anos bissextos)"""
    new_month = dt.month + 1 if dt.month < 12 else 1
    new_year = dt.year + 1 if dt.month == 12 else dt.year
    if new_month in [4, 6, 9, 11]: last_day = 30
    elif new_month == 2:
        last_day = 29 if (new_year % 4 == 0 and (new_year % 100 != 0 or new_year % 400 == 0)) else 28
    else: last_day = 31
    new_day = min(dt.day, last_day)
    return dt.replace(year=new_year, month=new_month, day=new_day)

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
            mes_agora = datetime.date.today().month
            nome_mes_agora = utils.meses_pt[mes_agora - 1]
            default_idx = subpastas.index(nome_mes_agora) if nome_mes_agora in subpastas else 0
            
            sub_sel = st.selectbox("Selecione a Pasta / Mês:", subpastas, index=default_idx, key=f"combo_mes_{nome_principal}")
            path_atual.append(sub_sel)
            
        with c_busca:
            termo_busca = st.text_input("🔍 Buscar por Nome...", key=f"busca_{nome_principal}").lower()
            
        with c_data:
            filtro_tipo = st.selectbox("📅 Filtrar por Data", ["Todo o Período", "Hoje", "Últimos 30 dias", "Últimos 60 dias", "Últimos 90 dias", "Personalizado (Faixa)"], key=f"tipo_data_{nome_principal}")
            data_filtro = None
            if filtro_tipo == "Personalizado (Faixa)":
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
    # 2. ADIÇÃO DE LEMBRETE MANUAL (ABA BOLETOS)
    # ==========================================
    if nome_principal == "Boletos":
        with st.expander("➕ Adicionar Lembrete / Conta Manual (Sem Arquivo)"):
            with st.form(f"form_manual_bol"):
                st.caption("Cadastre despesas manuais para centralizar seus alertas.")
                c_mn, c_mv, c_md, c_mrec = st.columns([3, 1.5, 1.5, 1])
                nome_man = c_mn.text_input("Descrição (Ex: Conta de Luz, Contador)")
                valor_man = c_mv.number_input("Valor (R$)", min_value=0.0, format="%.2f", step=None)
                venc_man = c_md.date_input("Vencimento", format="DD/MM/YYYY")
                rec_man = c_mrec.checkbox("Recorrente?")
                
                if st.form_submit_button("Salvar Lembrete", use_container_width=True):
                    if not nome_man:
                        st.error("Informe a descrição.")
                    else:
                        st.session_state.supabase.table('boletos_fornecedores').insert({
                            "cliente": nome_man,
                            "vencimento": venc_man.strftime("%Y-%m-%d"),
                            "valor": valor_man,
                            "status": "Pendente",
                            "is_recorrente": rec_man
                        }).execute()
                        st.success("Lembrete salvo com sucesso!")
                        st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # 3. BUSCA DE DADOS NO DRIVE E BANCO (MERGE)
    # ==========================================
    arquivos_brutos = utils.list_drive_files(path_atual)
    df_db = pd.DataFrame()

    # Mapeamento do Banco de Dados para os arquivos
    vencimentos_map = {}
    valores_map = {}
    db_id_map = {}
    is_rec_map = {}
    status_map = {}

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
                        try: vencimentos_map[id_d] = datetime.datetime.strptime(str(r['vencimento']), "%Y-%m-%d").date()
                        except: vencimentos_map[id_d] = pd.NaT
        except: pass

    dados_tabela = []
    
    # 1. Arquivos Físicos do Drive
    for a in arquivos_brutos:
        linha_arquivo = {
            "Excluir": False,
            "ID_Drive": str(a.get('id', '')),
            "ID_DB": str(db_id_map.get(a['id'], "")),
            "ID": str(a.get('id', '')),
            "Nome": str(a.get('name', '')),
            "Data": parse_drive_date(a.get('createdTime', '')),
            "Tamanho": str(formatar_tamanho(a.get('size', 0))),
            "Link": a.get('webViewLink', None)
        }
        if nome_principal == "Boletos":
            linha_arquivo["Pagar"] = False
            v_date = vencimentos_map.get(a['id'])
            linha_arquivo["Vencimento"] = v_date if pd.notna(v_date) else pd.NaT
            linha_arquivo["Valor"] = utils.to_br_currency(valores_map.get(a['id'], 0.0))
            linha_arquivo["Recorrente"] = "🔄 Sim" if is_rec_map.get(a['id'], False) else "-"
            linha_arquivo["Status"] = str(status_map.get(a['id'], "Pendente"))
        dados_tabela.append(linha_arquivo)
        
    # 2. Lembretes Manuais do Banco (Sem Arquivo no Drive)
    if nome_principal == "Boletos" and not df_db.empty:
        mes_sel_idx = utils.meses_pt.index(sub_sel) + 1 if sub_sel in utils.meses_pt else datetime.date.today().month
        for _, r in df_db.iterrows():
            val_link = r.get('link_drive_id')
            
            # Verificação segura: se o link_drive_id estiver vazio, nulo ou for NaN
            if pd.isna(val_link) or str(val_link).strip().lower() in ['nan', 'none', '']:
                try: v_dt = datetime.datetime.strptime(str(r['vencimento']), "%Y-%m-%d").date()
                except: v_dt = None
                
                # Filtra para exibir apenas na pasta correta
                if sub_sel == "PAGOS": pertence = (r.get('status') == 'Pago')
                else: pertence = (v_dt and v_dt.month == mes_sel_idx and r.get('status') != 'Pago')
                
                if pertence:
                    # Resolve o Erro do Arrow Convertendo a "Data" do Banco para Datetime (Igual ao do Drive)
                    v_dt_datetime = datetime.datetime.combine(v_dt, datetime.time()) if v_dt else pd.NaT
                    
                    dados_tabela.append({
                        "Excluir": False,
                        "Pagar": False,
                        "ID_Drive": None,
                        "ID_DB": str(r['id']),
                        "ID": f"db_{r['id']}",
                        "Nome": f"📝 {r.get('cliente', 'Lembrete')}",
                        "Data": v_dt_datetime,
                        "Tamanho": "-",
                        "Link": None,
                        "Vencimento": v_dt if v_dt else pd.NaT,
                        "Valor": utils.to_br_currency(float(r.get('valor', 0.0))),
                        "Recorrente": "🔄 Sim" if r.get('is_recorrente', False) else "-",
                        "Status": str(r.get('status', 'Pendente'))
                    })

    df = pd.DataFrame(dados_tabela)

    if df.empty:
        st.info("Nenhum arquivo ou lembrete encontrado nesta pasta.")
        return

    # ==========================================
    # 4. APLICAÇÃO DOS FILTROS
    # ==========================================
    if termo_busca:
        df = df[df['Nome'].str.lower().str.contains(termo_busca)]
        
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
        st.warning("Nenhum item corresponde aos filtros selecionados.")
        return

    # ==========================================
    # 5. PAGINAÇÃO E CONTROLES
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
    # 6. RENDERIZAÇÃO DA TABELA / GALERIA
    # ==========================================
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
                    st.rerun()
    else:
        config_colunas = {
            "Excluir": st.column_config.CheckboxColumn("🗑️ Excluir", default=False),
            "ID": None, "ID_Drive": None, "ID_DB": None,
            "Data": None,       # Ocultado para ganhar espaço na tela
            "Tamanho": None,    # Ocultado para ganhar espaço na tela
            "Nome": st.column_config.TextColumn("Descrição/Arquivo", width="medium"), # Largura reduzida
            "Link": st.column_config.LinkColumn("Visualizar PDF", display_text="👁️ Abrir")
        }
        
        lista_desabilitados = ["Nome", "Data", "Tamanho", "Link", "Valor", "Recorrente", "Status"]
        
        if nome_principal == "Boletos":
            config_colunas["Pagar"] = st.column_config.CheckboxColumn("✅ Pagar", default=False)
            config_colunas["Vencimento"] = st.column_config.DateColumn("📅 Vencimento", format="DD/MM/YYYY")
            config_colunas["Valor"] = st.column_config.TextColumn("💰 Valor")
            config_colunas["Recorrente"] = st.column_config.TextColumn("Recorrente")
            config_colunas["Status"] = st.column_config.TextColumn("Status")
            lista_desabilitados.append("Vencimento")

        df_editado = st.data_editor(
            df_pagina, column_config=config_colunas, disabled=lista_desabilitados,
            hide_index=True, use_container_width=True, key=f"editor_{nome_principal}"
        )

        # ==========================================
        # 7. AÇÕES DE PAGAMENTO (MOVE PARA PAGOS) E EXCLUSÃO
        # ==========================================
        if df_editado is not None and not df_editado.empty:
            
            # BLOCO: MARCAR COMO PAGO
            if "Pagar" in df_editado.columns:
                boletos_pagar = df_editado[df_editado["Pagar"] == True]
                if not boletos_pagar.empty:
                    st.info(f"💡 Você marcou {len(boletos_pagar)} boleto(s) para pagamento.")
                    if st.button("🚀 Confirmar Pagamentos (Mover para Pagos)", type="primary", use_container_width=True):
                        with st.spinner("Atualizando registros e movendo arquivos..."):
                            for _, r_pag in boletos_pagar.iterrows():
                                id_db = r_pag.get("ID_DB")
                                id_drive = r_pag.get("ID_Drive")
                                
                                # Move arquivo físico no Drive
                                if id_drive and not pd.isna(id_drive) and str(id_drive).strip().lower() not in ["none", "nan", ""]:
                                    mover_arquivo_drive(id_drive, ["Boletos", "PAGOS"])
                                    
                                # Atualiza status no banco e trata recorrência
                                if id_db and not pd.isna(id_db) and str(id_db).strip() != "":
                                    st.session_state.supabase.table('boletos_fornecedores').update({'status': 'Pago'}).eq('id', id_db).execute()
                                    try:
                                        # Verifica se é recorrente
                                        orig = st.session_state.supabase.table('boletos_fornecedores').select('*').eq('id', id_db).execute().data[0]
                                        if orig.get('is_recorrente'):
                                            venc_antigo = datetime.datetime.strptime(orig['vencimento'], "%Y-%m-%d").date()
                                            novo_venc = add_one_month(venc_antigo)
                                            # Insere o espelho para o próximo mês (sem o arquivo)
                                            st.session_state.supabase.table('boletos_fornecedores').insert({
                                                'cliente': orig.get('cliente'),
                                                'vencimento': novo_venc.strftime('%Y-%m-%d'),
                                                'valor': orig.get('valor'),
                                                'status': 'Pendente',
                                                'is_recorrente': True
                                            }).execute()
                                    except: pass
                        st.success("✅ Tudo atualizado! Os arquivos foram movidos para a pasta PAGOS e os lembretes recorrentes já foram gerados.")
                        st.rerun()
            
            # BLOCO: EXCLUSÃO DE ARQUIVOS / LEMBRETES
            arquivos_para_apagar = df_editado[df_editado["Excluir"] == True]
            if not arquivos_para_apagar.empty:
                st.error(f"⚠️ Selecionou {len(arquivos_para_apagar)} item(ns) para exclusão permanente.")
                if st.button("🚨 Confirmar Exclusão", type="primary", key=f"conf_del_{nome_principal}"):
                    with st.spinner("Apagando..."):
                        for _, row_del in arquivos_para_apagar.iterrows():
                            # Apaga do Drive
                            id_dr = row_del.get("ID_Drive")
                            if id_dr and not pd.isna(id_dr) and str(id_dr).strip().lower() not in ["none", "nan", ""]:
                                utils.delete_drive_file(id_dr)
                            # Apaga do Banco
                            id_bd = row_del.get("ID_DB")
                            if id_bd and not pd.isna(id_bd) and str(id_bd).strip() != "":
                                st.session_state.supabase.table('boletos_fornecedores').delete().eq('id', id_bd).execute()
                    st.success("Excluídos com sucesso!")
                    st.rerun()

def renderizar():
    st.markdown("<br><br>", unsafe_allow_html=True)
    abas = st.tabs(["📝 Orçamentos", "🤝 Contratos", "🧾 Boletos", "🖼️ Imagens", "📊 Notas Fiscais (NF)"])
    
    with abas[0]: renderizar_aba("Orçamentos")
    with abas[1]: renderizar_aba("Contratos")
    with abas[2]: 
        meses_boletos = utils.meses_pt + ["PAGOS"]
        renderizar_aba("Boletos", subpastas=meses_boletos)
    with abas[3]: renderizar_aba("Imagens", subpastas=utils.meses_pt, is_imagens=True)
    with abas[4]: renderizar_aba("Notas Fiscais", subpastas=utils.meses_pt)
