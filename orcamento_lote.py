import streamlit as st
import pandas as pd
import utils
import zipfile
import io

def renderizar():
    deve_rerun = False
    
    st.markdown("### 📦 Geração de Orçamentos em Lote")
    st.caption("Esta ferramenta lê os 'Kits' criados em Configurações, cruza com os preços atualizados de hoje e gera todos os PDFs automaticamente.")
    
    try:
        res_kits = st.session_state.supabase.table('config_kits_lote').select('*').execute()
        df_kits = pd.DataFrame(res_kits.data)
    except Exception:
        df_kits = pd.DataFrame()

    if df_kits.empty:
        st.warning("⚠️ Nenhum Kit configurado. Vá em 'Configurações' -> 'Kits em Lote' e monte seus kits padrão primeiro.")
    else:
        nome_mes_atual_pt = utils.mes_atual_nome.capitalize()
        
        st.markdown("#### ⚙️ Configurações da Geração")
        mostrar_precos_lote = st.checkbox("Mostrar Preços Unitários no PDF?", value=False, key="check_precos_lote")
        
        opcoes_kits = [k for k in df_kits['nome_kit'].tolist() if str(k).strip() != ""]
        
        if "lote_check_all" not in st.session_state:
            st.session_state.lote_check_all = True
            
        col_sel1, col_sel2, col_sel3 = st.columns([1.5, 1.5, 3])
        
        if col_sel1.button("✅ Selecionar Todos", use_container_width=True):
            st.session_state.lote_check_all = True
            if "grid_selecao_kits" in st.session_state:
                del st.session_state["grid_selecao_kits"]
            deve_rerun = True
            
        if col_sel2.button("❌ Desmarcar Todos", use_container_width=True):
            st.session_state.lote_check_all = False
            if "grid_selecao_kits" in st.session_state:
                del st.session_state["grid_selecao_kits"]
            deve_rerun = True
        
        df_selecao = pd.DataFrame({
            "Gerar PDF": [st.session_state.lote_check_all] * len(opcoes_kits),
            "Kit Configurado": opcoes_kits
        })
        
        st.markdown("Selecione na tabela abaixo quais kits deseja gerar:")
        df_selecao_editado = st.data_editor(
            df_selecao,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Gerar PDF": st.column_config.CheckboxColumn("Gerar?", width="small"),
                "Kit Configurado": st.column_config.TextColumn("Nome Completo do Kit", disabled=True)
            },
            key="grid_selecao_kits"
        )
        
        kits_selecionados = df_selecao_editado[df_selecao_editado["Gerar PDF"] == True]["Kit Configurado"].tolist()
        
        if not kits_selecionados:
            st.warning("⚠️ Marque pelo menos um kit na tabela acima para prosseguir.")
        else:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(f"🚀 GERAR TABELAS ATUALIZADAS ({nome_mes_atual_pt})", type="primary", use_container_width=True):
                with st.spinner("Cruzando dados de preço e desenhando PDFs..."):
                    pdfs_gerados = []
                    
                    db_servicos_fresquinho = utils.load_catalog('catalogo_servicos')
                    db_produtos_fresquinho = utils.load_catalog('catalogo_produtos')
                    
                    df_kits_filtrado = df_kits[df_kits['nome_kit'].isin(kits_selecionados)]
                    
                    for _, kit in df_kits_filtrado.iterrows():
                        nome_kit_base = str(kit.get('nome_kit', 'Kit_Sem_Nome'))
                        servico_nome = str(kit.get('servico_base', '')).strip()
                        capa = str(kit.get('modelo_capa', 'Aquecedor Solar Tradicional'))
                        itens_do_kit = kit.get('itens', [])
                        if not isinstance(itens_do_kit, list): 
                            itens_do_kit = []
                        
                        nome_arquivo_final = f"{nome_kit_base}_{nome_mes_atual_pt}"
                        
                        val_serv = 0.0
                        desc_serv = ""
                        if servico_nome:
                            match_s = db_servicos_fresquinho[db_servicos_fresquinho['Item'].astype(str).str.strip().str.upper() == servico_nome.upper()]
                            if not match_s.empty:
                                try: 
                                    val_serv = float(match_s['Venda (R$)'].values[0])
                                except Exception: 
                                    pass
                                
                                nome_real_serv = str(match_s['Item'].values[0])
                                desc_real_serv = str(match_s['Descrição'].values[0])
                                
                                desc_serv = f"{nome_real_serv}\n{desc_real_serv}"
                                if desc_serv.endswith('\nnan') or desc_serv.endswith('\n'): 
                                    desc_serv = nome_real_serv
                        
                        lista_linhas_pdf = []
                        total_prod = 0.0
                        
                        for ik in itens_do_kit:
                            p_nome = str(ik.get('Produto', '')).strip()
                            try: 
                                p_qtd = int(ik.get('Quantidade', 1))
                            except Exception: 
                                p_qtd = 1
                            
                            p_preco = 0.0
                            p_desc = ""
                            if p_nome:
                                match_p = db_produtos_fresquinho[db_produtos_fresquinho['Item'].astype(str).str.strip().str.upper() == p_nome.upper()]
                                if not match_p.empty:
                                    try: 
                                        p_preco = float(match_p['Venda (R$)'].values[0])
                                    except Exception: 
                                        pass
                                    p_desc = str(match_p['Descrição'].values[0])
                                    if p_desc.lower() == 'nan': 
                                        p_desc = ""
                            
                            subtotal_item = p_preco * p_qtd
                            total_prod += subtotal_item
                            
                            lista_linhas_pdf.append({
                                "Produto da Base": p_nome,
                                "Produto Manual": "",
                                "Descrição": p_desc,
                                "Quantidade": p_qtd,
                                "Custo (R$)": 0.0,
                                "Venda (R$)": p_preco,
                                "Custo Total": 0.0,
                                "Venda Total": subtotal_item
                            })
                        
                        df_itens_lote = pd.DataFrame(lista_linhas_pdf)
                        if df_itens_lote.empty:
                            df_itens_lote = pd.DataFrame(columns=[
                                "Produto da Base", "Produto Manual", "Descrição", 
                                "Quantidade", "Custo (R$)", "Venda (R$)", 
                                "Custo Total", "Venda Total"
                            ])
                        
                        total_lote = total_prod + val_serv
                        obs_padrao = "Material hidráulico não incluso nesta proposta."
                        
                        pdf_buffer = utils.gerar_pdf_orcamento(
                            nome=nome_kit_base,
                            tel="-",
                            capa=capa,
                            df_items=df_itens_lote,
                            d_s=desc_serv,
                            v_s=val_serv,
                            d_o="",
                            v_o=0.0,
                            total=total_lote,
                            obs=obs_padrao,
                            mostrar_un=mostrar_precos_lote
                        )
                        
                        pdfs_gerados.append({
                            "nome_arquivo": f"{nome_arquivo_final}.pdf",
                            "buffer": pdf_buffer
                        })
                    
                    st.session_state['pdf_gerados_lote'] = pdfs_gerados
                    st.success(f"✅ {len(pdfs_gerados)} PDFs gerados com sucesso!")

        if 'pdf_gerados_lote' in st.session_state:
            st.markdown("---")
            st.markdown("#### 📥 Seus Arquivos (Download e Drive)")
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for pdf_dict in st.session_state['pdf_gerados_lote']:
                    zip_file.writestr(pdf_dict['nome_arquivo'], pdf_dict['buffer'].getvalue())
            
            col_down_zip, col_save_drive = st.columns(2)
            
            with col_down_zip:
                st.download_button(
                    label="📦 BAIXAR TODOS (.ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name=f"Orcamentos_Tabelas_Padrao_{nome_mes_atual_pt}.zip",
                    mime="application/zip",
                    use_container_width=True,
                    type="primary"
                )
                
            with col_save_drive:
                if st.button("☁️ SALVAR TODOS NO DRIVE", use_container_width=True):
                    with st.spinner("Enviando arquivos para o Google Drive..."):
                        pasta_lote = ["Orçamentos", "Lote", utils.mes_atual_nome]
                        erros_up = 0
                        for arq in st.session_state['pdf_gerados_lote']:
                            sucesso, msg = utils.upload_to_drive(
                                arq["buffer"], 
                                arq["nome_arquivo"], 
                                "application/pdf", 
                                pasta_lote
                            )
                            if not sucesso: 
                                erros_up += 1
                            
                        if erros_up == 0:
                            st.success(f"☁️ Todos os {len(st.session_state['pdf_gerados_lote'])} arquivos foram salvos (Orçamentos -> Lote -> {utils.mes_atual_nome}).")
                        else:
                            st.warning(f"⚠️ {erros_up} arquivo(s) não puderam ser enviados ao Drive.")
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.caption("Downloads individuais:")
            
            cols_download = st.columns(2)
            for idx, pdf_dict in enumerate(st.session_state['pdf_gerados_lote']):
                with cols_download[idx % 2]:
                    st.download_button(
                        label=f"⬇️ {pdf_dict['nome_arquivo']}",
                        data=pdf_dict['buffer'].getvalue(),
                        file_name=pdf_dict['nome_arquivo'],
                        mime="application/pdf",
                        key=f"dl_lote_{idx}",
                        use_container_width=True
                    )
    return deve_rerun
