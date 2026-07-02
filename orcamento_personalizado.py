import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar(lista_nomes_produtos, limpar_func):
    deve_rerun = False
    cat_produtos = st.session_state.db_produtos

    try:
        res_rascunhos = st.session_state.supabase.table('servicos_andamento').select('id, nome_cliente, valor_venda_total').eq('status_projeto', 'Rascunho').execute()
        rascunhos_db = res_rascunhos.data
    except Exception:
        rascunhos_db = []

    if rascunhos_db or st.session_state.get('rascunho_id'):
        with st.expander("📂 Continuar Rascunho Salvo", expanded=True if st.session_state.get('rascunho_id') else False):
            if st.session_state.get('rascunho_id'):
                st.success("✏️ Você está editando um rascunho em andamento.")
                if st.button("❌ Fechar Rascunho e Iniciar Novo Orçamento", use_container_width=True):
                    limpar_func()
                    deve_rerun = True
            else:
                c_sel, c_btn_load, c_btn_del = st.columns([3, 1, 1])
                opcoes_rascunhos = {f"{r['nome_cliente']} (R$ {r.get('valor_venda_total', 0):.2f}) - ID: {r['id']}": r['id'] for r in rascunhos_db}
                rasc_selecionado = c_sel.selectbox("Selecione um rascunho:", list(opcoes_rascunhos.keys()), label_visibility="collapsed")

                if c_btn_load.button("📥 Carregar", use_container_width=True):
                    id_r = opcoes_rascunhos[rasc_selecionado]
                    res_full = st.session_state.supabase.table('servicos_andamento').select('*').eq('id', id_r).execute()
                    if res_full.data:
                        r_data = res_full.data[0]
                        st.session_state.rascunho_id = r_data['id']
                        st.session_state.input_nome_cliente = r_data.get('nome_cliente', '')
                        st.session_state.input_whatsapp = r_data.get('telefone_cliente', '')
                        st.session_state.txt_servico = r_data.get('servicos_adquiridos', '')
                        
                        d_ct = r_data.get('dados_contrato') or {}
                        st.session_state.val_servico = float(d_ct.get('val_servico', 0.0))
                        st.session_state.txt_outros = d_ct.get('txt_outros', '')
                        st.session_state.val_outros = float(d_ct.get('val_outros', 0.0))
                        st.session_state.input_obs_pdf = d_ct.get('obs_pdf', 'Material Hidráulico não incluído na proposta')

                        itens = r_data.get('detalhamento_itens', [])
                        novo_df = []
                        for it in itens:
                            v_un = float(it.get('Venda Un.', 0.0))
                            qtd = float(it.get('Qtd', 0))
                            
                            c_un = 0.0
                            p_nome = it.get('Item', '')
                            p_manual = ""
                            
                            if p_nome and p_nome not in lista_nomes_produtos and p_nome != "OUTRO":
                                p_manual = p_nome
                                p_nome = "OUTRO"
                            elif p_nome:
                                match_c = cat_produtos[cat_produtos['Item'].astype(str).str.strip() == p_nome]
                                if not match_c.empty:
                                    c_un = float(match_c.get('Custo (R$)', pd.Series([0.0])).values[0])

                            novo_df.append({
                                "Produto da Base": p_nome,
                                "Produto Manual": p_manual,
                                "Descrição": it.get('Descrição', ''),
                                "Quantidade": qtd,
                                "Custo (R$)": c_un,
                                "Venda (R$)": v_un,
                                "Custo Total": qtd * c_un,
                                "Venda Total": qtd * v_un
                            })
                            
                        while len(novo_df) < 5:
                            novo_df.append({"Produto da Base": "", "Produto Manual": "", "Descrição": "", "Quantidade": 0, "Custo (R$)": 0.0, "Venda (R$)": 0.0, "Custo Total": 0.0, "Venda Total": 0.0})
                        
                        st.session_state.df_orc = pd.DataFrame(novo_df)
                        st.session_state.df_orc_prev = st.session_state.df_orc.copy()
                        if "editor_orc_base" in st.session_state: 
                            del st.session_state["editor_orc_base"]
                        deve_rerun = True

                if c_btn_del.button("🗑️ Excluir", use_container_width=True):
                    id_r = opcoes_rascunhos[rasc_selecionado]
                    st.session_state.supabase.table('servicos_andamento').delete().eq('id', id_r).execute()
                    st.success("✅ Rascunho excluído permanentemente.")
                    deve_rerun = True

    with st.container(border=True):
        st.subheader("👤 Dados do Cliente")
        col1, col2 = st.columns(2)
        
        nome_cliente = col1.text_input("Nome do Cliente", key="input_nome_cliente")
        whatsapp = col2.text_input("WhatsApp", placeholder="(31) 99715-1596", key="input_whatsapp")
        
        modelo_capa = st.selectbox("Modelo para Capa", [
            "Aquecedor Solar Tradicional", 
            "Aquecedor Solar a Vácuo Acoplado", 
            "Aquecedor Solar Modular", 
            "Aquecedor de Piscina - Tradicional", 
            "Aquecedor de Piscina - Trocador de Calor", 
            "Sistema de Pressurização"
        ], index=1)

    with st.container(border=True):
        st.subheader("⚙️ 1. Equipamentos")
        mostrar_precos_unitarios = st.checkbox("Mostrar Preços Unitários no PDF?", value=False)
        
        if 'df_orc' not in st.session_state:
            linhas_iniciais = []
            for _ in range(5):
                linhas_iniciais.append({
                    "Produto da Base": "", 
                    "Produto Manual": "", 
                    "Descrição": "", 
                    "Quantidade": 0, 
                    "Custo (R$)": 0.0, 
                    "Venda (R$)": 0.0, 
                    "Custo Total": 0.0, 
                    "Venda Total": 0.0
                })
            st.session_state.df_orc = pd.DataFrame(linhas_iniciais)
        
        if 'df_orc_prev' not in st.session_state:
            st.session_state.df_orc_prev = st.session_state.df_orc.copy()
        
        configuracao_colunas = {
            "Produto da Base": st.column_config.SelectboxColumn("Produto", options=[""] + lista_nomes_produtos + ["OUTRO"], width="medium"), 
            "Produto Manual": st.column_config.TextColumn("Nome Manual", width="medium"),
            "Descrição": st.column_config.TextColumn("Detalhes / Garantia"), 
            "Quantidade": st.column_config.NumberColumn("Qtd", min_value=0, step=1, width="small"),
            "Custo (R$)": st.column_config.NumberColumn("Custo Unt.", format="R$ %,.2f", width="small"),
            "Venda (R$)": st.column_config.NumberColumn("Venda Unt.", format="R$ %,.2f", width="small"),
            "Custo Total": st.column_config.NumberColumn("Custo Total", format="R$ %,.2f", disabled=True, width="small"),
            "Venda Total": st.column_config.NumberColumn("Total", format="R$ %,.2f", disabled=True, width="small")
        }
        
        sequencia_colunas = ["Produto da Base", "Produto Manual", "Quantidade", "Custo (R$)", "Venda (R$)", "Custo Total", "Venda Total"]
        
        df_editavel = st.data_editor(
            st.session_state.df_orc, 
            column_config=configuracao_colunas, 
            column_order=sequencia_colunas,
            num_rows="dynamic", 
            use_container_width=True, 
            key="editor_orc_base"
        )
        df_editavel = df_editavel.reset_index(drop=True)
        
        precisa_atualizar_tela = False
        
        for i in range(len(df_editavel)):
            produto_atual = str(df_editavel.at[i, 'Produto da Base']).strip()
            if produto_atual.lower() in ['nan', 'none', '']: 
                produto_atual = ""
            
            produto_anterior = ""
            if i < len(st.session_state.df_orc_prev):
                produto_anterior = str(st.session_state.df_orc_prev.at[i, 'Produto da Base']).strip()
                if produto_anterior.lower() in ['nan', 'none', '']: 
                    produto_anterior = ""

            df_editavel.at[i, 'Produto da Base'] = produto_atual

            if produto_atual != produto_anterior and produto_atual != "" and produto_atual != "OUTRO":
                match_base = cat_produtos[cat_produtos['Item'].astype(str).str.strip() == produto_atual]
                
                if not match_base.empty:
                    val_venda = match_base['Venda (R$)'].values[0]
                    val_custo = match_base.get('Custo (R$)', pd.Series([0.0])).values[0]
                    desc_base = match_base['Descrição'].values[0]
                    
                    try: preco_novo = float(val_venda)
                    except Exception: preco_novo = 0.0
                        
                    try: custo_novo = float(val_custo)
                    except Exception: custo_novo = 0.0
                        
                    df_editavel.at[i, 'Venda (R$)'] = preco_novo
                    df_editavel.at[i, 'Custo (R$)'] = custo_novo
                    df_editavel.at[i, 'Descrição'] = str(desc_base) if pd.notna(desc_base) and str(desc_base).lower() != 'nan' else ""
                    
                    if pd.isna(df_editavel.at[i, 'Quantidade']) or float(df_editavel.at[i, 'Quantidade']) <= 0:
                        df_editavel.at[i, 'Quantidade'] = 1
                        
                    precisa_atualizar_tela = True

            qtd = float(df_editavel.at[i, 'Quantidade']) if pd.notna(df_editavel.at[i, 'Quantidade']) else 0.0
            preco = float(df_editavel.at[i, 'Venda (R$)']) if pd.notna(df_editavel.at[i, 'Venda (R$)']) else 0.0
            custo_un = float(df_editavel.at[i, 'Custo (R$)']) if pd.notna(df_editavel.at[i, 'Custo (R$)']) else 0.0
            
            total_venda_calc = qtd * preco
            total_custo_calc = qtd * custo_un
            
            total_venda_tela = float(df_editavel.at[i, 'Venda Total']) if pd.notna(df_editavel.at[i, 'Venda Total']) else 0.0
            total_custo_tela = float(df_editavel.at[i, 'Custo Total']) if pd.notna(df_editavel.at[i, 'Custo Total']) else 0.0
            
            if abs(total_venda_calc - total_venda_tela) > 0.01 or abs(total_custo_calc - total_custo_tela) > 0.01:
                df_editavel.at[i, 'Venda Total'] = total_venda_calc
                df_editavel.at[i, 'Custo Total'] = total_custo_calc
                precisa_atualizar_tela = True

        if precisa_atualizar_tela:
            st.session_state.df_orc = df_editavel
            st.session_state.df_orc_prev = df_editavel.copy()
            if "editor_orc_base" in st.session_state:
                del st.session_state["editor_orc_base"]
            deve_rerun = True

        subtotal_equipamentos = df_editavel['Venda Total'].sum()
        st.markdown(f"**Subtotal Equipamentos:** :blue[{utils.to_br_currency(subtotal_equipamentos)}]")
        
        mostrar_lucro = st.toggle("Exibir Custos, Margem e Lucro Estimado", value=False)
        if mostrar_lucro:
            custo_total_produtos = pd.to_numeric(df_editavel["Custo Total"], errors='coerce').fillna(0).sum()
            venda_total_produtos = subtotal_equipamentos
            lucro_total_produtos = venda_total_produtos - custo_total_produtos
            
            st.markdown(f"""
                <div style='display: flex; justify-content: flex-start; gap: 25px; margin-top: 10px; margin-bottom: 5px;'>
                    <span style='color: #cc0000; font-size: 15px;'><b>Custo Total Produtos:</b> {utils.to_br_currency(custo_total_produtos)}</span>
                    <span style='color: #006600; font-size: 15px;'><b>Lucro Total Produtos:</b> {utils.to_br_currency(lucro_total_produtos)}</span>
                </div>
            """, unsafe_allow_html=True)
            
            margem_equip = (lucro_total_produtos / custo_total_produtos * 100) if custo_total_produtos > 0 else (100.0 if lucro_total_produtos > 0 else 0.0)
            
            html_lucro = f"""
            <div style='background-color: #e6ffe6; padding: 10px; border-radius: 5px; border: 1px solid #006600; margin-top: 10px; margin-bottom: 5px;'>
                <span style='color: #006600; font-weight: bold; font-size: 16px;'>💸 Lucro Projetado: {utils.to_br_currency(lucro_total_produtos)} ({margem_equip:.1f}%)</span><br>
                <small style='color: #444;'><i>(Calculado apenas sobre o custo total acumulado dos equipamentos)</i></small>
            </div>
            """
            st.markdown(html_lucro, unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("🛠️ 2. Serviços")
        
        lista_servicos = st.session_state.db_servicos['Item'].dropna().tolist() if not st.session_state.db_servicos.empty else []
        
        servico_atual = st.selectbox("Selecionar Serviço da Base:", [""] + lista_servicos + ["Manual"])
        
        if servico_atual != st.session_state.servico_selecionado_anterior:
            st.session_state.servico_selecionado_anterior = servico_atual
            if servico_atual == "Manual":
                st.session_state.txt_servico = ""
                st.session_state.val_servico = 0.0
            elif servico_atual != "":
                linha_base = st.session_state.db_servicos.loc[st.session_state.db_servicos['Item']==servico_atual]
                descricao_base = str(linha_base['Descrição'].values[0]) if pd.notna(linha_base['Descrição'].values[0]) else ""
                st.session_state.txt_servico = f"{servico_atual}\n{descricao_base}".strip()
                st.session_state.val_servico = float(linha_base['Venda (R$)'].values[0]) if pd.notna(linha_base['Venda (R$)'].values[0]) else 0.0
            else:
                st.session_state.txt_servico = ""
                st.session_state.val_servico = 0.0

        descricao_final_servico = st.text_area("Descrição detalhada do Serviço:", key="txt_servico", height=100)
        valor_final_servico = st.number_input("Valor do Serviço (R$):", key="val_servico", format="%.2f")

    with st.container(border=True):
        st.subheader("🤝 3. Outros / Terceiros")

        lista_outros = st.session_state.db_outros['Item'].dropna().tolist() if not st.session_state.db_outros.empty else []
        
        outros_atual = st.selectbox("Adicionar Outros / Terceiros:", [""] + lista_outros + ["Manual"])
        
        if outros_atual != st.session_state.outros_selecionado_anterior:
            st.session_state.outros_selecionado_anterior = outros_atual
            if outros_atual == "Manual":
                st.session_state.txt_outros = ""
                st.session_state.val_outros = 0.0
            elif outros_atual != "":
                linha_base_o = st.session_state.db_outros.loc[st.session_state.db_outros['Item']==outros_atual]
                descricao_base_o = str(linha_base_o['Descrição'].values[0]) if pd.notna(linha_base_o['Descrição'].values[0]) else ""
                st.session_state.txt_outros = f"{outros_atual}\n{descricao_base_o}".strip()
                st.session_state.val_outros = float(linha_base_o['Venda (R$)'].values[0]) if pd.notna(linha_base_o['Venda (R$)'].values[0]) else 0.0
            else:
                st.session_state.txt_outros = ""
                st.session_state.val_outros = 0.0

        descricao_final_outros = st.text_area("Descrição de Diversos:", key="txt_outros", height=80)
        valor_final_outros = st.number_input("Valor Adicional (R$):", key="val_outros", format="%.2f")

    total_investimento = subtotal_equipamentos + valor_final_servico + valor_final_outros
    st.markdown(f"<h3 style='color:#004488;'>💰 INVESTIMENTO TOTAL: {utils.to_br_currency(total_investimento)}</h3>", unsafe_allow_html=True)
    
    if "input_obs_pdf" not in st.session_state: 
        st.session_state.input_obs_pdf = "Material Hidráulico não incluído na proposta"
    
    obs_pdf = st.text_area("Observações no PDF:", key="input_obs_pdf")

    def formatar_telefone(tel):
        numeros = ''.join(filter(str.isdigit, tel))
        if len(numeros) == 11: 
            return f"({numeros[:2]}) {numeros[2:7]}-{numeros[7:]}"
        return tel

    col_btn_previa, col_btn_rasc, col_btn_salvar = st.columns([1, 1.2, 1.2])
    
    with col_btn_previa:
        if st.button("👁️ GERAR PRÉVIA", use_container_width=True):
            if not nome_cliente: 
                st.warning("Preencha o nome do cliente!")
            else:
                tel_formatado = formatar_telefone(whatsapp)
                st.session_state['pdf_gerado'] = utils.gerar_pdf_orcamento(
                    nome_cliente, 
                    tel_formatado, 
                    modelo_capa, 
                    df_editavel, 
                    descricao_final_servico, 
                    valor_final_servico, 
                    descricao_final_outros, 
                    valor_final_outros, 
                    total_investimento, 
                    obs_pdf, 
                    mostrar_precos_unitarios
                )
                st.session_state['nome_cliente_previa'] = nome_cliente
        
        if 'pdf_gerado' in st.session_state and st.session_state.get('nome_cliente_previa') == nome_cliente:
            st.download_button(
                "📥 BAIXAR RASCUNHO", 
                data=st.session_state['pdf_gerado'], 
                file_name=f"ORCAMENTO_{nome_cliente}.pdf", 
                mime="application/pdf", 
                use_container_width=True
            )

    with col_btn_rasc:
        if st.button("💾 SALVAR RASCUNHO", use_container_width=True):
            if not nome_cliente:
                st.warning("Preencha ao menos o nome do cliente para salvar o rascunho!")
            else:
                tel_formatado = formatar_telefone(whatsapp)
                snapshot_itens = []
                for _, r in df_editavel.iterrows():
                    if r['Quantidade'] > 0 or str(r.get('Produto da Base', '')) != "" or str(r.get('Produto Manual', '')) != "":
                        p_base = str(r.get('Produto da Base', '')).strip()
                        p_man = str(r.get('Produto Manual', '')).strip()
                        nome_item = p_base if p_base not in ["", "OUTRO", "None"] else p_man
                        
                        snapshot_itens.append({
                            "Item": nome_item, 
                            "Qtd": r['Quantidade'], 
                            "Venda Un.": r['Venda (R$)'], 
                            "Descrição": r['Descrição']
                        })

                payload_rascunho = {
                    "nome_cliente": nome_cliente,
                    "telefone_cliente": tel_formatado,
                    "servicos_adquiridos": descricao_final_servico,
                    "valor_venda_total": total_investimento,
                    "status_projeto": "Rascunho",
                    "detalhamento_itens": snapshot_itens,
                    "data_conclusao": datetime.date.today().strftime('%Y-%m-%d'),
                    "dados_contrato": {
                        "val_servico": valor_final_servico,
                        "txt_outros": descricao_final_outros,
                        "val_outros": valor_final_outros,
                        "obs_pdf": obs_pdf
                    }
                }

                if st.session_state.get('rascunho_id'):
                    st.session_state.supabase.table("servicos_andamento").update(payload_rascunho).eq('id', st.session_state.rascunho_id).execute()
                    st.success("✅ Rascunho atualizado com sucesso!")
                else:
                    string_data = datetime.datetime.now().strftime('%y%m%d-%H%M')
                    payload_rascunho["numero_orcamento"] = f"RASC-{string_data}"
                    res = st.session_state.supabase.table("servicos_andamento").insert(payload_rascunho).execute()
                    st.session_state.rascunho_id = res.data[0]['id']
                    st.success("✅ Rascunho criado com sucesso!")

    with col_btn_salvar:
        if st.button("✅ SALVAR NO SISTEMA", type="primary", use_container_width=True):
            if not nome_cliente: 
                st.error("Preencha o nome do cliente!")
            else:
                string_data = datetime.datetime.now().strftime('%y%m%d-%H%M')
                numero_do_orcamento = f"ORC-{string_data}"
                try:
                    tel_formatado = formatar_telefone(whatsapp)
                    snapshot_itens = []
                    lista_prods_texto = []
                    
                    for _, r in df_editavel.iterrows():
                        if r['Quantidade'] > 0:
                            p_base = str(r.get('Produto da Base', '')).strip()
                            p_man = str(r.get('Produto Manual', '')).strip()
                            nome_item = p_base if p_base not in ["", "OUTRO", "None"] else p_man
                            
                            snapshot_itens.append({
                                "Item": nome_item, 
                                "Qtd": r['Quantidade'], 
                                "Venda Un.": r['Venda (R$)'], 
                                "Descrição": r['Descrição']
                            })
                            lista_prods_texto.append(f"{int(r['Quantidade'])}x {nome_item}")
                    
                    string_produtos = ", ".join(lista_prods_texto)
                    
                    payload_final = {
                        "numero_orcamento": numero_do_orcamento,
                        "nome_cliente": nome_cliente, 
                        "telefone_cliente": tel_formatado, 
                        "produtos_adquiridos": string_produtos,
                        "servicos_adquiridos": descricao_final_servico,
                        "valor_venda_total": total_investimento,
                        "status_projeto": "Orçamento Enviado",
                        "detalhamento_itens": snapshot_itens,
                        "data_conclusao": datetime.date.today().strftime('%Y-%m-%d'),
                        "dados_contrato": {}
                    }
                    
                    if st.session_state.get('rascunho_id'):
                        st.session_state.supabase.table("servicos_andamento").update(payload_final).eq('id', st.session_state.rascunho_id).execute()
                    else:
                        st.session_state.supabase.table("servicos_andamento").insert(payload_final).execute()
                    
                    st.success(f"✅ Orçamento {numero_do_orcamento} salvo com sucesso no banco de dados!")
                    limpar_func()
                    deve_rerun = True
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

    return deve_rerun
