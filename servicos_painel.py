import streamlit as st
import pandas as pd
import datetime
import utils
import traceback

def safe_float(val):
    try:
        if pd.isna(val) or val is None or str(val).strip() == '': 
            return 0.0
        if isinstance(val, str):
            val = val.replace('R$', '').replace(' ', '').replace(',', '.')
        return float(val)
    except:
        return 0.0

def exibir_painel_detalhado(projeto_selecionado, supabase, df_taxas_config, df_produtos, prefix_key, lista_instaladores):
    # =========================================================================
    # ARMADURA ANTI-CRASH GLOBAL DO PAINEL
    # =========================================================================
    try:
        st.markdown("---")
        st.markdown(f"### ⚙️ Detalhes e Fechamento")
        
        c_cad1, c_cad2 = st.columns(2)
        novo_nome_cliente = c_cad1.text_input("Nome do Cliente", value=str(projeto_selecionado.get('nome_cliente', 'Sem Nome')), key=f"edit_nome_{prefix_key}")
        novo_tel_cliente = c_cad2.text_input("Telefone / WhatsApp", value=str(projeto_selecionado.get('telefone_cliente', '')), key=f"edit_tel_{prefix_key}")
        
        col_esq, col_meio, col_dir = st.columns(3)
        
        status_atual = projeto_selecionado.get('status_projeto', 'Orçamento Enviado')
        if status_atual == "Cancelado": status_atual = "Orçamento Cancelado"
        if status_atual == "Aguardando Peças": status_atual = "Aguardando Pagamento"

        todas_opcoes = [
            "Orçamento Enviado", "Orçamento Cancelado", "Em Andamento", 
            "Aguardando Pagamento", "Concluído PIX", "Concluído CARTÃO", "Excluir"
        ]
        novo_status = col_esq.selectbox("Alterar Status", todas_opcoes, index=todas_opcoes.index(status_atual) if status_atual in todas_opcoes else 0, key=f"status_{prefix_key}")
        
        data_banco = projeto_selecionado.get('data_conclusao')
        data_inicial = datetime.date.today()
        if pd.notna(data_banco) and str(data_banco).lower() not in ['none', 'nan', 'nat', '']:
            try: data_inicial = pd.to_datetime(data_banco).date()
            except: pass

        if f"last_status_{prefix_key}" not in st.session_state:
            st.session_state[f"last_status_{prefix_key}"] = status_atual

        if f"data_edit_{prefix_key}" not in st.session_state:
            st.session_state[f"data_edit_{prefix_key}"] = data_inicial

        if novo_status != st.session_state[f"last_status_{prefix_key}"]:
            if novo_status in ["Concluído PIX", "Concluído CARTÃO"] and st.session_state[f"last_status_{prefix_key}"] not in ["Concluído PIX", "Concluído CARTÃO"]:
                hoje = datetime.date.today()
                st.session_state[f"data_edit_{prefix_key}"] = hoje
                st.session_state[f"data_{prefix_key}"] = hoje
                
            st.session_state[f"last_status_{prefix_key}"] = novo_status
            st.rerun()

        label_data = "Data de Término" if novo_status in ["Concluído PIX", "Concluído CARTÃO"] else "Data de Inclusão / Previsão"
        
        nova_data = col_meio.date_input(label_data, value=st.session_state[f"data_edit_{prefix_key}"], format="DD/MM/YYYY", key=f"data_{prefix_key}")
        
        st.session_state[f"data_edit_{prefix_key}"] = nova_data

        instalador_atual = str(projeto_selecionado.get('instalador', ''))
        if instalador_atual.lower() in ['nan', 'none']: instalador_atual = ""
        
        opcoes_inst = [""] + lista_instaladores
        idx_inst = opcoes_inst.index(instalador_atual) if instalador_atual in opcoes_inst else 0
        novo_instalador = col_dir.selectbox("Instalador Responsável", opcoes_inst, index=idx_inst, key=f"inst_{prefix_key}")

        st.markdown("#### 🛒 Itens Vendidos (Ajuste Quantidades e Custos)")
        
        lista_prod = df_produtos['Item'].dropna().tolist() if not df_produtos.empty else []
        
        itens_json = projeto_selecionado.get('detalhamento_itens', [])
        df_itens = pd.DataFrame(itens_json) if (isinstance(itens_json, list) and len(itens_json) > 0) else pd.DataFrame()
        
        for col in ['Item', 'Descrição', 'Qtd', 'Custo Un.', 'Venda Un.', 'Custo Total', 'Venda Total']:
            if col not in df_itens.columns: 
                df_itens[col] = 0.0 if 'Un.' in col or 'Qtd' in col or 'Total' in col else ""
            
            if col in ['Qtd', 'Custo Un.', 'Venda Un.', 'Custo Total', 'Venda Total']:
                df_itens[col] = df_itens[col].apply(lambda x: safe_float(x))

        session_key = f"itens_state_{prefix_key}"
        if session_key not in st.session_state:
            if not df_produtos.empty:
                for idx, row in df_itens.iterrows():
                    if safe_float(row.get('Custo Un.')) == 0.0:
                        nome_procurado = str(row.get('Item', '')).strip().upper()
                        match = df_produtos[df_produtos['Item'].astype(str).str.strip().str.upper() == nome_procurado]
                        if not match.empty:
                            df_itens.at[idx, 'Custo Un.'] = safe_float(match.iloc[0].get('Custo (R$)', 0))
                    if safe_float(row.get('Venda Un.')) == 0.0:
                        nome_procurado = str(row.get('Item', '')).strip().upper()
                        match = df_produtos[df_produtos['Item'].astype(str).str.strip().str.upper() == nome_procurado]
                        if not match.empty:
                            df_itens.at[idx, 'Venda Un.'] = safe_float(match.iloc[0].get('Venda (R$)', 0))
            st.session_state[session_key] = df_itens.copy()

        config_itens = {
            "Item": st.column_config.SelectboxColumn("Produto", options=[""] + lista_prod + ["OUTRO"], width="large"),
            "Descrição": st.column_config.TextColumn("Descrição", width="medium"),
            "Qtd": st.column_config.NumberColumn("Qtd", min_value=0, width="small"),
            "Custo Un.": st.column_config.NumberColumn("Custo Fábrica", format="R$ %.2f", width="small"),
            "Venda Un.": st.column_config.NumberColumn("Venda Unt.", format="R$ %.2f", width="small"),
            "Custo Total": st.column_config.NumberColumn("Custo Total", format="R$ %.2f", disabled=True, width="small"),
            "Venda Total": st.column_config.NumberColumn("Venda Total", format="R$ %.2f", disabled=True, width="small")
        }
        
        ordem_cols = ["Item", "Descrição", "Qtd", "Custo Un.", "Venda Un.", "Custo Total", "Venda Total"]
        
        df_itens_editavel = st.data_editor(
            st.session_state[session_key], 
            column_config=config_itens, 
            column_order=ordem_cols,
            num_rows="dynamic", 
            use_container_width=True, 
            key=f"edit_itens_{prefix_key}"
        )
        
        precisa_atualizar = False
        
        # Correção do KeyError: Iterando sobre o índice real para prevenir falhas se alguma linha for apagada
        for idx in df_itens_editavel.index:
            item_atual = str(df_itens_editavel.at[idx, 'Item'] if pd.notna(df_itens_editavel.at[idx, 'Item']) else "").strip()
            item_ant = ""
            if idx in st.session_state[session_key].index:
                item_ant = str(st.session_state[session_key].at[idx, 'Item'] if pd.notna(st.session_state[session_key].at[idx, 'Item']) else "").strip()
                
            if item_atual != item_ant and item_atual != "" and item_atual != "OUTRO":
                match = df_produtos[df_produtos['Item'].astype(str).str.strip().str.upper() == item_atual.upper()]
                if not match.empty:
                    df_itens_editavel.at[idx, 'Custo Un.'] = safe_float(match.iloc[0].get('Custo (R$)', 0))
                    df_itens_editavel.at[idx, 'Venda Un.'] = safe_float(match.iloc[0].get('Venda (R$)', 0))
                    if pd.isna(df_itens_editavel.at[idx, 'Qtd']) or float(df_itens_editavel.at[idx, 'Qtd']) <= 0:
                        df_itens_editavel.at[idx, 'Qtd'] = 1
                    precisa_atualizar = True

            qtd_calc = safe_float(df_itens_editavel.at[idx, 'Qtd'])
            c_un_calc = safe_float(df_itens_editavel.at[idx, 'Custo Un.'])
            v_un_calc = safe_float(df_itens_editavel.at[idx, 'Venda Un.'])
            
            tot_c = qtd_calc * c_un_calc
            tot_v = qtd_calc * v_un_calc
            
            if abs(tot_c - safe_float(df_itens_editavel.at[idx, 'Custo Total'])) > 0.01 or abs(tot_v - safe_float(df_itens_editavel.at[idx, 'Venda Total'])) > 0.01:
                df_itens_editavel.at[idx, 'Custo Total'] = tot_c
                df_itens_editavel.at[idx, 'Venda Total'] = tot_v
                precisa_atualizar = True

        if precisa_atualizar:
            st.session_state[session_key] = df_itens_editavel
            if f"edit_itens_{prefix_key}" in st.session_state:
                del st.session_state[f"edit_itens_{prefix_key}"]
            st.rerun()
            
        df_itens_final = df_itens_editavel
        
        custo_total_produtos = pd.to_numeric(df_itens_final['Custo Total'], errors='coerce').fillna(0).sum()
        venda_total_produtos = pd.to_numeric(df_itens_final['Venda Total'], errors='coerce').fillna(0).sum()
        lucro_total_produtos = venda_total_produtos - custo_total_produtos

        st.markdown(f"""
            <div style='display: flex; justify-content: flex-end; gap: 25px; margin-top: -10px; margin-bottom: 25px;'>
                <span style='color: #cc0000; font-size: 15px;'><b>Custo Total Produtos:</b> {utils.to_br_currency(custo_total_produtos)}</span>
                <span style='color: #006600; font-size: 15px;'><b>Lucro Total Produtos:</b> {utils.to_br_currency(lucro_total_produtos)}</span>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("#### 🧮 Abatimentos e Impostos")
        with st.container(border=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            venda_final = f_col1.number_input("Valor da Venda (R$)", value=safe_float(projeto_selecionado.get('valor_venda_total')), format="%.2f", step=None, key=f"venda_{prefix_key}")
            f_col1.caption(f"Custo Produtos: - {utils.to_br_currency(custo_total_produtos)}") 
            
            emite_nf = f_col2.radio("Nota Fiscal?", ["Não", "Sim"], index=1 if safe_float(projeto_selecionado.get('custo_impostos')) > 0 else 0, key=f"nf_{prefix_key}")
            valor_nf = 0.0
            if emite_nf == "Sim":
                taxa_nf_pct = 6.0
                if not df_taxas_config.empty:
                    for _, t_row in df_taxas_config.iterrows():
                        if "NOTA FISCAL" in str(t_row.get('Item', '')).upper() or "NF" in str(t_row.get('Item', '')).upper():
                            taxa_nf_pct = safe_float(t_row.get('Taxa (%)'))
                            break
                valor_nf = venda_final * (taxa_nf_pct / 100)
                f_col2.caption(f"Imposto ({taxa_nf_pct}%): - {utils.to_br_currency(valor_nf)}")
            else:
                f_col2.caption("&nbsp;", unsafe_allow_html=True)
            
            opcoes_cartao = ["Nenhum / Dinheiro / PIX"]
            dict_taxas = {"Nenhum / Dinheiro / PIX": 0.0}
            
            if not df_taxas_config.empty:
                for _, t_row in df_taxas_config.iterrows():
                    item_nome = str(t_row.get('Item', '')).strip()
                    taxa_val = safe_float(t_row.get('Taxa (%)', 0.0))
                    if "NF" not in item_nome.upper() and "NOTA FISCAL" not in item_nome.upper() and item_nome != "":
                        opcoes_cartao.append(item_nome)
                        dict_taxas[item_nome] = taxa_val

            custo_c_salvo = safe_float(projeto_selecionado.get('custo_cartao'))
            perc_previo = (custo_c_salvo / venda_final * 100) if venda_final > 0 else 0.0
            
            idx_selecionado = 0
            for i, opt in enumerate(opcoes_cartao):
                if abs(dict_taxas[opt] - perc_previo) < 0.01:
                    idx_selecionado = i
                    break
                    
            opcao_escolhida = f_col3.selectbox("PARCELAMENTO CARTÃO", opcoes_cartao, index=idx_selecionado, key=f"taxa_man_{prefix_key}")
            taxa_cartao_pct = dict_taxas[opcao_escolhida]
            valor_cartao_taxa = venda_final * (taxa_cartao_pct / 100)
            f_col3.caption(f"Taxa ({taxa_cartao_pct}%): - {utils.to_br_currency(valor_cartao_taxa)}")

            st.markdown("---")
            f_col4, f_col5, f_col6 = st.columns(3)
            
            perc_comissao_salvo = (safe_float(projeto_selecionado.get('custo_comissao')) / venda_final * 100) if venda_final > 0 else 0.0
            comissao_pct = f_col4.number_input("Comissão (%)", value=float(perc_comissao_salvo), format="%.1f", step=None, key=f"com_{prefix_key}")
            valor_comissao = venda_final * (comissao_pct / 100)
            f_col4.caption(f"Valor: - {utils.to_br_currency(valor_comissao)}")

            d_ct_fallback = projeto_selecionado.get('dados_contrato')
            if not isinstance(d_ct_fallback, dict): d_ct_fallback = {}
            
            val_mo_salvo = safe_float(projeto_selecionado.get('custo_terceirizados'))
            if val_mo_salvo == 0.0 and safe_float(d_ct_fallback.get('val_servico')) > 0:
                val_mo_salvo = safe_float(d_ct_fallback.get('val_servico'))
                
            val_ext_salvo = safe_float(projeto_selecionado.get('custo_adicional_materiais'))
            if val_ext_salvo == 0.0 and safe_float(d_ct_fallback.get('val_outros')) > 0:
                val_ext_salvo = safe_float(d_ct_fallback.get('val_outros'))

            custo_ext = f_col5.number_input("Materiais Extras (R$)", value=val_ext_salvo, format="%.2f", step=None, key=f"mat_{prefix_key}")
            f_col5.caption("&nbsp;", unsafe_allow_html=True) 

            custo_mo = f_col6.number_input("Mão de Obra / Terceiros (R$)", value=val_mo_salvo, format="%.2f", step=None, key=f"mao_{prefix_key}")
            f_col6.caption("&nbsp;", unsafe_allow_html=True) 

            abatimentos = valor_nf + valor_cartao_taxa + valor_comissao + custo_ext + custo_mo
            lucro_final = venda_final - custo_total_produtos - abatimentos
            
            st.markdown("<br>", unsafe_allow_html=True)
            r1, r2 = st.columns(2)
            r1.metric("Custo Total (Produtos + Taxas)", utils.to_br_currency(custo_total_produtos + abatimentos))
            margem_r = (lucro_final / venda_final * 100) if venda_final > 0 else 0
            r2.metric("LUCRO LÍQUIDO FINAL", utils.to_br_currency(lucro_final), delta=f"{margem_r:.1f}% Margem")

        notas = st.text_area("Observações", value=str(projeto_selecionado.get('notas_internas', '')) if str(projeto_selecionado.get('notas_internas', '')) != 'nan' else '', key=f"notas_{prefix_key}")

        nova_nf_entrada = ""
        novo_venc_boleto = None

        if novo_status not in ["Orçamento Enviado", "Orçamento Cancelado", "Excluir"]:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("#### 🧾 Informações Fiscais e Boletos")
            
            c_nf, c_venc = st.columns(2)
            
            nf_entrada_banco = projeto_selecionado.get('nf_entrada', '')
            venc_boleto_banco = projeto_selecionado.get('vencimento_boleto')
            
            venc_boleto_inicial = None
            if pd.notna(venc_boleto_banco) and str(venc_boleto_banco).lower() not in ['none', 'nan', 'nat', '']:
                try: venc_boleto_inicial = pd.to_datetime(venc_boleto_banco).date()
                except: pass

            try:
                res_bol_check = supabase.table('boletos_fornecedores').select('*').eq('servico_id', int(projeto_selecionado['id'])).execute()
                boletos_importados = res_bol_check.data
            except:
                boletos_importados = []
                
            if boletos_importados and venc_boleto_inicial is None:
                try:
                    venc_b_temp = boletos_importados[0].get('vencimento')
                    if venc_b_temp:
                        venc_boleto_inicial = pd.to_datetime(venc_b_temp).date()
                except:
                    pass
            
            nova_nf_entrada = c_nf.text_input("NF de Entrada", value=str(nf_entrada_banco) if str(nf_entrada_banco) != 'nan' else '', placeholder="Opcional", key=f"nf_ent_{prefix_key}")
            novo_venc_boleto = c_venc.date_input("Vencimento Boleto (Cliente)", value=venc_boleto_inicial, format="DD/MM/YYYY", key=f"venc_bol_{prefix_key}")

            with st.container(border=True):
                st.markdown("##### 📥 Importar Boletos de Fornecedores (PDF)")
                
                if boletos_importados:
                    st.success(f"✅ {len(boletos_importados)} boleto(s) de fornecedor(es) já importado(s).")
                    for i_bol, b_imp in enumerate(boletos_importados):
                        dt_str = "Sem data"
                        try: 
                            dt_b = pd.to_datetime(b_imp.get('vencimento'))
                            if pd.notna(dt_b): dt_str = dt_b.strftime('%d/%m/%Y')
                        except: pass
                        
                        val_str = utils.to_br_currency(b_imp.get('valor', 0))
                        link = b_imp.get('link_drive_id', '')
                        # Indexação robusta para evitar erro de chaves duplicadas no widget do Streamlit
                        b_id = b_imp.get('id', f'desc_{i_bol}')
                        
                        c_bol1, c_bol2 = st.columns([4, 1])
                        with c_bol1:
                            if link:
                                st.markdown(f"📄 **Venc:** {dt_str} | **Valor:** {val_str} | <a href='https://drive.google.com/file/d/{link}/view' target='_blank'>👁️ Ver PDF</a>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"📄 **Venc:** {dt_str} | **Valor:** {val_str}")
                        with c_bol2:
                            if st.button("🗑️ Remover", key=f"del_bol_{b_id}_{prefix_key}"):
                                try:
                                    supabase.table('boletos_fornecedores').delete().eq('id', b_id).execute()
                                    if link: utils.delete_drive_file(link)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao remover: {e}")
                    st.markdown("---")
                
                # Controle rigoroso do Uploader para impedir loops de memória
                upload_key_name = f"up_bol_k_{prefix_key}"
                if upload_key_name not in st.session_state:
                    st.session_state[upload_key_name] = 0

                arquivo_boleto = st.file_uploader("Anexar PDF de um Novo Boleto para leitura de IA", type=["pdf"], key=f"up_bol_{prefix_key}_{st.session_state[upload_key_name]}")
                
                if arquivo_boleto:
                    if f"dados_bol_{prefix_key}" not in st.session_state:
                        with st.spinner("🤖 Lendo dados do boleto..."):
                            venc_ext, val_ext = utils.extrair_dados_boleto(arquivo_boleto)
                            st.session_state[f"dados_bol_{prefix_key}"] = {"vencimento": venc_ext, "valor": val_ext}

                    dados_ext = st.session_state.get(f"dados_bol_{prefix_key}", {})
                    
                    st.caption("Verifique e corrija os dados extraídos pelo sistema:")
                    col_b1, col_b2 = st.columns(2)
                    
                    venc_obj = datetime.date.today()
                    if dados_ext.get('vencimento'):
                        try: venc_obj = datetime.datetime.strptime(dados_ext['vencimento'], "%d/%m/%Y").date()
                        except: pass
                    
                    data_confirmada = col_b1.date_input("Vencimento do Fornecedor", value=venc_obj, format="DD/MM/YYYY", key=f"conf_data_{prefix_key}")
                    valor_confirmado = col_b2.number_input("Valor Extraído (R$)", value=float(dados_ext.get('valor', 0.0)), format="%.2f", step=None, key=f"conf_val_{prefix_key}")
                    
                    if st.button("🚀 Salvar Boleto e Criar Lembrete", type="primary", use_container_width=True, key=f"btn_salvar_bol_{prefix_key}"):
                        if not data_confirmada:
                            st.error("⚠️ A data de vencimento não pode estar vazia.")
                        else:
                            with st.spinner("Salvando no Drive e no ERP..."):
                                mes_idx = data_confirmada.month
                                nome_mes_pasta = utils.meses_pt[mes_idx - 1]
                                
                                partes_nome = novo_nome_cliente.strip().split() if novo_nome_cliente and novo_nome_cliente.strip() else []
                                nome_cliente_limpo = partes_nome[0] if partes_nome else "Cliente"
                                
                                timestamp_str = datetime.datetime.now().strftime('%H%M%S')
                                nome_arquivo_drive = f"FORNECEDOR_{nome_cliente_limpo}_{data_confirmada.strftime('%d%m%Y')}_{timestamp_str}.pdf"
                                
                                arquivo_boleto.seek(0)
                                
                                sucesso, link_id = utils.upload_to_drive(
                                    file_buffer=arquivo_boleto, 
                                    filename=nome_arquivo_drive, 
                                    mimetype="application/pdf", 
                                    folder_path=["Boletos", nome_mes_pasta]
                                )
                                
                                if sucesso:
                                    novo_boleto = {
                                        "cliente": novo_nome_cliente if novo_nome_cliente else "Cliente",
                                        "servico_id": int(projeto_selecionado['id']),
                                        "vencimento": data_confirmada.strftime("%Y-%m-%d"),
                                        "valor": valor_confirmado,
                                        "link_drive_id": link_id,
                                        "status": "Pendente"
                                    }
                                    try:
                                        supabase.table('boletos_fornecedores').insert(novo_boleto).execute()
                                        utils.sincronizar_boletos_com_calendar()
                                        
                                        if pd.isna(venc_boleto_banco) or str(venc_boleto_banco).lower() in ['none', 'nan', 'nat', '']:
                                            supabase.table('servicos_andamento').update({'vencimento_boleto': data_confirmada.strftime('%Y-%m-%d')}).eq('id', int(projeto_selecionado['id'])).execute()
                                        
                                        st.success(f"✅ Boleto salvo com sucesso!")
                                        if f"dados_bol_{prefix_key}" in st.session_state:
                                            del st.session_state[f"dados_bol_{prefix_key}"]
                                            
                                        # Ejetar o arquivo do uploader para impedir leituras duplicadas (Anti-Crash Memory Bug)
                                        st.session_state[upload_key_name] += 1
                                        st.rerun() 
                                    except Exception as e:
                                        st.error(f"Erro no banco de dados. Detalhe: {e}")
                                else:
                                    st.error(f"Erro ao fazer o upload para o Google Drive. Detalhes: {link_id}")

        st.markdown("<br>", unsafe_allow_html=True)
        
        with st.expander("📄 GERAR PDF DO ORÇAMENTO"):
            col_pdf1, col_pdf2 = st.columns([1, 1])
            modelo_capa = col_pdf1.selectbox("Modelo para Capa", [
                "Aquecedor Solar Tradicional", "Aquecedor Solar a Vácuo Acoplado", 
                "Aquecedor Solar Modular", "Aquecedor de Piscina - Tradicional", 
                "Aquecedor de Piscina - Trocador de Calor", "Sistema de Pressurização"
            ], index=3, key=f"capa_{prefix_key}")
            
            if col_pdf2.button("GERAR PRÉVIA DO PDF", use_container_width=True, key=f"btn_pdf_{prefix_key}"):
                df_pdf = df_itens_final.copy()
                if not df_pdf.empty:
                    df_pdf['Quantidade'] = df_pdf.get('Qtd', 0)
                    df_pdf['Produto da Base'] = df_pdf.get('Item', '')
                    df_pdf['Produto Manual'] = ""
                    df_pdf['Venda Total'] = df_pdf['Quantidade'] * df_pdf.get('Venda Un.', 0)
                    df_pdf['Descrição'] = df_pdf.get('Descrição', "")
                else:
                    df_pdf = pd.DataFrame(columns=['Quantidade', 'Produto da Base', 'Produto Manual', 'Venda Total', 'Descrição'])
                
                obs_pdf = str(projeto_selecionado.get('notas_internas', 'Material Hidráulico não incluído na proposta'))
                if obs_pdf == 'nan' or obs_pdf.strip() == '': obs_pdf = "Material Hidráulico não incluído na proposta"

                pdf_bytes = utils.gerar_pdf_orcamento(
                    nome=novo_nome_cliente, tel=novo_tel_cliente, 
                    capa=modelo_capa, df_items=df_pdf, d_s=str(projeto_selecionado.get('servicos_adquiridos', '')).replace('nan',''), 
                    v_s=0.0, d_o="", v_o=0.0, total=safe_float(projeto_selecionado.get('valor_venda_total')), obs=obs_pdf, mostrar_un=False
                )
                st.session_state[f'pdf_gerado_{prefix_key}'] = pdf_bytes
                
            if f'pdf_gerado_{prefix_key}' in st.session_state:
                st.download_button("📥 BAIXAR PDF DO ORÇAMENTO", data=st.session_state[f'pdf_gerado_{prefix_key}'], file_name=f"ORCAMENTO_{novo_nome_cliente}.pdf", mime="application/pdf", use_container_width=True, key=f"dl_pdf_{prefix_key}")

        status_contrato_permitido = ["Em Andamento", "Aguardando Pagamento", "Concluído PIX", "Concluído CARTÃO"]
        if novo_status in status_contrato_permitido:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("📝 GERAR CONTRATO"):
                
                d_ct = projeto_selecionado.get('dados_contrato')
                if not isinstance(d_ct, dict): d_ct = {}

                st.markdown("#### Dados do Cliente para o Contrato")
                c_tipo = st.radio("Tipo de Cliente", ["Pessoa Física", "Pessoa Jurídica"], horizontal=True, index=0 if d_ct.get('tipo', 'Pessoa Física') == 'Pessoa Física' else 1, key=f"ct_tipo_{prefix_key}")
                c_nome = st.text_input("Nome Completo / Razão Social", value=d_ct.get('nome', novo_nome_cliente), key=f"ct_nome_{prefix_key}")
                c_cpf = st.text_input("CPF" if c_tipo == "Pessoa Física" else "CNPJ", value=d_ct.get('cpf', ''), key=f"ct_cpf_{prefix_key}")

                st.markdown("#### Endereço do Cliente")
                col_cep1, col_cep2 = st.columns([1, 2])
                
                if f"ct_rua_{prefix_key}" not in st.session_state: st.session_state[f"ct_rua_{prefix_key}"] = d_ct.get('rua', '')
                if f"ct_num_{prefix_key}" not in st.session_state: st.session_state[f"ct_num_{prefix_key}"] = d_ct.get('num', '')
                if f"ct_bairro_{prefix_key}" not in st.session_state: st.session_state[f"ct_bairro_{prefix_key}"] = d_ct.get('bairro', '')
                if f"ct_cid_{prefix_key}" not in st.session_state: st.session_state[f"ct_cid_{prefix_key}"] = d_ct.get('cidade', '')
                if f"ct_uf_{prefix_key}" not in st.session_state: st.session_state[f"ct_uf_{prefix_key}"] = d_ct.get('uf', '')

                c_cep = col_cep1.text_input("CEP", placeholder="00000-000", value=d_ct.get('cep', ''), key=f"ct_cep_{prefix_key}")

                if col_cep2.button("🔍 Buscar CEP", key=f"btn_cep_{prefix_key}"):
                    end_dados = utils.buscar_cep(c_cep)
                    if end_dados:
                        st.session_state[f"ct_rua_{prefix_key}"] = end_dados.get('logradouro', '')
                        st.session_state[f"ct_bairro_{prefix_key}"] = end_dados.get('bairro', '')
                        st.session_state[f"ct_cid_{prefix_key}"] = end_dados.get('localidade', '')
                        st.session_state[f"ct_uf_{prefix_key}"] = end_dados.get('uf', '')
                        st.rerun() 
                    else:
                        st.error("CEP não encontrado ou inválido.")

                c_rua = st.text_input("Rua / Logradouro", key=f"ct_rua_{prefix_key}")
                col_num, col_bairro = st.columns([1, 2])
                c_num = col_num.text_input("Número", key=f"ct_num_{prefix_key}")
                c_bairro = col_bairro.text_input("Bairro", key=f"ct_bairro_{prefix_key}")

                col_cid, col_uf = st.columns([2, 1])
                c_cidade = col_cid.text_input("Cidade", key=f"ct_cid_{prefix_key}")
                c_uf = col_uf.text_input("Estado (UF)", key=f"ct_uf_{prefix_key}")

                st.markdown("#### Estrutura do Contrato")
                c_objeto = st.text_area("Objeto do Contrato (Opcional)", value=d_ct.get('objeto', ''), height=80, key=f"ct_obj_{prefix_key}")
                c_mat = st.radio("Materiais Hidráulicos Inclusos na Proposta?", ["Não", "Sim"], index=0 if d_ct.get('mat_inclusos', 'Não') == 'Não' else 1, horizontal=True, key=f"ct_mat_{prefix_key}")
                
                data_t = datetime.date.today()
                if d_ct.get('data_termino'):
                    try: data_t = datetime.datetime.strptime(d_ct.get('data_termino'), "%Y-%m-%d").date()
                    except: pass
                c_data_term = st.date_input("Data de Término do Serviço (Para base da Garantia)", value=data_t, format="DD/MM/YYYY", key=f"ct_term_{prefix_key}")
                
                st.markdown("#### Valores e Pagamento")
                col_val1, col_val2 = st.columns(2)
                c_val_base = col_val1.number_input("Valor Base / Equipamentos (R$)", value=float(d_ct.get('val_base', venda_final)), format="%.2f", step=None, key=f"ct_val_base_{prefix_key}")
                c_val_inst = col_val2.number_input("Valor da Instalação (R$ - Opcional)", value=float(d_ct.get('val_inst', 0.0)), format="%.2f", step=None, key=f"ct_val_inst_{prefix_key}")
                
                col_val3, col_val4 = st.columns(2)
                c_val_hidr = col_val3.number_input("Valor Materiais Hidráulicos (R$ - Opcional)", value=float(d_ct.get('val_hidr', 0.0)), format="%.2f", step=None, key=f"ct_val_hidr_{prefix_key}")
                c_val_outros = col_val4.number_input("Valor Outros Serviços (R$ - Opcional)", value=float(d_ct.get('val_outros', 0.0)), format="%.2f", step=None, key=f"ct_val_outros_{prefix_key}")
                
                c_desc_outros = ""
                if c_val_outros > 0:
                    c_desc_outros = st.text_input("Descrição dos Outros Serviços", value=d_ct.get('desc_outros', ''), key=f"ct_desc_outros_{prefix_key}")

                lista_pag = ["PIX", "Cartão de Crédito", "Cartão de Débito", "Boleto", "Dinheiro", "Transferência Bancária"]
                c_pagamento = st.selectbox("Forma de Pagamento Acordada", lista_pag, index=lista_pag.index(d_ct.get('pagamento', 'PIX')), key=f"ct_pag_{prefix_key}")
                c_obs_pag = st.text_input("Observações do Pagamento (Opcional)", value=d_ct.get('obs_pagamento', ''), key=f"ct_obs_pag_{prefix_key}")

                total_ct = c_val_base + c_val_inst + c_val_hidr + c_val_outros
                st.markdown(f"<span style='color:#004488; font-weight:bold;'>Total do Contrato: {utils.to_br_currency(total_ct)}</span>", unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                
                col_b1, col_b2 = st.columns(2)
                
                if col_b1.button("💾 SALVAR DADOS DO CONTRATO", use_container_width=True, key=f"btn_sv_ct_{prefix_key}"):
                    payload = {
                        "tipo": c_tipo, "nome": c_nome, "cpf": c_cpf, "cep": c_cep, "rua": c_rua, "num": c_num, 
                        "bairro": c_bairro, "cidade": c_cidade, "uf": c_uf, "objeto": c_objeto, "mat_inclusos": c_mat, 
                        "data_termino": c_data_term.strftime("%Y-%m-%d"), "pagamento": c_pagamento, "obs_pagamento": c_obs_pag, 
                        "val_base": c_val_base, "val_inst": c_val_inst, "val_hidr": c_val_hidr, 
                        "val_outros": c_val_outros, "desc_outros": c_desc_outros
                    }
                    try:
                        supabase.table('servicos_andamento').update({"dados_contrato": payload}).eq('id', int(projeto_selecionado['id'])).execute()
                        st.success("✅ Dados do contrato salvos com sucesso!")
                    except Exception as e:
                        st.error("⚠️ ERRO: Certifique-se de que a coluna 'dados_contrato' existe no Supabase.")

                if col_b2.button("📄 GERAR PDF DO CONTRATO", type="primary", use_container_width=True, key=f"btn_gerar_pdf_ct_{prefix_key}"):
                    if not c_nome or not c_cpf or not c_rua or not c_num:
                        st.warning("Preencha Nome, CPF/CNPJ, Rua e Número para gerar o contrato!")
                    else:
                        end_completo = f"{c_rua}, nº {c_num} - {c_bairro}, {c_cidade} - {c_uf}, CEP: {c_cep}"
                        
                        df_ct_itens = df_itens_final.copy()
                        descricoes = []
                        for _, r in df_ct_itens.iterrows():
                            match = df_produtos[df_produtos['Item'] == r['Item']]
                            descricoes.append(match['Descrição'].values[0] if not match.empty else "")
                        df_ct_itens['Descrição'] = descricoes

                        pdf_ct_bytes = utils.gerar_pdf_contrato(
                            nome=c_nome, doc=c_cpf, tipo_cliente=c_tipo, endereco=end_completo,
                            objeto=c_objeto, df_items=df_ct_itens, mat_inclusos=c_mat,
                            forma_pagamento=c_pagamento, obs_pagamento=c_obs_pag, data_termino=c_data_term,
                            val_base=c_val_base, val_inst=c_val_inst, val_hidr=c_val_hidr, 
                            val_outros=c_val_outros, desc_outros=c_desc_outros
                        )
                        st.session_state[f'pdf_contrato_{prefix_key}'] = pdf_ct_bytes
                        st.success("✅ Contrato gerado! Clique no botão abaixo para baixar.")

                if f'pdf_contrato_{prefix_key}' in st.session_state:
                    st.download_button("📥 BAIXAR CONTRATO (PDF)", data=st.session_state[f'pdf_contrato_{prefix_key}'], file_name=f"CONTRATO_{c_nome.split()[0]}.pdf", mime="application/pdf", use_container_width=True, key=f"dl_ct_{prefix_key}")
                    
                    with st.container(border=True):
                        st.markdown("☁️ **Salvar no Drive (Pasta: Contratos)**")
                        
                        hoje_str = datetime.datetime.now().strftime("%Y_%m_%d")
                        partes_nome = c_nome.strip().split()
                        if len(partes_nome) >= 2:
                            nome_formatado = f"{partes_nome[0]}_{partes_nome[-1]}".lower()
                        else:
                            nome_formatado = partes_nome[0].lower() if partes_nome else "cliente"
                        
                        nome_sugerido = f"contrato_{hoje_str}_{nome_formatado}.pdf"
                        
                        nome_arquivo_drive = st.text_input("Nome do arquivo do contrato:", value=nome_sugerido, key=f"input_nome_ct_drive_{prefix_key}")
                        
                        if st.button("🚀 Enviar Contrato para o Drive", use_container_width=True, key=f"btn_upload_ct_drive_{prefix_key}"):
                            with st.spinner("Salvando na pasta Contratos..."):
                                sucesso, msg = utils.upload_to_drive(
                                    file_buffer=st.session_state[f'pdf_contrato_{prefix_key}'], 
                                    filename=nome_arquivo_drive, 
                                    mimetype="application/pdf", 
                                    folder_path=["Contratos"]
                                )
                                if sucesso:
                                    st.success(f"✅ Contrato {nome_arquivo_drive} salvo com sucesso no Drive!")
                                else:
                                    st.error(f"Erro ao salvar: {msg}")

        st.markdown("<br>", unsafe_allow_html=True)
        
        if novo_status == "Excluir":
            st.error("⚠️ **ATENÇÃO:** Você selecionou a opção de Excluir. Isso apagará permanentemente este cliente e orçamento do sistema.")
            if st.button("🗑️ CONFIRMAR EXCLUSÃO", type="primary", use_container_width=True, key=f"del_{prefix_key}"):
                try:
                    supabase.table('servicos_andamento').delete().eq('id', int(projeto_selecionado['id'])).execute()
                    st.success("✅ Orçamento excluído com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao excluir: {e}")
        else:
            if st.button("💾 SALVAR PROJETO", type="primary", use_container_width=True, key=f"save_{prefix_key}"):
                dados = {
                    "nome_cliente": novo_nome_cliente,
                    "telefone_cliente": novo_tel_cliente,
                    "status_projeto": novo_status, 
                    "data_conclusao": nova_data.strftime('%Y-%m-%d'),
                    "instalador": novo_instalador,
                    "detalhamento_itens": df_itens_final.fillna("").to_dict('records'),
                    "custo_adicional_materiais": custo_ext, 
                    "custo_terceirizados": custo_mo,
                    "custo_comissao": valor_comissao, 
                    "custo_impostos": valor_nf,
                    "custo_cartao": valor_cartao_taxa, 
                    "valor_venda_total": venda_final,
                    "lucro_estimado": lucro_final, 
                    "notas_internas": notas,
                    "nf_entrada": nova_nf_entrada,
                    "vencimento_boleto": novo_venc_boleto.strftime('%Y-%m-%d') if novo_venc_boleto else None
                }
                try:
                    supabase.table('servicos_andamento').update(dados).eq('id', int(projeto_selecionado['id'])).execute()
                    if f"itens_state_{prefix_key}" in st.session_state:
                        del st.session_state[f"itens_state_{prefix_key}"]
                    if f"last_status_{prefix_key}" in st.session_state: 
                        del st.session_state[f"last_status_{prefix_key}"]
                    if f"data_edit_{prefix_key}" in st.session_state: 
                        del st.session_state[f"data_edit_{prefix_key}"]
                    
                    st.success("✅ Atualizado com sucesso!")
                    st.rerun()
                except Exception as e: 
                    st.error(f"Erro ao salvar. Verifique se as colunas 'nf_entrada', 'vencimento_boleto' e 'instalador' foram criadas no Supabase. Detalhe: {e}")

    # Captura 100% de qualquer erro fatal antes que derrube o Streamlit ("Oh no. Error running app.")
    except Exception as global_e:
        st.error(f"⚠️ **Erro Interno de Execução:** Ocorreu uma falha ao renderizar este painel.")
        st.info("Para que o suporte possa ajudar, por favor tire um print do erro abaixo:")
        st.code(traceback.format_exc(), language="python")
