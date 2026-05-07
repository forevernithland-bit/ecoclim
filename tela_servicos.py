import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar():
    st.markdown("## 📋 Gestão de Serviços (CRM)")
    
    supabase = st.session_state.supabase
    
    # ==========================================
    # 1. CARREGAMENTO DOS DADOS E TAXAS
    # ==========================================
    try:
        res_servicos = supabase.table('servicos_andamento').select("*").order("id", desc=True).execute()
        df_projetos = pd.DataFrame(res_servicos.data)
    except Exception as e:
        st.error(f"Erro ao carregar serviços: {e}")
        return

    if df_projetos.empty:
        st.info("Nenhum orçamento ou serviço encontrado no banco de dados.")
        return

    # Carrega as taxas cadastradas na tela de Configurações
    df_taxas = utils.load_taxas()

    # ==========================================
    # 2. SEPARAÇÃO DAS TABELAS (ATIVOS VS ORÇAMENTOS)
    # ==========================================
    status_ativos = ["Em Andamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO"]
    
    df_ativos = df_projetos[df_projetos['status_projeto'].isin(status_ativos)].reset_index(drop=True)
    df_orcamentos = df_projetos[~df_projetos['status_projeto'].isin(status_ativos)].reset_index(drop=True)

    colunas_exibicao = ['id', 'numero_orcamento', 'nome_cliente', 'status_projeto', 'valor_venda_total', 'data_conclusao']

    st.markdown("### 🚀 Serviços Ativos")
    sel_ativos = st.dataframe(
        df_ativos[[c for c in colunas_exibicao if c in df_ativos.columns]],
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        key="tab_ativos"
    )

    st.markdown("---")
    st.markdown("### 📝 Orçamentos Pendentes")
    sel_orcamentos = st.dataframe(
        df_orcamentos[[c for c in colunas_exibicao if c in df_orcamentos.columns]],
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        key="tab_orcamentos"
    )

    # Identifica qual linha foi selecionada em qualquer uma das tabelas
    linha_sel = None
    if sel_ativos.selection.rows:
        linha_sel = df_ativos.iloc[sel_ativos.selection.rows[0]]
    elif sel_orcamentos.selection.rows:
        linha_sel = df_orcamentos.iloc[sel_orcamentos.selection.rows[0]]

    # ==========================================
    # 3. PAINEL DE DETALHAMENTO (LOGICA DE FECHAMENTO)
    # ==========================================
    if linha_sel is not None:
        st.markdown("---")
        st.markdown(f"### ⚙️ Detalhes e Fechamento: **{linha_sel.get('nome_cliente', 'Cliente')}**")
        
        c_status, c_data = st.columns(2)
        
        # --- STATUS E DATA (COM BLINDAGEM) ---
        status_atual = linha_sel.get('status_projeto', 'Orçamento Enviado')
        opcoes_status = ["Orçamento Enviado", "Em Andamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO", "Cancelado"]
        novo_status = c_status.selectbox("Alterar Status", opcoes_status, index=opcoes_status.index(status_atual) if status_atual in opcoes_status else 0)
        
        data_banco = linha_sel.get('data_conclusao')
        data_inicial = datetime.date.today()
        if pd.notna(data_banco) and str(data_banco).strip().lower() not in ['none', 'nan', 'null', 'nat', '']:
            try:
                data_inicial = datetime.datetime.strptime(str(data_banco)[:10], '%Y-%m-%d').date()
            except: pass
        nova_data = c_data.date_input("Previsão de Conclusão", value=data_inicial)

        # --- 1. PRODUTOS E QUANTIDADES (EDITÁVEL) ---
        st.markdown("#### 🛒 Itens do Orçamento")
        itens_json = linha_sel.get('detalhamento_itens', [])
        df_itens_ed = pd.DataFrame(itens_json) if (isinstance(itens_json, list) and len(itens_json) > 0) else pd.DataFrame(columns=['Item', 'Descrição', 'Qtd', 'Custo Un.', 'Venda Un.'])
        
        # Garantia de colunas e tipos
        for col in ['Item', 'Descrição', 'Qtd', 'Custo Un.', 'Venda Un.']:
            if col not in df_itens_ed.columns: df_itens_ed[col] = 0.0 if 'Un.' in col or 'Qtd' in col else ""
        
        df_itens_ed['Custo Un.'] = pd.to_numeric(df_itens_ed['Custo Un.'], errors='coerce').fillna(0.0)
        df_itens_ed['Venda Un.'] = pd.to_numeric(df_itens_ed['Venda Un.'], errors='coerce').fillna(0.0)
        df_itens_ed['Qtd'] = pd.to_numeric(df_itens_ed['Qtd'], errors='coerce').fillna(0)

        config_itens = {
            "Item": st.column_config.TextColumn("Produto", width="medium"),
            "Qtd": st.column_config.NumberColumn("Qtd", min_value=0),
            "Custo Un.": st.column_config.NumberColumn("Custo Fábrica (Un.)", format="R$ %.2f"),
            "Venda Un.": st.column_config.NumberColumn("Venda (Un.)", format="R$ %.2f")
        }
        
        df_final_itens = st.data_editor(df_itens_ed, column_config=config_itens, num_rows="dynamic", use_container_width=True, key=f"editor_itens_{linha_sel['id']}")
        
        # Cálculos baseados nos itens
        custo_total_produtos = (df_final_itens['Custo Un.'] * df_final_itens['Qtd']).sum()
        venda_sugerida = (df_final_itens['Venda Un.'] * df_final_itens['Qtd']).sum()

        # --- 2. SIMULADOR DE TAXAS (BUSCA NO BANCO) ---
        st.markdown("#### 🧮 Simulador Financeiro")
        with st.container(border=True):
            col_f1, col_f2, col_f3 = st.columns(3)
            
            # Valor da Venda Final
            venda_final = col_f1.number_input("Valor Final Fechado (R$)", value=float(venda_sugerida), format="%.2f")
            
            # Imposto (Nota Fiscal) - Busca em Configurações
            emite_nf = col_f2.radio("Emitir Nota Fiscal?", ["Não", "Sim"], index=1 if float(linha_sel.get('custo_impostos', 0.0)) > 0 else 0)
            valor_imposto = 0.0
            if emite_nf == "Sim":
                busca_nf = df_taxas[df_taxas['Item'].str.contains("Nota Fiscal|NF", case=False, na=False)]
                taxa_nf = float(busca_nf['Taxa (%)'].values[0]) if not busca_nf.empty else 6.0
                valor_imposto = venda_final * (taxa_nf / 100)
                col_f2.caption(f"Taxa NF ({taxa_nf}%): - {utils.to_br_currency(valor_imposto)}")
            
            # Cartão de Crédito - Busca Taxas Automáticas
            forma_pgto = col_f3.selectbox("Forma de Pagamento", ["PIX / Dinheiro", "Cartão de Crédito"])
            valor_taxa_cartao = 0.0
            if forma_pgto == "Cartão de Crédito":
                parc = col_f3.selectbox("Parcelas", [f"{i}x" for i in range(1, 13)])
                busca_c = df_taxas[df_taxas['Item'].str.contains(f"Cartão {parc}", case=False, na=False)]
                taxa_c = float(busca_c['Taxa (%)'].values[0]) if not busca_c.empty else 0.0
                valor_taxa_cartao = venda_final * (taxa_c / 100)
                col_f3.caption(f"Taxa Cartão ({taxa_c}%): - {utils.to_br_currency(valor_taxa_cartao)}")
            else:
                col_f3.caption("Taxa PIX: Isento")

            st.markdown("---")
            col_f4, col_f5, col_f6 = st.columns(3)
            
            # Comissão, Materiais Extras e Mão de Obra
            comissao_pct = col_f4.number_input("Comissão (%)", value=0.0, format="%.1f")
            valor_comissao = venda_final * (comissao_pct / 100)
            col_f4.caption(f"Abatimento: {utils.to_br_currency(valor_comissao)}")

            custo_ext = col_f5.number_input("Materiais Extras (R$)", value=float(linha_sel.get('custo_adicional_materiais', 0.0)), format="%.2f")
            custo_mo = col_f6.number_input("Mão de Obra / Terceiros (R$)", value=float(linha_sel.get('custo_terceirizados', 0.0)), format="%.2f")

            # === CÁLCULO FINAL DO LUCRO (Venda - Custos Prod - Taxas) ===
            abatimentos = valor_imposto + valor_taxa_cartao + valor_comissao + custo_ext + custo_mo
            lucro_liquido = venda_final - custo_total_produtos - abatimentos
            
            st.markdown("<br>", unsafe_allow_html=True)
            r1, r2 = st.columns(2)
            r1.metric("Custo Total (Produtos + Taxas)", utils.to_br_currency(custo_total_produtos + abatimentos))
            
            margem_real = (lucro_liquido / venda_final * 100) if venda_final > 0 else 0
            r2.metric("LUCRO LÍQUIDO FINAL", utils.to_br_currency(lucro_liquido), delta=f"{margem_real:.1f}% Margem")

        notas = st.text_area("Notas e Observações", value=str(linha_sel.get('notas_internas', '')))

        # === SALVAMENTO ===
        if st.button("💾 SALVAR ALTERAÇÕES DO PROJETO", type="primary", use_container_width=True):
            dados_upd = {
                "status_projeto": novo_status,
                "data_conclusao": nova_data.strftime('%Y-%m-%d'),
                "detalhamento_itens": df_final_itens.to_dict('records'),
                "custo_adicional_materiais": custo_ext,
                "custo_terceirizados": custo_mo,
                "custo_comissao": valor_comissao,
                "custo_impostos": valor_imposto,
                "custo_cartao": valor_taxa_cartao,
                "valor_venda_total": venda_final,
                "lucro_estimado": lucro_liquido,
                "notas_internas": notas
            }
            try:
                supabase.table('servicos_andamento').update(dados_upd).eq('id', int(linha_sel['id'])).execute()
                st.success("✅ Projeto atualizado! O lucro líquido foi recalculado com sucesso.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
