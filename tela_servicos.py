import streamlit as st
import pandas as pd
import datetime
import utils

def exibir_painel_detalhado(projeto_selecionado, supabase, df_taxas_config, df_produtos, prefix_key):
    st.markdown("---")
    st.markdown(f"### ⚙️ Detalhes e Fechamento: **{projeto_selecionado.get('nome_cliente', 'Sem Nome')}**")
    
    # --- STATUS E DATA ---
    col_esq, col_dir = st.columns(2)
    status_atual = projeto_selecionado.get('status_projeto', 'Orçamento Enviado')
    todas_opcoes = ["Orçamento Enviado", "Em Andamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO", "Cancelado"]
    
    novo_status = col_esq.selectbox("Alterar Status", todas_opcoes, index=todas_opcoes.index(status_atual) if status_atual in todas_opcoes else 0, key=f"status_{prefix_key}")
    
    data_bruta = projeto_selecionado.get('data_conclusao')
    data_default = datetime.date.today()
    if pd.notna(data_bruta) and str(data_bruta).lower() not in ['none', 'nan', 'nat', '']:
        try: data_default = pd.to_datetime(data_bruta).date()
        except: pass
    nova_data = col_dir.date_input("Previsão de Conclusão", value=data_default, key=f"data_{prefix_key}")

    # --- 1. PRODUTOS DO ORÇAMENTO (BUSCA DE CUSTO BLINDADA) ---
    st.markdown("#### 🛒 Produtos Adquiridos (Ajuste Quantidades e Custos)")
    itens_json = projeto_selecionado.get('detalhamento_itens', [])
    df_itens = pd.DataFrame(itens_json) if (isinstance(itens_json, list) and len(itens_json) > 0) else pd.DataFrame(columns=['Item', 'Qtd', 'Custo Un.', 'Venda Un.'])
    
    for coluna in ['Item', 'Qtd', 'Custo Un.', 'Venda Un.']:
        if coluna not in df_itens.columns:
            df_itens[coluna] = 0.0 if 'Un.' in coluna or 'Qtd' in coluna else ""

    # MOTOR DE BUSCA DO CUSTO 100% BLINDADO
    if not df_produtos.empty:
        for idx, row in df_itens.iterrows():
            custo_atual = 0.0
            try: custo_atual = float(row.get('Custo Un.', 0))
            except: pass
                
            if custo_atual == 0.0:
                nome_procurado = str(row.get('Item', '')).strip().upper()
                for _, prod_row in df_produtos.iterrows():
                    nome_catalogo = str(prod_row.get('Item', '')).strip().upper()
                    if nome_procurado == nome_catalogo:
                        c_val = prod_row.get('Custo', 0)
                        if pd.isna(c_val) or c_val == 0: 
                            c_val = prod_row.get('Custo (R$)', 0)
                        df_itens.at[idx, 'Custo Un.'] = float(c_val)
                        break

    config_colunas_itens = {
        "Item": st.column_config.TextColumn("Produto", width="medium"),
        "Qtd": st.column_config.NumberColumn("Qtd", min_value=0),
        "Custo Un.": st.column_config.NumberColumn("Custo Fábrica (Un.)", format="R$ %.2f"),
        "Venda Un.": st.column_config.NumberColumn("Preço Venda (Un.)", format="R$ %.2f")
    }
    
    df_itens_final = st.data_editor(df_itens, column_config=config_colunas_itens, num_rows="dynamic", use_container_width=True, key=f"edit_itens_{prefix_key}")
    
    df_itens_final['Custo Un.'] = pd.to_numeric(df_itens_final['Custo Un.'], errors='coerce').fillna(0.0)
    df_itens_final['Qtd'] = pd.to_numeric(df_itens_final['Qtd'], errors='coerce').fillna(0)
    custo_total_produtos = (df_itens_final['Custo Un.'] * df_itens_final['Qtd']).sum()

    # --- 2. SIMULADOR DE TAXAS ---
    st.markdown("#### 🧮 Simulador de Custos e Impostos")
    
    with st.container(border=True):
        f_col1, f_col2, f_col3 = st.columns(3)
        
        valor_venda_fechado = f_col1.number_input("Valor Final da Venda (R$)", value=float(projeto_selecionado.get('valor_venda_total', 0.0)), format="%.2f", key=f"venda_{prefix_key}")
        
        tem_nota = f_col2.radio("Emitir Nota Fiscal?", ["Não", "Sim"], index=1 if float(projeto_selecionado.get('custo_impostos', 0.0)) > 0 else 0, key=f"nf_{prefix_key}")
        valor_nf = 0.0
        if tem_nota == "Sim":
            taxa_nf_pct = 0.0
            if not df_taxas_config.empty:
                for _, t_row in df_taxas_config.iterrows():
                    n_taxa = str(t_row.get('Item', '')).strip().lower()
                    if "nota fiscal" in n_taxa or "nf" in n_taxa or "imposto" in n_taxa:
                        taxa_nf_pct = float(t_row.get('Taxa (%)', 0.0))
                        break
            valor_nf = valor_venda_fechado * (taxa_nf_pct / 100)
            f_col2.caption(f"Imposto ({taxa_nf_pct}%): - {utils.to_br_currency(valor_nf)}")
        
        metodo_pgto = f_col3.selectbox("Forma de Pagamento", ["PIX / Dinheiro", "Cartão de Crédito"], key=f"pgto_{prefix_key}")
        valor_cartao_taxa = 0.0
        if metodo_pgto == "Cartão de Crédito":
            parcelas_selecionadas = f_col3.selectbox("Número de Parcelas", [i for i in range(1, 13)], format_func=lambda x: f"{x}x", key=f"parc_{prefix_key}")
            taxa_cartao_pct = 0.0
            
            # AGORA SIM! A busca é exatamente pelo termo correto: "cartão 1x", "cartão 2x", etc.
            termo_busca = f"cartão {parcelas_selecionadas}x"
            
            if not df_taxas_config.empty:
                for _, t_row in df_taxas_config.iterrows():
                    n_taxa = str(t_row.get('Item', '')).strip().lower()
                    if n_taxa == termo_busca:
                        taxa_cartao_pct = float(t_row.get('Taxa (%)', 0.0))
                        break

            valor_cartao_taxa = valor_venda_fechado * (taxa_cartao_pct / 100)
            f_col3.caption(f"Taxa ({taxa_cartao_pct}%): - {utils.to_br_currency(valor_cartao_taxa)}")
        else:
            f_col3.caption("Taxa PIX: Isento")

        st.markdown("---")
        f_col4, f_col5, f_col6 = st.columns(3)
        
        comissao_percentual = f_col4.number_input("Comissão do Vendedor (%)", value=0.0, format="%.1f", key=f"com_{prefix_key}")
        valor_comissao = valor_venda_fechado * (comissao_percentual / 100)
        f_col4.caption(f"Valor Pago: - {utils.to_br_currency(valor_comissao)}")

        custo_mat_extra = f_col5.number_input("Materiais Extras (R$)", value=float(projeto_selecionado.get('custo_adicional_materiais', 0.0)), format="%.2f", key=f"mat_{prefix_key}")
        custo_mao_obra = f_col6.number_input("Mão de Obra / Terceiros (R$)", value=float(projeto_selecionado.get('custo_terceirizados', 0.0)), format="%.2f", key=f"mao_{prefix_key}")

        # === CÁLCULO FINAL ===
        abatimentos_totais = valor_nf + valor_cartao_taxa + valor_comissao + custo_mat_extra + custo_mao_obra
        lucro_final = valor_venda_fechado - custo_total_produtos - abatimentos_totais
        
        st.markdown("<br>", unsafe_allow_html=True)
        res1, res2 = st.columns(2)
        res1.metric("Custo Operacional Total (Produtos + Taxas)", utils.to_br_currency(custo_total_produtos + abatimentos_totais))
        
        margem_real = (lucro_final / valor_venda_fechado * 100) if valor_venda_fechado > 0 else 0
        res2.metric("LUCRO LÍQUIDO REAL", utils.to_br_currency(lucro_final), delta=f"{margem_real:.1f}% de Margem Líquida")

    notas_internas = st.text_area("Notas e Observações", value=str(projeto_selecionado.get('notas_internas', '')), key=f"notas_{prefix_key}")

    if st.button("💾 GUARDAR ALTERAÇÕES DO PROJETO", type="primary", use_container_width=True, key=f"save_{prefix_key}"):
        dados_para_atualizar = {
            "status_projeto": novo_status,
            "data_conclusao": nova_data.strftime('%Y-%m-%d'),
            "detalhamento_itens": df_itens_final.to_dict('records'),
            "custo_adicional_materiais": custo_mat_extra,
            "custo_terceirizados": custo_mao_obra,
            "custo_comissao": valor_comissao,
            "custo_impostos": valor_nf,
            "custo_cartao": valor_cartao_taxa,
            "valor_venda_total": valor_venda_fechado,
            "lucro_estimado": lucro_final,
            "notas_internas": notas_internas
        }
        try:
            supabase.table('servicos_andamento').update(dados_para_atualizar).eq('id', int(projeto_selecionado['id'])).execute()
            st.success("✅ Alterações guardadas com sucesso!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao guardar: {e}")


def renderizar():
    st.markdown("## 📋 Gestão de Serviços (CRM)")
    
    supabase = st.session_state.supabase
    
    try:
        resposta = supabase.table('servicos_andamento').select("*").order("id", desc=True).execute()
        df_projetos = pd.DataFrame(resposta.data)
    except Exception as erro:
        st.error(f"Erro ao ligar ao banco de dados: {erro}")
        return

    if df_projetos.empty:
        st.info("Nenhum registo encontrado.")
        return

    df_taxas_config = utils.load_taxas()
    df_produtos = utils.load_catalog('catalogo_produtos')

    lista_status_ativos = ["Em Andamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO"]
    
    df_servicos_ativos = df_projetos[df_projetos['status_projeto'].isin(lista_status_ativos)].reset_index(drop=True)
    df_orcamentos_pendentes = df_projetos[~df_projetos['status_projeto'].isin(lista_status_ativos)].reset_index(drop=True)

    colunas_grid = ['id', 'numero_orcamento', 'nome_cliente', 'status_projeto', 'valor_venda_total']

    # --- TABELA 1: SERVIÇOS ATIVOS ---
    st.markdown("### 🚀 Serviços em Andamento")
    selecao_ativo = st.dataframe(
        df_servicos_ativos[[c for c in colunas_grid if c in df_servicos_ativos.columns]],
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        key="grid_ativos"
    )
    
    # O PAINEL ABRE IMEDIATAMENTE AQUI SE CLICAR NA TABELA ACIMA
    if selecao_ativo.selection.rows:
        projeto_selecionado = df_servicos_ativos.iloc[selecao_ativo.selection.rows[0]]
        exibir_painel_detalhado(projeto_selecionado, supabase, df_taxas_config, df_produtos, prefix_key=f"ativo_{projeto_selecionado['id']}")

    st.markdown("---")

    # --- TABELA 2: ORÇAMENTOS ---
    st.markdown("### 📝 Orçamentos em Andamento")
    selecao_orcamento = st.dataframe(
        df_orcamentos_pendentes[[c for c in colunas_grid if c in df_orcamentos_pendentes.columns]],
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        key="grid_orcamentos"
    )

    # O PAINEL ABRE IMEDIATAMENTE AQUI SE CLICAR NA TABELA ACIMA
    if selecao_orcamento.selection.rows and not selecao_ativo.selection.rows:
        projeto_selecionado = df_orcamentos_pendentes.iloc[selecao_orcamento.selection.rows[0]]
        exibir_painel_detalhado(projeto_selecionado, supabase, df_taxas_config, df_produtos, prefix_key=f"orc_{projeto_selecionado['id']}")
