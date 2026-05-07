import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar():
    st.markdown("## 📝 Novo Orçamento")
    
    # Botão para forçar atualização do banco
    if st.button("🔄 ATUALIZAR DADOS DO BANCO"):
        for chave in ['db_produtos', 'db_servicos', 'db_outros', 'df_orc', 'df_orc_prev']:
            if chave in st.session_state: del st.session_state[chave]
        st.rerun()

    # Carregamento seguro dos catálogos
    if 'db_produtos' not in st.session_state: st.session_state.db_produtos = utils.load_catalog('catalogo_produtos')
    if 'db_servicos' not in st.session_state: st.session_state.db_servicos = utils.load_catalog('catalogo_servicos')
    if 'db_outros' not in st.session_state: st.session_state.db_outros = utils.load_catalog('catalogo_outros')

    cat_produtos = st.session_state.db_produtos
    lista_nomes_produtos = cat_produtos['Item'].tolist() if not cat_produtos.empty else []
    
    with st.container(border=True):
        st.subheader("👤 Dados do Cliente")
        col1, col2 = st.columns(2)
        nome_cliente = col1.text_input("Nome do Cliente", key="input_nome_cliente")
        whatsapp = col2.text_input("WhatsApp", placeholder="(31) 99715-1596", key="input_whatsapp")
        modelo_capa = st.selectbox("Modelo para Capa", [
            "AQUECEDOR SOLAR TRADICIONAL", 
            "AQUECEDOR SOLAR A VÁCUO ACOPLADO", 
            "AQUECEDOR SOLAR MODULAR", 
            "AQUECEDOR DE PISCINA - TRADICIONAL", 
            "AQUECEDOR DE PISCINA - TROCADOR DE CALOR", 
            "SISTEMAS DE PRESSURIZAÇÃO"
        ], index=1)

    with st.container(border=True):
        st.subheader("⚙️ 1. Equipamentos")
        mostrar_precos_unitarios = st.checkbox("Mostrar Preços Unitários no PDF?", value=False)
        
        # Inicialização protegida da tabela de orçamento
        if 'df_orc' not in st.session_state:
            st.session_state.df_orc = pd.DataFrame([{"Produto da Base": "", "Produto Manual": "", "Descrição": "", "Quantidade": 0, "Venda (R$)": 0.0, "Venda Total": 0.0} for _ in range(5)])
        
        # Garantia contra AttributeError: a tabela espelho sempre deve existir
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
        
        df_editavel = st.data_editor(st.session_state.df_orc, column_config=configuracao_colunas, num_rows="dynamic", use_container_width=True)
        df_editavel = df_editavel.reset_index(drop=True)
        
        precisa_atualizar_tela = False
        for i in range(len(df_editavel)):
            produto_atual = df_editavel.at[i, 'Produto da Base']
            produto_anterior = st.session_state.df_orc_prev.at[i, 'Produto da Base'] if i < len(st.session_state.df_orc_prev) else ""
            
            # Se o usuário trocou o produto na linha, busca dados da base
            if produto_atual != produto_anterior and produto_atual in lista_nomes_produtos:
                match_base = cat_produtos[cat_produtos['Item'] == produto_atual]
                if not match_base.empty:
                    # Puxa o preço de VENDA da base (conforme o print do Supabase)
                    df_editavel.at[i, 'Venda (R$)'] = float(match_base['Venda (R$)'].values[0])
                    df_editavel.at[i, 'Descrição'] = str(match_base['Descrição'].values[0]) if str(match_base['Descrição'].values[0]) != 'nan' else ""
                    if df_editavel.at[i, 'Quantidade'] == 0: 
                        df_editavel.at[i, 'Quantidade'] = 1
                    precisa_atualizar_tela = True
                
        df_editavel['Venda Total'] = df_editavel['Venda (R$)'] * df_editavel['Quantidade']
        
        if precisa_atualizar_tela:
            st.session_state.df_orc = df_editavel
            st.session_state.df_orc_prev = df_editavel.copy()
            st.rerun()
            
        st.session_state.df_orc = df_editavel
        st.session_state.df_orc_prev = df_editavel.copy()
        
        subtotal_equipamentos = df_editavel['Venda Total'].sum()
        st.markdown(f"**Subtotal Equipamentos:** :blue[{utils.to_br_currency(subtotal_equipamentos)}]")

    with st.container(border=True):
        st.subheader("🛠️ 2. Serviços / Diversos")
        
        lista_servicos = st.session_state.db_servicos['Item'].tolist() if not st.session_state.db_servicos.empty else []
        if 'servico_selecionado_anterior' not in st.session_state: st.session_state.servico_selecionado_anterior = ""
        
        servico_atual = st.selectbox("Selecionar Serviço da Base:", [""] + lista_servicos + ["Manual"])
        
        if servico_atual != st.session_state.servico_selecionado_anterior:
            st.session_state.servico_selecionado_anterior = servico_atual
            if servico_atual == "Manual":
                st.session_state.txt_servico, st.session_state.val_servico = "", 0.0
            elif servico_atual != "":
                linha_base = st.session_state.db_servicos.loc[st.session_state.db_servicos['Item']==servico_atual]
                descricao_base = str(linha_base['Descrição'].values[0]) if str(linha_base['Descrição'].values[0]) != 'nan' else ""
                st.session_state.txt_servico = f"{servico_atual}\n{descricao_base}".strip()
                st.session_state.val_servico = float(linha_base['Venda (R$)'].values[0])
            else:
                st.session_state.txt_servico, st.session_state.val_servico = "", 0.0

        descricao_final_servico = st.text_area("Descrição detalhada do Serviço:", value=st.session_state.get('txt_servico', ""), height=100)
        valor_final_servico = st.number_input("Valor do Serviço (R$):", value=float(st.session_state.get('val_servico', 0.0)), format="%.2f")

        st.markdown("---")

        lista_outros = st.session_state.db_outros['Item'].tolist() if not st.session_state.db_outros.empty else []
        if 'outros_selecionado_anterior' not in st.session_state: st.session_state.outros_selecionado_anterior = ""
        
        outros_atual = st.selectbox("Adicionar Outros / Terceiros:", [""] + lista_outros + ["Manual"])
        
        if outros_atual != st.session_state.outros_selecionado_anterior:
            st.session_state.outros_selecionado_anterior = outros_atual
            if outros_atual == "Manual":
                st.session_state.txt_outros, st.session_state.val_outros = "", 0.0
            elif outros_atual != "":
                linha_base_o = st.session_state.db_outros.loc[st.session_state.db_outros['Item']==outros_atual]
                descricao_base_o = str(linha_base_o['Descrição'].values[0]) if str(linha_base_o['Descrição'].values[0]) != 'nan' else ""
                st.session_state.txt_outros = f"{outros_atual}\n{descricao_base_o}".strip()
                st.session_state.val_outros = float(linha_base_o['Venda (R$)'].values[0])
            else:
                st.session_state.txt_outros, st.session_state.val_outros = "", 0.0

        descricao_final_outros = st.text_area("Descrição de Diversos:", value=st.session_state.get('txt_outros', ""), height=80)
        valor_final_outros = st.number_input("Valor Adicional (R$):", value=float(st.session_state.get('val_outros', 0.0)), format="%.2f")

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
                    
                    st.success(f"✅ Orçamento {numero_do_orcamento} salvo com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
