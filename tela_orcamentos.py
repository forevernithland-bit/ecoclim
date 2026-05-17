import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar():
    # =============================================================================
    # TÍTULO REDUZIDO E BOTÃO ALINHADOS LADO A LADO
    # =============================================================================
    col_tit, col_btn = st.columns([2, 1])
    
    with col_tit:
        st.markdown("<h4 style='color:#004488; margin:0; font-weight:600;'>📝 Novo Orçamento</h4>", unsafe_allow_html=True)
        
    with col_btn:
        if st.button("🔄 ATUALIZAR DADOS DO BANCO", use_container_width=True):
            for chave in ['db_produtos', 'db_servicos', 'db_outros', 'df_orc', 'df_orc_prev', 'editor_orc_base']:
                if chave in st.session_state: 
                    del st.session_state[chave]
            st.rerun()

    # Carregamento seguro dos catálogos
    if 'db_produtos' not in st.session_state: st.session_state.db_produtos = utils.load_catalog('catalogo_produtos')
    if 'db_servicos' not in st.session_state: st.session_state.db_servicos = utils.load_catalog('catalogo_servicos')
    if 'db_outros' not in st.session_state: st.session_state.db_outros = utils.load_catalog('catalogo_outros')

    cat_produtos = st.session_state.db_produtos
    lista_nomes_produtos = cat_produtos['Item'].dropna().tolist() if not cat_produtos.empty else []
    
    with st.container(border=True):
        st.subheader("👤 Dados do Cliente")
        col1, col2 = st.columns(2)
        nome_cliente = col1.text_input("Nome do Cliente", key="input_nome_cliente")
        whatsapp = col2.text_input("WhatsApp", placeholder="(31) 99715-1596", key="input_whatsapp")
        
        # OPÇÕES DE IMAGENS MAPEADAS CORRETAMENTE
        modelo_capa = st.selectbox("Modelo para Capa", [
            "Aquecedor Solar Tradicional", 
            "Aquecedor Solar a Vácuo Acoplado", 
            "Aquecedor Solar Modular", 
            "Aquecedor de Piscina - Tradicional", 
            "Aquecedor de Piscina - Trocador de Calor", 
            "Sistema de Pressurização"
        ], index=3)

    with st.container(border=True):
        st.subheader("⚙️ 1. Equipamentos")
        mostrar_precos_unitarios = st.checkbox("Mostrar Preços Unitários no PDF?", value=False)
        
        # Inicialização protegida da tabela de orçamento
        if 'df_orc' not in st.session_state:
            st.session_state.df_orc = pd.DataFrame([{"Produto da Base": "", "Produto Manual": "", "Descrição": "", "Quantidade": 0, "Venda (R$)": 0.0, "Venda Total": 0.0} for _ in range(5)])
        
        if 'df_orc_prev' not in st.session_state:
            st.session_state.df_orc_prev = st.session_state.df_orc.copy()
        
        configuracao_colunas = {
            "Produto da Base": st.column_config.SelectboxColumn("Produto", options=[""] + lista_nomes_produtos + ["OUTRO"], width="medium"), 
            "Produto Manual": st.column_config.TextColumn("Nome Manual", width="medium"),
            "Descrição": st.column_config.TextColumn("Detalhes / Garantia", width="large"),
            "Quantidade": st.column_config.NumberColumn("Qtd", min_value=0, step=1),
            "Venda (R$)": st.column_config.NumberColumn("Preço Venda", format="R$ %,.2f"),
            "Venda Total": st.column_config.NumberColumn("Total", format="R$ %,.2f", disabled=True)
        }
        
        df_editavel = st.data_editor(st.session_state.df_orc, column_config=configuracao_colunas, num_rows="dynamic", use_container_width=True, key="editor_orc_base")
        df_editavel = df_editavel.reset_index(drop=True)
        
        precisa_atualizar_tela = False
        
        for i in range(len(df_editavel)):
            # 1. Tratamento seguro de nomes
            produto_atual = str(df_editavel.at[i, 'Produto da Base']).strip()
            if produto_atual.lower() in ['nan', 'none', '']: produto_atual = ""
            
            produto_anterior = ""
            if i < len(st.session_state.df_orc_prev):
                produto_anterior = str(st.session_state.df_orc_prev.at[i, 'Produto da Base']).strip()
                if produto_anterior.lower() in ['nan', 'none', '']: produto_anterior = ""

            df_editavel.at[i, 'Produto da Base'] = produto_atual

            # 2. Se o usuário escolheu um produto novo da lista
            if produto_atual != produto_anterior and produto_atual != "":
                match_base = cat_produtos[cat_produtos['Item'].astype(str).str.strip() == produto_atual]
                
                if not match_base.empty:
                    val_venda = match_base['Venda (R$)'].values[0]
                    desc_base = match_base['Descrição'].values[0]
                    
                    try:
                        preco_novo = float(val_venda)
                    except:
                        preco_novo = 0.0
                        
                    df_editavel.at[i, 'Venda (R$)'] = preco_novo
                    df_editavel.at[i, 'Descrição'] = str(desc_base) if pd.notna(desc_base) and str(desc_base).lower() != 'nan' else ""
                    
                    if pd.isna(df_editavel.at[i, 'Quantidade']) or float(df_editavel.at[i, 'Quantidade']) <= 0:
                        df_editavel.at[i, 'Quantidade'] = 1
                        
                    precisa_atualizar_tela = True

            # 3. Matemática Segura
            qtd = float(df_editavel.at[i, 'Quantidade']) if pd.notna(df_editavel.at[i, 'Quantidade']) else 0.0
            preco = float(df_editavel.at[i, 'Venda (R$)']) if pd.notna(df_editavel.at[i, 'Venda (R$)']) else 0.0
            total_calc = qtd * preco
            total_tela = float(df_editavel.at[i, 'Venda Total']) if pd.notna(df_editavel.at[i, 'Venda Total']) else 0.0
            
            if abs(total_calc - total_tela) > 0.01:
                df_editavel.at[i, 'Venda Total'] = total_calc
                precisa_atualizar_tela = True

        if precisa_atualizar_tela:
            st.session_state.df_orc = df_editavel
            st.session_state.df_orc_prev = df_editavel.copy()
            if "editor_orc_base" in st.session_state:
                del st.session_state["editor_orc_base"]
            st.rerun()

        st.session_state.df_orc = df_editavel
        st.session_state.df_orc_prev = df_editavel.copy()
        
        subtotal_equipamentos = df_editavel['Venda Total'].sum()
        st.markdown(f"**Subtotal Equipamentos:** :blue[{utils.to_br_currency(subtotal_equipamentos)}]")

    # ------------------ DIVISÃO 2 (Serviços) ------------------
    with st.container(border=True):
        st.subheader("🛠️ 2. Serviços")
        
        lista_servicos = st.session_state.db_servicos['Item'].dropna().tolist() if not st.session_state.db_servicos.empty else []
        if 'servico_selecionado_anterior' not in st.session_state: st.session_state.servico_selecionado_anterior = ""
        
        servico_atual = st.selectbox("Selecionar Serviço da Base:", [""] + lista_servicos + ["Manual"])
        
        if servico_atual != st.session_state.servico_selecionado_anterior:
            st.session_state.servico_selecionado_anterior = servico_atual
            if servico_atual == "Manual":
                st.session_state.txt_servico, st.session_state.val_servico = "", 0.0
            elif servico_atual != "":
                linha_base = st.session_state.db_servicos.loc[st.session_state.db_servicos['Item']==servico_atual]
                descricao_base = str(linha_base['Descrição'].values[0]) if pd.notna(linha_base['Descrição'].values[0]) else ""
                st.session_state.txt_servico = f"{servico_atual}\n{descricao_base}".strip()
                st.session_state.val_servico = float(linha_base['Venda (R$)'].values[0]) if pd.notna(linha_base['Venda (R$)'].values[0]) else 0.0
            else:
                st.session_state.txt_servico, st.session_state.val_servico = "", 0.0

        descricao_final_servico = st.text_area("Descrição detalhada do Serviço:", value=st.session_state.get('txt_servico', ""), height=100)
        valor_final_servico = st.number_input("Valor do Serviço (R$):", value=float(st.session_state.get('val_servico', 0.0)), format="%.2f")

    # ------------------ DIVISÃO 3 (Outros/Terceiros) ------------------
    with st.container(border=True):
        st.subheader("🤝 3. Outros / Terceiros")

        lista_outros = st.session_state.db_outros['Item'].dropna().tolist() if not st.session_state.db_outros.empty else []
        if 'outros_selecionado_anterior' not in st.session_state: st.session_state.outros_selecionado_anterior = ""
        
        outros_atual = st.selectbox("Adicionar Outros / Terceiros:", [""] + lista_outros + ["Manual"])
        
        if outros_atual != st.session_state.outros_selecionado_anterior:
            st.session_state.outros_selecionado_anterior = outros_atual
            if outros_atual == "Manual":
                st.session_state.txt_outros, st.session_state.val_outros = "", 0.0
            elif outros_atual != "":
                linha_base_o = st.session_state.db_outros.loc[st.session_state.db_outros['Item']==outros_atual]
                descricao_base_o = str(linha_base_o['Descrição'].values[0]) if pd.notna(linha_base_o['Descrição'].values[0]) else ""
                st.session_state.txt_outros = f"{outros_atual}\n{descricao_base_o}".strip()
                st.session_state.val_outros = float(linha_base_o['Venda (R$)'].values[0]) if pd.notna(linha_base_o['Venda (R$)'].values[0]) else 0.0
            else:
                st.session_state.txt_outros, st.session_state.val_outros = "", 0.0

        descricao_final_outros = st.text_area("Descrição de Diversos:", value=st.session_state.get('txt_outros', ""), height=80)
        valor_final_outros = st.number_input("Valor Adicional (R$):", value=float(st.session_state.get('val_outros', 0.0)), format="%.2f")

    # ------------------ FECHAMENTO ------------------
    total_investimento = subtotal_equipamentos + valor_final_servico + valor_final_outros
    st.markdown(f"<h3 style='color:#004488;'>💰 INVESTIMENTO TOTAL: {utils.to_br_currency(total_investimento)}</h3>", unsafe_allow_html=True)
    obs_pdf = st.text_area("Observações no PDF:", value="Material Hidráulico não incluído na proposta")

    def formatar_telefone(tel):
        numeros = ''.join(filter(str.isdigit, tel))
        if len(numeros) == 11: return f"({numeros[:2]}) {numeros[2:7]}-{numeros[7:]}"
        return tel

    col_btn_previa, col_btn_salvar = st.columns(2)
    
    with col_btn_previa:
        if st.button("GERAR PRÉVIA DO PDF", use_container_width=True):
            if not nome_cliente: st.warning("Preencha o nome do cliente!")
            else:
                tel_formatado = formatar_telefone(whatsapp)
                st.session_state['pdf_gerado'] = utils.gerar_pdf_orcamento(nome_cliente, tel_formatado, modelo_capa, df_editavel, descricao_final_servico, valor_final_servico, descricao_final_outros, valor_final_outros, total_investimento, obs_pdf, mostrar_precos_unitarios)
                st.session_state['nome_cliente_previa'] = nome_cliente
        
        if 'pdf_gerado' in st.session_state and st.session_state.get('nome_cliente_previa') == nome_cliente:
            st.download_button("📥 BAIXAR RASCUNHO", data=st.session_state['pdf_gerado'], file_name=f"ORCAMENTO_{nome_cliente}.pdf", mime="application/pdf", use_container_width=True)
            
            # --- NOVO BLOCO: SALVAR NO DRIVE USANDO ST.CONTAINER NATIVO ---
            with st.container(border=True):
                st.markdown("☁️ **Salvar no Drive (Pasta: Orçamentos)**")
                
                hoje_str = datetime.datetime.now().strftime("%Y_%m_%d")
                partes_nome = nome_cliente.strip().split()
                if len(partes_nome) >= 2:
                    nome_formatado = f"{partes_nome[0]}_{partes_nome[-1]}".lower()
                else:
                    nome_formatado = partes_nome[0].lower() if partes_nome else "cliente"
                
                nome_sugerido = f"orcamento_{hoje_str}_{nome_formatado}.pdf"
                
                nome_arquivo_drive = st.text_input("Nome do arquivo:", value=nome_sugerido, key="input_nome_drive")
                
                if st.button("🚀 Enviar para o Drive", use_container_width=True):
                    with st.spinner("Salvando na pasta Orçamentos..."):
                        sucesso, msg = utils.upload_to_drive(
                            file_buffer=st.session_state['pdf_gerado'], 
                            filename=nome_arquivo_drive, 
                            mimetype="application/pdf", 
                            folder_path=["Orçamentos"]
                        )
                        if sucesso:
                            st.success(f"✅ Arquivo {nome_arquivo_drive} saved com sucesso no Drive!")
                        else:
                            st.error(f"Erro ao salvar: {msg}")

    with col_btn_salvar:
        if st.button("SALVAR ORÇAMENTO NO SISTEMA", type="primary", use_container_width=True):
            if not nome_cliente: st.error("Preencha o nome do cliente!")
            else:
                numero_do_orcamento = f"ORC-{datetime.datetime.now().strftime('%y%m%d-%H%M')}"
                try:
                    tel_formatado = formatar_telefone(whatsapp)
                    snapshot_itens = []
                    for _, r in df_editavel.iterrows():
                        if r['Quantidade'] > 0:
                            snapshot_itens.append({"Item": r['Produto da Base'] or r['Produto Manual'], "Qtd": r['Quantidade'], "Venda Un.": r['Venda (R$)'], "Descrição": r['Descrição']})
                    
                    st.session_state.supabase.table("servicos_andamento").insert({
                        "numero_orcamento": numero_do_orcamento,
                        "nome_cliente": nome_cliente, 
                        "telefone_cliente": tel_formatado, 
                        "produtos_adquiridos": ", ".join([f"{int(r['Quantidade'])}x {r['Produto da Base']}" for _, r in df_editavel.iterrows() if r['Quantidade']>0]),
                        "servicos_adquiridos": descricao_final_servico,
                        "valor_venda_total": total_investimento,
                        "status_projeto": "Orçamento Enviado",
                        "detalhamento_itens": snapshot_itens
                    }).execute()
                    
                    st.success(f"✅ Orçamento {numero_do_orcamento} salvo com sucesso no banco de dados!")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
