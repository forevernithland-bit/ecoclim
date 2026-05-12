import streamlit as st
import pandas as pd
import datetime
import utils

# Escudo contra erros de valores nulos do banco de dados
def safe_float(val):
    try:
        if pd.isna(val) or val is None or str(val).strip() == '': 
            return 0.0
        return float(val)
    except:
        return 0.0

# Regra: Só vai para a aba Finalizados se o status for Concluído E o mês já tiver virado
def deve_ir_para_finalizados(status, data_conc_str):
    if status not in ["Concluído PIX", "Concluído CARTÃO"]:
        return False
    try:
        data_conc = pd.to_datetime(data_conc_str).date()
        hoje = datetime.date.today()
        # Verifica se o mês/ano atual é maior que o mês/ano da conclusão
        if hoje.year > data_conc.year or (hoje.year == data_conc.year and hoje.month > data_conc.month):
            return True
        return False
    except:
        return False

def exibir_painel_detalhado(projeto_selecionado, supabase, df_taxas_config, df_produtos, prefix_key):
    st.markdown("---")
    st.markdown(f"### ⚙️ Detalhes e Fechamento: **{projeto_selecionado.get('nome_cliente', 'Sem Nome')}**")
    
    col_esq, col_dir = st.columns(2)
    
    # --- STATUS ---
    status_atual = projeto_selecionado.get('status_projeto', 'Orçamento Enviado')
    
    # Compatibilidade com status antigos para não quebrar o que já existe no banco
    if status_atual == "Cancelado": status_atual = "Orçamento Cancelado"
    if status_atual == "Aguardando Peças": status_atual = "Aguardando Pagamento"

    todas_opcoes = [
        "Orçamento Enviado", 
        "Orçamento Cancelado", 
        "Em Andamento", 
        "Aguardando Pagamento", 
        "Concluído PIX", 
        "Concluído CARTÃO", 
        "Excluir"
    ]
    
    novo_status = col_esq.selectbox("Alterar Status", todas_opcoes, index=todas_opcoes.index(status_atual) if status_atual in todas_opcoes else 0, key=f"status_{prefix_key}")
    
    # --- DATA (Blindada) ---
    data_banco = projeto_selecionado.get('data_conclusao')
    data_inicial = datetime.date.today()
    if pd.notna(data_banco) and str(data_banco).lower() not in ['none', 'nan', 'nat', '']:
        try: data_inicial = pd.to_datetime(data_banco).date()
        except: pass
    nova_data = col_dir.date_input("Previsão / Data de Conclusão", value=data_inicial, key=f"data_{prefix_key}")

    # --- 1. PRODUTOS DO ORÇAMENTO ---
    st.markdown("#### 🛒 Itens Vendidos (Ajuste Quantidades e Custos)")
    itens_json = projeto_selecionado.get('detalhamento_itens', [])
    df_itens = pd.DataFrame(itens_json) if (isinstance(itens_json, list) and len(itens_json) > 0) else pd.DataFrame(columns=['Item', 'Qtd', 'Custo Un.', 'Venda Un.'])
    
    for col in ['Item', 'Qtd', 'Custo Un.', 'Venda Un.']:
        if col not in df_itens.columns: df_itens[col] = 0.0 if 'Un.' in col or 'Qtd' in col else ""

    # Busca automática de custo se estiver zerado
    if not df_produtos.empty:
        for idx, row in df_itens.iterrows():
            if safe_float(row.get('Custo Un.')) == 0.0:
                nome_procurado = str(row.get('Item', '')).strip().upper()
                for _, prod_row in df_produtos.iterrows():
                    if str(prod_row.get('Item', '')).strip().upper() == nome_procurado:
                        c_val = prod_row.get('Custo', prod_row.get('Custo (R$)', 0))
                        df_itens.at[idx, 'Custo Un.'] = safe_float(c_val)
                        break

    config_itens = {
        "Item": st.column_config.TextColumn("Produto", width="medium"),
        "Qtd": st.column_config.NumberColumn("Qtd", min_value=0),
        "Custo Un.": st.column_config.NumberColumn("Custo Fábrica (Un.)", format="R$ %.2f"),
        "Venda Un.": st.column_config.NumberColumn("Venda (Un.)", format="R$ %.2f")
    }
    df_itens_final = st.data_editor(df_itens, column_config=config_itens, num_rows="dynamic", use_container_width=True, key=f"edit_itens_{prefix_key}")
    
    custo_total_produtos = (pd.to_numeric(df_itens_final['Custo Un.'], errors='coerce').fillna(0) * pd.to_numeric(df_itens_final['Qtd'], errors='coerce').fillna(0)).sum()

    # --- 2. SIMULADOR FINANCEIRO (100% DIGITÁVEL) ---
    st.markdown("#### 🧮 Abatimentos e Impostos")
    with st.container(border=True):
        f_col1, f_col2, f_col3 = st.columns(3)
        
        venda_final = f_col1.number_input("Valor da Venda (R$)", value=safe_float(projeto_selecionado.get('valor_venda_total')), format="%.2f", key=f"venda_{prefix_key}")
        
        # IMPOSTO
        emite_nf = f_col2.radio("Nota Fiscal?", ["Não", "Sim"], index=1 if safe_float(projeto_selecionado.get('custo_impostos')) > 0 else 0, key=f"nf_{prefix_key}")
        valor_nf = 0.0
        if emite_nf == "Sim":
            taxa_nf_pct = 6.0 # Padrão
            if not df_taxas_config.empty:
                for _, t_row in df_taxas_config.iterrows():
                    if "NOTA FISCAL" in str(t_row.get('Item', '')).upper() or "NF" in str(t_row.get('Item', '')).upper():
                        taxa_nf_pct = safe_float(t_row.get('Taxa (%)'))
                        break
            valor_nf = venda_final * (taxa_nf_pct / 100)
            f_col2.caption(f"Imposto ({taxa_nf_pct}%): - {utils.to_br_currency(valor_nf)}")
        
        # TAXA DE RECEBIMENTO (CARTÃO/PIX - DIRETO EM %)
        custo_c_salvo = safe_float(projeto_selecionado.get('custo_cartao'))
        perc_previo = (custo_c_salvo / venda_final * 100) if venda_final > 0 else 0.0
        
        taxa_manual_pct = f_col3.number_input("Taxa de Recebimento (%)", value=float(perc_previo), format="%.2f", step=0.01, key=f"taxa_man_{prefix_key}")
        valor_cartao_taxa = venda_final * (taxa_manual_pct / 100)
        f_col3.caption(f"Desconto Recebimento: - {utils.to_br_currency(valor_cartao_taxa)}")
        
        with f_col3.expander("📋 Ver Tabela de Taxas"):
            if not df_taxas_config.empty:
                st.dataframe(df_taxas_config[['Item', 'Taxa (%)']], hide_index=True, use_container_width=True)
            else: 
                st.warning("Sem taxas cadastradas.")

        st.markdown("---")
        f_col4, f_col5, f_col6 = st.columns(3)
        
        perc_comissao_salvo = (safe_float(projeto_selecionado.get('custo_comissao')) / venda_final * 100) if venda_final > 0 else 0.0
        comissao_pct = f_col4.number_input("Comissão (%)", value=float(perc_comissao_salvo), format="%.1f", key=f"com_{prefix_key}")
        valor_comissao = venda_final * (comissao_pct / 100)
        f_col4.caption(f"Valor: - {utils.to_br_currency(valor_comissao)}")

        custo_ext = f_col5.number_input("Materiais Extras (R$)", value=safe_float(projeto_selecionado.get('custo_adicional_materiais')), format="%.2f", key=f"mat_{prefix_key}")
        custo_mo = f_col6.number_input("Mão de Obra / Terceiros (R$)", value=safe_float(projeto_selecionado.get('custo_terceirizados')), format="%.2f", key=f"mao_{prefix_key}")

        # Lógica final de lucro
        abatimentos = valor_nf + valor_cartao_taxa + valor_comissao + custo_ext + custo_mo
        lucro_final = venda_final - custo_total_produtos - abatimentos
        
        st.markdown("<br>", unsafe_allow_html=True)
        r1, r2 = st.columns(2)
        r1.metric("Custo Total (Produtos + Taxas)", utils.to_br_currency(custo_total_produtos + abatimentos))
        margem_r = (lucro_final / venda_final * 100) if venda_final > 0 else 0
        r2.metric("LUCRO LÍQUIDO FINAL", utils.to_br_currency(lucro_final), delta=f"{margem_r:.1f}% Margem")

    notas = st.text_area("Observações", value=str(projeto_selecionado.get('notas_internas', '')) if str(projeto_selecionado.get('notas_internas', '')) != 'nan' else '', key=f"notas_{prefix_key}")

    # --- AÇÕES FINAIS (PDF E SALVAMENTO) ---
    st.markdown("<br>", unsafe_allow_html=True)
    
    with st.expander("📄 GERAR PDF DO ORÇAMENTO"):
        col_pdf1, col_pdf2 = st.columns([1, 1])
        modelo_capa = col_pdf1.selectbox("Modelo para Capa", [
            "Aquecedor Solar Tradicional", 
            "Aquecedor Solar a Vácuo Acoplado", 
            "Aquecedor Solar Modular", 
            "Aquecedor de Piscina - Tradicional", 
            "Aquecedor de Piscina - Trocador de Calor", 
            "Sistema de Pressurização"
        ], index=3, key=f"capa_{prefix_key}")
        
        if col_pdf2.button("GERAR PRÉVIA DO PDF", use_container_width=True, key=f"btn_pdf_{prefix_key}"):
            # Reconstruindo os dados para o PDF
            itens_pdf = projeto_selecionado.get('detalhamento_itens', [])
            df_pdf = pd.DataFrame(itens_pdf)
            if not df_pdf.empty:
                df_pdf['Quantidade'] = df_pdf.get('Qtd', 0)
                df_pdf['Produto da Base'] = df_pdf.get('Item', '')
                df_pdf['Produto Manual'] = ""
                df_pdf['Venda Total'] = df_pdf['Quantidade'] * df_pdf.get('Venda Un.', 0)
                df_pdf['Descrição'] = df_pdf.get('Descrição', "")
            else:
                df_pdf = pd.DataFrame(columns=['Quantidade', 'Produto da Base', 'Produto Manual', 'Venda Total', 'Descrição'])
            
            nome_c = projeto_selecionado.get('nome_cliente', 'Cliente')
            tel_c = projeto_selecionado.get('telefone_cliente', '')
            serv_text = str(projeto_selecionado.get('servicos_adquiridos', ''))
            if serv_text == 'nan': serv_text = ""
            val_tot = safe_float(projeto_selecionado.get('valor_venda_total'))
            obs_pdf = str(projeto_selecionado.get('notas_internas', 'Material Hidráulico não incluído na proposta'))
            if obs_pdf == 'nan' or obs_pdf.strip() == '': obs_pdf = "Material Hidráulico não incluído na proposta"

            pdf_bytes = utils.gerar_pdf_orcamento(
                nome=nome_c, tel=tel_c, capa=modelo_capa, df_items=df_pdf, 
                d_s=serv_text, v_s=0.0, d_o="", v_o=0.0, total=val_tot, obs=obs_pdf, mostrar_un=False
            )
            st.session_state[f'pdf_gerado_{prefix_key}'] = pdf_bytes
            
        if f'pdf_gerado_{prefix_key}' in st.session_state:
            st.download_button("📥 BAIXAR PDF DO ORÇAMENTO", data=st.session_state[f'pdf_gerado_{prefix_key}'], file_name=f"ORCAMENTO_{projeto_selecionado.get('nome_cliente', 'Cliente')}.pdf", mime="application/pdf", use_container_width=True, key=f"dl_pdf_{prefix_key}")

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Lógica de Exclusão vs Salvamento
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
                "status_projeto": novo_status, 
                "data_conclusao": nova_data.strftime('%Y-%m-%d'),
                "detalhamento_itens": df_itens_final.to_dict('records'),
                "custo_adicional_materiais": custo_ext, 
                "custo_terceirizados": custo_mo,
                "custo_comissao": valor_comissao, 
                "custo_impostos": valor_nf,
                "custo_cartao": valor_cartao_taxa, 
                "valor_venda_total": venda_final,
                "lucro_estimado": lucro_final, 
                "notas_internas": notas
            }
            try:
                supabase.table('servicos_andamento').update(dados).eq('id', int(projeto_selecionado['id'])).execute()
                st.success("✅ Atualizado com sucesso!")
                st.rerun()
            except Exception as e: 
                st.error(f"Erro ao salvar: {e}")

def renderizar():
    st.markdown("## 📋 Gestão de Serviços")
    supabase = st.session_state.supabase
    
    try:
        res = supabase.table('servicos_andamento').select("*").order("id", desc=True).execute()
        df = pd.DataFrame(res.data)
    except: 
        st.error("Erro de conexão com o banco de dados.")
        return
        
    if df.empty: 
        st.info("Nenhum serviço ou orçamento encontrado.")
        return

    df_taxas = utils.load_taxas()
    df_produtos = utils.load_catalog('catalogo_produtos')
    
    df['ir_finalizados'] = df.apply(lambda x: deve_ir_para_finalizados(x['status_projeto'], x['data_conclusao']), axis=1)

    # Considera os status ativos (Incluindo os antigos para evitar bugs)
    ativos_status = ["Em Andamento", "Aguardando Pagamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO"]
    
    df_orc = df[~df['status_projeto'].isin(ativos_status)].reset_index(drop=True)
    df_fin = df[df['ir_finalizados'] == True].reset_index(drop=True)
    df_atv = df[(df['status_projeto'].isin(ativos_status)) & (df['ir_finalizados'] == False)].reset_index(drop=True)

    aba1, aba2, aba3 = st.tabs(["🚀 Em Andamento", "📝 Orçamentos", "✅ Finalizados"])
    
    colunas_visiveis = ['id', 'numero_orcamento', 'nome_cliente', 'status_projeto', 'valor_venda_total', 'lucro_estimado', 'data_conclusao']
    
    config_colunas = {
        "id": "ID",
        "numero_orcamento": "Nº Orçamento",
        "nome_cliente": "Cliente",
        "status_projeto": "Status",
        "valor_venda_total": st.column_config.NumberColumn("Venda Total", format="R$ %.2f"),
        "lucro_estimado": st.column_config.NumberColumn("Lucro Líquido", format="R$ %.2f"),
        "data_conclusao": "Data"
    }
    
    with aba1:
        sel = st.dataframe(df_atv[colunas_visiveis], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, column_config=config_colunas, key="g_atv")
        
        total_lucro_atv = pd.to_numeric(df_atv['lucro_estimado'], errors='coerce').fillna(0).sum()
        st.markdown(f"<div style='text-align: right; color: #004488; font-size: 18px; font-weight: bold; margin-bottom: 20px;'>Total Lucro Líquido Estimado: {utils.to_br_currency(total_lucro_atv)}</div>", unsafe_allow_html=True)
        
        # Trava de Segurança
        if sel.selection.rows and len(df_atv) > sel.selection.rows[0]: 
            exibir_painel_detalhado(df_atv.iloc[sel.selection.rows[0]], supabase, df_taxas, df_produtos, f"atv_{df_atv.iloc[sel.selection.rows[0]]['id']}")
    
    with aba2:
        sel = st.dataframe(df_orc[colunas_visiveis], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, column_config=config_colunas, key="g_orc")
        
        total_lucro_orc = pd.to_numeric(df_orc['lucro_estimado'], errors='coerce').fillna(0).sum()
        st.markdown(f"<div style='text-align: right; color: #004488; font-size: 18px; font-weight: bold; margin-bottom: 20px;'>Total Lucro Líquido Estimado: {utils.to_br_currency(total_lucro_orc)}</div>", unsafe_allow_html=True)
        
        # Trava de Segurança
        if sel.selection.rows and len(df_orc) > sel.selection.rows[0]: 
            exibir_painel_detalhado(df_orc.iloc[sel.selection.rows[0]], supabase, df_taxas, df_produtos, f"orc_{df_orc.iloc[sel.selection.rows[0]]['id']}")

    with aba3:
        st.caption("Serviços concluídos em meses anteriores.")
        sel = st.dataframe(df_fin[colunas_visiveis], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True, column_config=config_colunas, key="g_fin")
        
        total_lucro_fin = pd.to_numeric(df_fin['lucro_estimado'], errors='coerce').fillna(0).sum()
        st.markdown(f"<div style='text-align: right; color: #004488; font-size: 18px; font-weight: bold; margin-bottom: 20px;'>Total Lucro Líquido Realizado: {utils.to_br_currency(total_lucro_fin)}</div>", unsafe_allow_html=True)
        
        # Trava de Segurança
        if sel.selection.rows and len(df_fin) > sel.selection.rows[0]: 
            exibir_painel_detalhado(df_fin.iloc[sel.selection.rows[0]], supabase, df_taxas, df_produtos, f"fin_{df_fin.iloc[sel.selection.rows[0]]['id']}")
