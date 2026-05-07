import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar():
    st.markdown("## 📋 Gestão de Serviços em Andamento (CRM)")
    
    supabase = st.session_state.supabase
    
    # 1. CARREGAMENTO DOS PROJETOS
    try:
        resposta_servicos = supabase.table('servicos_andamento').select("*").order("id", desc=True).execute()
        df_projetos = pd.DataFrame(resposta_servicos.data)
    except Exception as erro_banco:
        st.error(f"Erro ao carregar serviços: {erro_banco}")
        return

    if df_projetos.empty:
        st.info("Nenhum projeto em andamento encontrado.")
        return

    # 2. TABELA PRINCIPAL DE SELEÇÃO
    st.markdown("### 📊 Lista de Projetos")
    colunas_para_exibir = ['id', 'numero_orcamento', 'nome_cliente', 'status_projeto', 'valor_venda_total', 'data_conclusao']
    df_visualizacao = df_projetos[[coluna for coluna in colunas_para_exibir if coluna in df_projetos.columns]].copy()
    
    selecao_usuario = st.dataframe(
        df_visualizacao,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True
    )

    # 3. DETALHAMENTO E SIMULADOR FINANCEIRO
    def exibir_painel_detalhado(linha_selecionada, supabase):
        st.markdown("---")
        st.markdown(f"### 🔍 Gerenciar Projeto: {linha_selecionada.get('nome_cliente', 'Cliente não identificado')}")
        
        # --- BUSCA DE TAXAS NAS CONFIGURAÇÕES ---
        df_taxas_base = utils.load_taxas()
        
        # --- STATUS E DATA ---
        coluna_status, coluna_data = st.columns(2)
        status_no_banco = linha_selecionada.get('status_projeto', 'Orçamento Enviado')
        lista_opcoes_status = ["Orçamento Enviado", "Em Andamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO", "Cancelado"]
        
        novo_status_selecionado = coluna_status.selectbox("Alterar Status", lista_opcoes_status, index=lista_opcoes_status.index(status_no_banco) if status_no_banco in lista_opcoes_status else 0)
        
        data_banco = linha_selecionada.get('data_conclusao')
        data_inicial = datetime.datetime.strptime(str(data_banco), '%Y-%m-%d').date() if data_banco else datetime.date.today()
        nova_data_conclusao = coluna_data.date_input("Data de Conclusão", value=data_inicial)

        # --- TABELA DE ITENS (Com Cadastro Dinâmico) ---
        lista_itens_json = linha_selecionada.get('detalhamento_itens', [])
        if isinstance(lista_itens_json, list) and len(lista_itens_json) > 0:
            df_itens_projeto = pd.DataFrame(lista_itens_json)
        else:
            df_itens_projeto = pd.DataFrame(columns=['Item', 'Qtd', 'Venda Un.', 'Custo Un.', 'Descrição'])
            
        colunas_obrigatorias = {'Custo Un.': 0.0, 'Qtd': 0, 'Venda Un.': 0.0, 'Item': '', 'Descrição': ''}
        df_itens_projeto = df_itens_projeto.assign(**{col: val for col, val in colunas_obrigatorias.items() if col not in df_itens_projeto.columns})

        df_itens_projeto['Custo Un.'] = pd.to_numeric(df_itens_projeto['Custo Un.'], errors='coerce').fillna(0.0)
        df_itens_projeto['Qtd'] = pd.to_numeric(df_itens_projeto['Qtd'], errors='coerce').fillna(0)
        
        st.markdown("#### 🛒 Itens e Custos de Materiais")
        st.info("💡 Você pode adicionar ou apagar itens preenchendo as linhas em branco abaixo da tabela.")
        
        config_itens = {
            "Item": st.column_config.TextColumn("Produto / Item", width="medium"),
            "Descrição": st.column_config.TextColumn("Descrição", width="large"),
            "Qtd": st.column_config.NumberColumn("Qtd", min_value=0),
            "Custo Un.": st.column_config.NumberColumn("Custo Base Un. (R$)", format="R$ %.2f"),
            "Venda Un.": st.column_config.NumberColumn("Venda Un. (R$)", format="R$ %.2f")
        }
        
        df_editado_itens = st.data_editor(df_itens_projeto, column_config=config_itens, num_rows="dynamic", use_container_width=True, key=f"editor_itens_{linha_selecionada['id']}")
        soma_custo_materiais_base = (df_editado_itens['Custo Un.'] * df_editado_itens['Qtd']).sum()

        # ==========================================
        # SIMULADOR FINANCEIRO (LUCRO REAL)
        # ==========================================
        st.markdown("#### 🧮 Fechamento (Impostos, Taxas e Custos Reais)")
        
        with st.container(border=True):
            col_financeiro_1, col_financeiro_2, col_financeiro_3 = st.columns(3)
            
            # 1. VALOR DA VENDA
            valor_venda_final = col_financeiro_1.number_input("Valor Total Fechado (R$)", value=float(linha_selecionada.get('valor_venda_total', 0.0)), format="%.2f")
            
            # 2. IMPOSTO (NOTA FISCAL)
            opcao_nota_fiscal = col_financeiro_2.radio("Emitir Nota Fiscal?", ["Não", "Sim"], index=1 if float(linha_selecionada.get('custo_impostos', 0.0)) > 0 else 0)
            taxa_nota_fiscal = 0.0
            if opcao_nota_fiscal == "Sim":
                busca_nf = df_taxas_base[df_taxas_base['Item'].str.contains("Nota Fiscal|NF|Imposto", case=False, na=False)]
                taxa_nota_fiscal = float(busca_nf['Taxa (%)'].values[0]) if not busca_nf.empty else 6.0
            
            valor_imposto_calculado = (valor_venda_final * (taxa_nota_fiscal / 100))
            col_financeiro_2.caption(f"Custo Imposto ({taxa_nota_fiscal}%): {utils.to_br_currency(valor_imposto_calculado)}")

            # 3. FORMA DE PAGAMENTO (Direto das Configurações)
            lista_formas_pagamento = ["PIX / Sem Taxa"] + df_taxas_base['Item'].tolist()
            pagamento_salvo = linha_selecionada.get('forma_pagamento', 'PIX / Sem Taxa')
            if pagamento_salvo not in lista_formas_pagamento: lista_formas_pagamento.append(pagamento_salvo)
                
            forma_recebimento = col_financeiro_3.selectbox("Opção de Recebimento", lista_formas_pagamento, index=lista_formas_pagamento.index(pagamento_salvo))
            
            custo_maquininha_cartao = 0.0
            taxa_cartao_percentual = 0.0
            if forma_recebimento != "PIX / Sem Taxa" and not df_taxas_base.empty:
                busca_taxa_cartao = df_taxas_base[df_taxas_base['Item'] == forma_recebimento]
                if not busca_taxa_cartao.empty:
                    taxa_cartao_percentual = float(busca_taxa_cartao['Taxa (%)'].values[0])
                    custo_maquininha_cartao = valor_venda_final * (taxa_cartao_percentual / 100)
            
            col_financeiro_3.caption(f"Custo Financeiro ({taxa_cartao_percentual}%): {utils.to_br_currency(custo_maquininha_cartao)}")

            st.markdown("---")
            col_financeiro_4, col_financeiro_5, col_financeiro_6 = st.columns(3)
            
            # 4. OUTROS CUSTOS OPERACIONAIS
            custo_materiais_ajustado = col_financeiro_4.number_input("Materiais de Instalação (Extras)", value=float(linha_selecionada.get('custo_adicional_materiais', 0.0)), format="%.2f")
            custo_mao_de_obra = col_financeiro_5.number_input("Mão de Obra / Instaladores", value=float(linha_selecionada.get('custo_terceirizados', 0.0)), format="%.2f")
            
            # COMISSÃO (Transformado para Percentual)
            pct_comissao = col_financeiro_6.number_input("Comissão do Vendedor (%)", value=float(linha_selecionada.get('pct_comissao', 0.0)), format="%.2f")
            valor_comissao = valor_venda_final * (pct_comissao / 100)
            col_financeiro_6.caption(f"Custo Comissão: {utils.to_br_currency(valor_comissao)}")

            # --- MATEMÁTICA DO CUSTO REAL E LUCRO FINAL ---
            custo_materiais_total = soma_custo_materiais_base + custo_materiais_ajustado
            custo_total_projeto = custo_materiais_total + custo_mao_de_obra + valor_comissao + valor_imposto_calculado + custo_maquininha_cartao
            
            lucro_liquido_real = valor_venda_final - custo_total_projeto
            
            st.markdown("<br>", unsafe_allow_html=True)
            metrica_1, metrica_2 = st.columns(2)
            metrica_1.metric("Custo Operacional (Total Real)", utils.to_br_currency(custo_total_projeto))
            
            margem_percentual = ((lucro_liquido_real / valor_venda_final) * 100) if valor_venda_final > 0 else 0
            metrica_2.metric(
                "LUCRO LÍQUIDO FINAL", 
                utils.to_br_currency(lucro_liquido_real), 
                delta=f"{margem_percentual:.1f}% de Margem Líquida",
                delta_color="normal" if lucro_liquido_real > 0 else "inverse"
            )

        observacoes_internas = st.text_area("Notas e Observações do Projeto", value=str(linha_selecionada.get('notas_internas', '')))

        # --- BOTÃO DE ATUALIZAÇÃO ---
        if st.button("💾 ATUALIZAR E SALVAR DADOS DO PROJETO", type="primary", use_container_width=True):
            dicionario_atualizacao = {
                "status_projeto": novo_status_selecionado,
                "data_conclusao": nova_data_conclusao.strftime('%Y-%m-%d'),
                "detalhamento_itens": df_editado_itens.to_dict('records'),
                "custo_adicional_materiais": custo_materiais_ajustado,
                "custo_terceirizados": custo_mao_de_obra,
                "pct_comissao": pct_comissao,
                "custo_comissao": valor_comissao,
                "custo_impostos": valor_imposto_calculado,
                "forma_pagamento": forma_recebimento,
                "custo_cartao": custo_maquininha_cartao,
                "valor_venda_total": valor_venda_final,
                "lucro_estimado": lucro_liquido_real,
                "notas_internas": observacoes_internas
            }
            try:
                supabase.table('servicos_andamento').update(dicionario_atualizacao).eq('id', linha_selecionada['id']).execute()
                st.success("✅ Projeto atualizado! O lucro líquido exato foi salvo.")
                st.rerun()
            except Exception as erro_salvamento:
                st.error(f"Erro ao salvar alterações: {erro_salvamento}")

    if selecao_usuario.selection.rows:
        indice_selecionado = selecao_usuario.selection.rows[0]
        exibir_painel_detalhado(df_projetos.iloc[indice_selecionado], supabase)
