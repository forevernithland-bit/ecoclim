import streamlit as st
import pandas as pd
import datetime
import utils
import zipfile
import io
import math

# =========================================================================
# FUNÇÃO DO POP-UP (MODAL) DE LEMBRETES
# =========================================================================
@st.dialog("💡 Calculadoras de Dimensionamento e Lembretes")
def abrir_lembretes():
    t_banho, t_tubo, t_col = st.tabs(["🚿 Banhos por Litro", "🧪 Tubos (Vácuo)", "☀️ Coletores (Planos)"])
    
    with t_banho:
        st.caption("Calcule quantos banhos o boiler suporta.")
        c1, c2 = st.columns(2)
        v_b = c1.number_input("Volume do Boiler (Litros)", min_value=0, step=10, key="calc_vol_banho")
        l_b = c2.number_input("Litros por Banho", min_value=1, value=45, step=1, key="calc_litro_banho")
        if v_b > 0:
            qtd_banhos = int(v_b / l_b)
            st.success(f"**Resultado:** {qtd_banhos} Banhos\n\n*(1 banho está configurado para {l_b} litros)*")
            
    with t_tubo:
        st.caption("Calcule a quantidade de tubos a vácuo necessários.")
        v_t = st.number_input("Volume do Boiler (Litros)", min_value=0, step=10, key="calc_vol_tubo")
        if v_t > 0:
            c1, c2 = st.columns(2)
            c1.info(f"**BOM (20L por tubo):**\n### {math.ceil(v_t / 20)} tubos")
            c2.success(f"**ÓTIMO (15L por tubo):**\n### {math.ceil(v_t / 15)} tubos")
            
    with t_col:
        st.caption("Calcule a quantidade de coletores (1 placa para cada 200L).")
        v_c = st.number_input("Volume do Boiler (Litros)", min_value=0, step=10, key="calc_vol_col")
        if v_c > 0:
            exato = v_c / 200
            arredondado = math.ceil(exato)
            if arredondado > exato:
                st.success(f"**Resultado:** ### {arredondado} coletores\n\n⚠️ *O sistema colocou 1 coletor a mais para o sistema ficar mais eficiente.*")
            else:
                st.success(f"**Resultado:** ### {arredondado} coletores\n\n✅ *Cálculo exato de 1 coletor para cada 200L.*")

def limpar_tela_orcamento():
    chaves = [
        # Orçamento Padrão
        'rascunho_id', 'input_nome_cliente', 'input_whatsapp', 
        'txt_servico', 'val_servico', 'txt_outros', 'val_outros', 
        'input_obs_pdf', 'df_orc', 'df_orc_prev', 'editor_orc_base', 
        'pdf_gerado', 'nome_cliente_previa', 'servico_selecionado_anterior', 
        'outros_selecionado_anterior',
        # Orçamento Rápido
        'rapido_rascunho_id', 'rapido_input_nome_cliente', 'rapido_df_orc', 'editor_rapido',
        'rapido_custo_servico', 'rapido_venda_servico', 'rapido_custo_outros', 'rapido_venda_outros',
        'rapido_nf', 'rapido_taxa_cartao', 'rapido_comissao'
    ]
    for k in chaves:
        if k in st.session_state: 
            del st.session_state[k]

# =========================================================================
# RENDERIZAÇÃO DA TELA
# =========================================================================
def renderizar():
    # -------------------------------------------------------------------------
    # BLINDAGEM DE ESTADO: Evita perda de dados em atualizações
    # -------------------------------------------------------------------------
    deve_rerun = False
    
    if "input_nome_cliente" not in st.session_state: st.session_state.input_nome_cliente = ""
    if "input_whatsapp" not in st.session_state: st.session_state.input_whatsapp = ""
    if "txt_servico" not in st.session_state: st.session_state.txt_servico = ""
    if "val_servico" not in st.session_state: st.session_state.val_servico = 0.0
    if "txt_outros" not in st.session_state: st.session_state.txt_outros = ""
    if "val_outros" not in st.session_state: st.session_state.val_outros = 0.0
    if "servico_selecionado_anterior" not in st.session_state: st.session_state.servico_selecionado_anterior = ""
    if "outros_selecionado_anterior" not in st.session_state: st.session_state.outros_selecionado_anterior = ""
    
    if "rapido_input_nome_cliente" not in st.session_state: st.session_state.rapido_input_nome_cliente = ""
    if "rapido_custo_servico" not in st.session_state: st.session_state.rapido_custo_servico = 0.0
    if "rapido_venda_servico" not in st.session_state: st.session_state.rapido_venda_servico = 0.0
    if "rapido_custo_outros" not in st.session_state: st.session_state.rapido_custo_outros = 0.0
    if "rapido_venda_outros" not in st.session_state: st.session_state.rapido_venda_outros = 0.0
    if "rapido_nf" not in st.session_state: st.session_state.rapido_nf = "Não"
    if "rapido_taxa_cartao" not in st.session_state: st.session_state.rapido_taxa_cartao = "Nenhum / Dinheiro / PIX"
    if "rapido_comissao" not in st.session_state: st.session_state.rapido_comissao = 0.0

    # =============================================================================
    # TÍTULO E BOTÕES LATERAIS DIREITOS
    # =============================================================================
    col_tit, col_btn = st.columns([2, 1])
    
    with col_tit:
        st.markdown("<h4 style='color:#004488; margin:0; font-weight:600;'>📝 Gestão de Orçamentos</h4>", unsafe_allow_html=True)
        
    with col_btn:
        if st.button("🔄 ATUALIZAR DADOS DO BANCO / LIMPAR", use_container_width=True):
            limpar_tela_orcamento()
            for chave in ['db_produtos', 'db_servicos', 'db_outros', 'db_taxas', 'pdf_gerados_lote']:
                if chave in st.session_state: 
                    del st.session_state[chave]
            st.rerun()
            
        # BOTÃO QUE CHAMA O POP-UP MODAL
        if st.button("💡 Lembretes e Cálculos Rápidos", use_container_width=True):
            abrir_lembretes()

    # Carrega bases de dados apenas se não estiverem no session_state
    if 'db_produtos' not in st.session_state: 
        st.session_state.db_produtos = utils.load_catalog('catalogo_produtos')
    if 'db_servicos' not in st.session_state: 
        st.session_state.db_servicos = utils.load_catalog('catalogo_servicos')
    if 'db_outros' not in st.session_state: 
        st.session_state.db_outros = utils.load_catalog('catalogo_outros')
    if 'db_taxas' not in st.session_state: 
        st.session_state.db_taxas = utils.load_taxas()

    cat_produtos = st.session_state.db_produtos
    lista_nomes_produtos = cat_produtos['Item'].dropna().tolist() if not cat_produtos.empty else []
    
    aba_personalizado, aba_lote, aba_rapido = st.tabs(["📝 Orçamento Personalizado", "📦 Gerador em Lote (Tabelas)", "⚡ Orçamento Rápido"])

    # =========================================================================
    # ABA 1: ORÇAMENTO PERSONALIZADO
    # =========================================================================
    with aba_personalizado:
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
                        limpar_tela_orcamento()
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
                                if p_nome:
                                    match_c = cat_produtos[cat_produtos['Item'].astype(str).str.strip() == p_nome]
                                    if not match_c.empty:
                                        c_un = float(match_c.get('Custo (R$)', pd.Series([0.0])).values[0])

                                novo_df.append({
                                    "Produto da Base": p_nome,
                                    "Produto Manual": "",
                                    "Descrição": it.get('Descrição', ''),
                                    "Quantidade": qtd,
                                    "Custo (R$)": c_un,
                                    "Venda (R$)": v_un,
                                    "Custo Total": qtd * c_un,
                                    "Venda Total": qtd * v_un
                                })
                                
                            while len(novo_df) < 5:
                                novo_df.append({
                                    "Produto da Base": "", 
                                    "Produto Manual": "", 
                                    "Descrição": "", 
                                    "Quantidade": 0, 
                                    "Custo (R$)": 0.0, 
                                    "Venda (R$)": 0.0, 
                                    "Custo Total": 0.0, 
                                    "Venda Total": 0.0
                                })
                            
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
            ], index=3)

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
                "Custo (R$)": st.column_config.NumberColumn("Custo Unt.", format="R$ %,.2f"),
                "Venda (R$)": st.column_config.NumberColumn("Venda Unt.", format="R$ %,.2f"),
                "Custo Total": st.column_config.NumberColumn("Custo Total", format="R$ %,.2f", disabled=True),
                "Venda Total": st.column_config.NumberColumn("Total", format="R$ %,.2f", disabled=True)
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

                if produto_atual != produto_anterior and produto_atual != "":
                    match_base = cat_produtos[cat_produtos['Item'].astype(str).str.strip() == produto_atual]
                    
                    if not match_base.empty:
                        val_venda = match_base['Venda (R$)'].values[0]
                        val_custo = match_base.get('Custo (R$)', pd.Series([0.0])).values[0]
                        desc_base = match_base['Descrição'].values[0]
                        
                        try: 
                            preco_novo = float(val_venda)
                        except Exception: 
                            preco_novo = 0.0
                            
                        try: 
                            custo_novo = float(val_custo)
                        except Exception: 
                            custo_novo = 0.0
                            
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

            st.session_state.df_orc = df_editavel
            st.session_state.df_orc_prev = df_editavel.copy()
            
            subtotal_equipamentos = df_editavel['Venda Total'].sum()
            st.markdown(f"**Subtotal Equipamentos:** :blue[{utils.to_br_currency(subtotal_equipamentos)}]")
            
            mostrar_lucro = st.toggle("Exibir Margem e Lucro Estimado", value=False)
            if mostrar_lucro:
                custo_total_equipamentos = df_editavel['Custo Total'].sum()
                lucro_equip = subtotal_equipamentos - custo_total_equipamentos
                
                margem_equip = (lucro_equip / custo_total_equipamentos * 100) if custo_total_equipamentos > 0 else (100.0 if lucro_equip > 0 else 0.0)
                
                html_lucro = f"""
                <div style='background-color: #e6ffe6; padding: 10px; border-radius: 5px; border: 1px solid #006600; margin-top: 10px; margin-bottom: 5px;'>
                    <span style='color: #006600; font-weight: bold; font-size: 16px;'>💸 Lucro Projetado: {utils.to_br_currency(lucro_equip)} ({margem_equip:.1f}%)</span><br>
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
                        if r['Quantidade'] > 0 or r['Produto da Base'] != "":
                            nome_item = r['Produto da Base'] or r['Produto Manual']
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
                                nome_item = r['Produto da Base'] or r['Produto Manual']
                                snapshot_itens.append({
                                    "Item": nome_item, 
                                    "Qtd": r['Quantidade'], 
                                    "Venda Un.": r['Venda (R$)'], 
                                    "Descrição": r['Descrição']
                                })
                                lista_prods_texto.append(f"{int(r['Quantidade'])}x {r['Produto da Base']}")
                        
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
                        limpar_tela_orcamento()
                        deve_rerun = True
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

    # =========================================================================
    # ABA 2: GERADOR EM LOTE
    # =========================================================================
    with aba_lote:
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

    # =========================================================================
    # ABA 3: ORÇAMENTO RÁPIDO
    # =========================================================================
    with aba_rapido:
        st.markdown("### ⚡ Calculadora de Custo e Venda Rápida")
        st.caption("Apenas para cálculo interno de margem. Salva como rascunho específico desta aba.")

        try:
            res_r = st.session_state.supabase.table('servicos_andamento').select('id, nome_cliente, valor_venda_total').eq('status_projeto', 'Rascunho Rápido').execute()
            rascunhos_rapidos = res_r.data
        except Exception: 
            rascunhos_rapidos = []

        if rascunhos_rapidos or st.session_state.get('rapido_rascunho_id'):
            with st.expander("📂 Meus Cálculos Salvos", expanded=True if st.session_state.get('rapido_rascunho_id') else False):
                if st.session_state.get('rapido_rascunho_id'):
                    st.success("✏️ Você está editando um cálculo rápido em andamento.")
                    if st.button("❌ Fechar e Iniciar Novo Cálculo", use_container_width=True):
                        limpar_tela_orcamento()
                        deve_rerun = True
                else:
                    c_sel, c_load, c_del = st.columns([3, 1, 1])
                    opcoes_rapidas = {f"{r['nome_cliente']} ({utils.to_br_currency(r['valor_venda_total'])})": r['id'] for r in rascunhos_rapidos}
                    sel_r = c_sel.selectbox("Escolha um cálculo:", list(opcoes_rapidas.keys()), key="sel_rapido", label_visibility="collapsed")
                    
                    if c_load.button("📥 Abrir", use_container_width=True):
                        id_r = opcoes_rapidas[sel_r]
                        data_r = st.session_state.supabase.table('servicos_andamento').select('*').eq('id', id_r).execute().data[0]
                        st.session_state.rapido_rascunho_id = data_r['id']
                        st.session_state.rapido_input_nome_cliente = data_r['nome_cliente']
                        
                        d_ct_r = data_r.get('dados_contrato', {})
                        st.session_state.rapido_custo_servico = float(d_ct_r.get('custo_servico', 0.0))
                        st.session_state.rapido_venda_servico = float(d_ct_r.get('venda_servico', 0.0))
                        st.session_state.rapido_custo_outros = float(d_ct_r.get('custo_outros', 0.0))
                        st.session_state.rapido_venda_outros = float(d_ct_r.get('venda_outros', 0.0))
                        st.session_state.rapido_nf = d_ct_r.get('nf', "Não")
                        st.session_state.rapido_taxa_cartao = d_ct_r.get('taxa_cartao', "Nenhum / Dinheiro / PIX")
                        st.session_state.rapido_comissao = float(d_ct_r.get('comissao', 0.0))

                        itens_r = data_r.get('detalhamento_itens', [])
                        df_rec = []
                        for it in itens_r:
                            df_rec.append({
                                "Produto da Base": it.get("Item", ""),
                                "Quantidade": float(it.get("Qtd", 0)),
                                "Custo (R$)": float(it.get("Custo Un.", 0)),
                                "Venda (R$)": float(it.get("Venda Un.", 0)),
                                "Custo Total": float(it.get("Qtd", 0)) * float(it.get("Custo Un.", 0)),
                                "Venda Total": float(it.get("Qtd", 0)) * float(it.get("Venda Un.", 0))
                            })
                        
                        while len(df_rec) < 5:
                            df_rec.append({"Produto da Base": "", "Quantidade": 0, "Custo (R$)": 0.0, "Venda (R$)": 0.0, "Custo Total": 0.0, "Venda Total": 0.0})
                            
                        st.session_state.rapido_df_orc = pd.DataFrame(df_rec)
                        if "editor_rapido" in st.session_state:
                            del st.session_state["editor_rapido"]
                        deve_rerun = True
                        
                    if c_del.button("🗑️ Apagar", use_container_width=True):
                        st.session_state.supabase.table('servicos_andamento').delete().eq('id', opcoes_rapidas[sel_r]).execute()
                        st.success("Cálculo apagado!")
                        deve_rerun = True

        # Dados Iniciais
        nome_rapido = st.text_input("Nome do Cliente (Identificação)", key="rapido_input_nome_cliente")

        # Equipamentos
        st.markdown("#### 📦 Equipamentos")
        if 'rapido_df_orc' not in st.session_state:
            st.session_state.rapido_df_orc = pd.DataFrame([{"Produto da Base": "", "Quantidade": 0, "Custo (R$)": 0.0, "Venda (R$)": 0.0, "Custo Total": 0.0, "Venda Total": 0.0} for _ in range(5)])
        
        cfg_grid = {
            "Produto da Base": st.column_config.SelectboxColumn("Produto", options=[""] + lista_nomes_produtos, width="large"),
            "Quantidade": st.column_config.NumberColumn("Qtd", min_value=0),
            "Custo (R$)": st.column_config.NumberColumn("Custo Unt.", format="R$ %.2f"),
            "Venda (R$)": st.column_config.NumberColumn("Venda Unt.", format="R$ %.2f"),
            "Custo Total": st.column_config.NumberColumn("Custo Total", format="R$ %.2f", disabled=True),
            "Venda Total": st.column_config.NumberColumn("Venda Total", format="R$ %.2f", disabled=True),
        }

        df_r_ed = st.data_editor(st.session_state.rapido_df_orc, column_config=cfg_grid, num_rows="dynamic", use_container_width=True, key="editor_rapido", hide_index=True)
        
        # Lógica de Auto-Preenchimento e Soma na grade Rápida
        refresh_rapido = False
        for i in range(len(df_r_ed)):
            p_atual = str(df_r_ed.at[i, "Produto da Base"]).strip()
            p_ant = str(st.session_state.rapido_df_orc.at[i, "Produto da Base"]).strip() if i < len(st.session_state.rapido_df_orc) else ""
            
            if p_atual != p_ant and p_atual != "":
                match = cat_produtos[cat_produtos['Item'].astype(str).str.strip() == p_atual]
                if not match.empty:
                    try: custo_n = float(match.get('Custo (R$)', pd.Series([0.0])).values[0])
                    except: custo_n = 0.0
                    try: venda_n = float(match['Venda (R$)'].values[0])
                    except: venda_n = 0.0
                    
                    df_r_ed.at[i, "Custo (R$)"] = custo_n
                    df_r_ed.at[i, "Venda (R$)"] = venda_n
                    if pd.isna(df_r_ed.at[i, "Quantidade"]) or float(df_r_ed.at[i, "Quantidade"]) <= 0:
                        df_r_ed.at[i, "Quantidade"] = 1
                    refresh_rapido = True
            
            qtd = float(df_r_ed.at[i, "Quantidade"]) if pd.notna(df_r_ed.at[i, "Quantidade"]) else 0.0
            c_un = float(df_r_ed.at[i, "Custo (R$)"]) if pd.notna(df_r_ed.at[i, "Custo (R$)"]) else 0.0
            v_un = float(df_r_ed.at[i, "Venda (R$)"]) if pd.notna(df_r_ed.at[i, "Venda (R$)"]) else 0.0
            
            tot_c_calc = qtd * c_un
            tot_v_calc = qtd * v_un
            
            if abs(tot_c_calc - float(df_r_ed.at[i, "Custo Total"])) > 0.01 or abs(tot_v_calc - float(df_r_ed.at[i, "Venda Total"])) > 0.01:
                df_r_ed.at[i, "Custo Total"] = tot_c_calc
                df_r_ed.at[i, "Venda Total"] = tot_v_calc
                refresh_rapido = True

        if refresh_rapido:
            st.session_state.rapido_df_orc = df_r_ed
            if "editor_rapido" in st.session_state: del st.session_state["editor_rapido"]
            deve_rerun = True
            
        st.session_state.rapido_df_orc = df_r_ed

        # --- NOVO: TOTAIS DE EQUIPAMENTOS ---
        custo_total_produtos = pd.to_numeric(df_r_ed["Custo Total"], errors='coerce').fillna(0).sum()
        venda_total_produtos = pd.to_numeric(df_r_ed["Venda Total"], errors='coerce').fillna(0).sum()
        lucro_total_produtos = venda_total_produtos - custo_total_produtos
        
        st.markdown(f"""
            <div style='display: flex; justify-content: flex-end; gap: 25px; margin-top: -10px; margin-bottom: 25px;'>
                <span style='color: #cc0000; font-size: 15px;'><b>Custo Total Produtos:</b> {utils.to_br_currency(custo_total_produtos)}</span>
                <span style='color: #004488; font-size: 15px;'><b>Venda Total Produtos:</b> {utils.to_br_currency(venda_total_produtos)}</span>
                <span style='color: #006600; font-size: 15px;'><b>Lucro Total Produtos:</b> {utils.to_br_currency(lucro_total_produtos)}</span>
            </div>
        """, unsafe_allow_html=True)
        # ------------------------------------

        # Serviços e Outros
        st.markdown("#### 🛠️ Mão de Obra e Outros")
        
        c_s1, c_s2 = st.columns(2)
        c_serv = c_s1.number_input("Custo de Serviço (R$)", min_value=0.0, format="%.2f", key="rapido_custo_servico")
        v_serv = c_s2.number_input("Preço de Venda Serviço (R$)", min_value=0.0, format="%.2f", key="rapido_venda_servico")
        
        c_o1, c_o2 = st.columns(2)
        c_outros = c_o1.number_input("Custo de Outros/Terceiros (R$)", min_value=0.0, format="%.2f", key="rapido_custo_outros")
        v_outros = c_o2.number_input("Preço de Venda Outros (R$)", min_value=0.0, format="%.2f", key="rapido_venda_outros")

        # Taxas e Impostos
        st.markdown("#### 🧮 Impostos e Taxas")
        with st.container(border=True):
            col_t1, col_t2, col_t3 = st.columns(3)
            
            venda_bruta = df_r_ed["Venda Total"].sum() + v_serv + v_outros
            
            # Nota Fiscal
            emite_nf = col_t1.radio("Nota Fiscal?", ["Não", "Sim"], horizontal=True, key="rapido_nf")
            taxa_nf_val = 6.0
            if not st.session_state.db_taxas.empty:
                for _, t_row in st.session_state.db_taxas.iterrows():
                    if "NF" in str(t_row.get('Item', '')).upper() or "NOTA FISCAL" in str(t_row.get('Item', '')).upper():
                        try: taxa_nf_val = float(t_row.get('Taxa (%)', 6.0))
                        except: pass
            
            custo_nf = venda_bruta * (taxa_nf_val/100) if emite_nf == "Sim" else 0.0
            col_t1.caption(f"Custo NF ({taxa_nf_val}%): - {utils.to_br_currency(custo_nf)}")

            # Cartão
            opcoes_cartao = ["Nenhum / Dinheiro / PIX"]
            dict_taxas = {"Nenhum / Dinheiro / PIX": 0.0}
            if not st.session_state.db_taxas.empty:
                for _, t_row in st.session_state.db_taxas.iterrows():
                    item_nome = str(t_row.get('Item', '')).strip()
                    try: taxa_val = float(t_row.get('Taxa (%)', 0.0))
                    except: taxa_val = 0.0
                    if "NF" not in item_nome.upper() and "NOTA FISCAL" not in item_nome.upper() and item_nome != "":
                        opcoes_cartao.append(item_nome)
                        dict_taxas[item_nome] = taxa_val
            
            sel_cartao = col_t2.selectbox("Parcelamento Cartão", opcoes_cartao, key="rapido_taxa_cartao")
            taxa_c_pct = dict_taxas[sel_cartao]
            custo_cartao = venda_bruta * (taxa_c_pct / 100)
            col_t2.caption(f"Taxa Cartão ({taxa_c_pct}%): - {utils.to_br_currency(custo_cartao)}")

            # Comissão
            comissao_pct = col_t3.number_input("Comissão (%)", min_value=0.0, format="%.1f", key="rapido_comissao")
            custo_comissao = venda_bruta * (comissao_pct / 100)
            col_t3.caption(f"Valor Comissão: - {utils.to_br_currency(custo_comissao)}")

        # Totais e Lucro
        custo_equip = df_r_ed["Custo Total"].sum()
        custo_fixo = custo_equip + c_serv + c_outros
        custo_variavel = custo_nf + custo_cartao + custo_comissao
        custo_total_geral = custo_fixo + custo_variavel
        
        lucro_est = venda_bruta - custo_total_geral
        margem_pct = (lucro_est / venda_bruta * 100) if venda_bruta > 0 else 0.0

        st.markdown("<br>", unsafe_allow_html=True)
        res1, res2, res3 = st.columns(3)
        res1.metric("Custo Total Acumulado", utils.to_br_currency(custo_total_geral))
        res2.metric("Preço de Venda Final", utils.to_br_currency(venda_bruta))
        res3.metric("LUCRO LÍQUIDO", utils.to_br_currency(lucro_est), delta=f"{margem_pct:.1f}% Margem Real")

        # Salvar Rascunho
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 SALVAR CÁLCULO RÁPIDO", type="primary", use_container_width=True):
            if not nome_rapido:
                st.error("⚠️ Preencha o Nome do Cliente (Identificação) para poder salvar.")
            else:
                snapshot = []
                for _, r in df_r_ed.iterrows():
                    if r["Quantidade"] > 0 or r["Produto da Base"] != "":
                        snapshot.append({
                            "Item": r["Produto da Base"], 
                            "Qtd": r["Quantidade"], 
                            "Venda Un.": r["Venda (R$)"], 
                            "Custo Un.": r["Custo (R$)"]
                        })
                
                payload = {
                    "nome_cliente": nome_rapido,
                    "valor_venda_total": venda_bruta,
                    "lucro_estimado": lucro_est,
                    "status_projeto": "Rascunho Rápido",
                    "detalhamento_itens": snapshot,
                    "data_conclusao": datetime.date.today().strftime('%Y-%m-%d'),
                    "dados_contrato": {
                        "custo_servico": c_serv, 
                        "venda_servico": v_serv,
                        "custo_outros": c_outros, 
                        "venda_outros": v_outros,
                        "nf": emite_nf, 
                        "taxa_cartao": sel_cartao, 
                        "comissao": comissao_pct
                    }
                }
                
                if st.session_state.get('rapido_rascunho_id'):
                    st.session_state.supabase.table('servicos_andamento').update(payload).eq('id', st.session_state.rapido_rascunho_id).execute()
                else:
                    res = st.session_state.supabase.table('servicos_andamento').insert(payload).execute()
                    st.session_state.rapido_rascunho_id = res.data[0]['id']
                
                st.success("✅ Cálculo salvo com sucesso! Você pode continuar editando ou criar um novo.")
                deve_rerun = True

    # -------------------------------------------------------------------------
    # GATILHO DE RERUN SEGURO (Executado apenas após toda a tela ser renderizada)
    # -------------------------------------------------------------------------
    if deve_rerun:
        st.rerun()
