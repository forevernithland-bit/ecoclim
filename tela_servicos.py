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

    # Carrega catálogos para consultas de taxas e custos perdidos
    df_taxas = utils.load_taxas()
    df_produtos_catalogo = utils.load_catalog('catalogo_produtos')

    # 2. TABELA PRINCIPAL DE SELEÇÃO
    st.markdown("### 📊 Lista de Projetos")
    colunas_visiveis = ['id', 'numero_orcamento', 'nome_cliente', 'status_projeto', 'valor_venda_total', 'data_conclusao']
    df_visualizacao = df_projetos[[c for c in colunas_visiveis if c in df_projetos.columns]].copy()
    
    selecao_usuario = st.dataframe(
        df_visualizacao,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True
    )

    # 3. DETALHAMENTO E SIMULADOR FINANCEIRO
    def exibir_painel_detalhado(linha_selecionada):
        st.markdown("---")
        
        # --- CABEÇALHO COM BOTÃO DE VOLTAR ---
        col_titulo, col_botao_voltar = st.columns([3, 1])
        col_titulo.markdown(f"### 🔍 Gerenciar Projeto: {linha_selecionada.get('nome_cliente', 'Sem Nome')}")
        
        if col_botao_voltar.button("⬅️ Criar Novo Orçamento", use_container_width=True):
            # Hack simples para recarregar a página forçando a aba de orçamentos (ajuste conforme seu app.py)
            st.info("Por favor, selecione 'Orçamentos' no menu lateral esquerdo.")
        
        # --- STATUS E DATA ---
        col1, col2 = st.columns(2)
        status_banco = linha_selecionada.get('status_projeto', 'Orçamento Enviado')
        lista_status = ["Orçamento Enviado", "Em Andamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO", "Cancelado"]
        novo_status = col1.selectbox("Status", lista_status, index=lista_status.index(status_banco) if status_banco in lista_status else 0)
        
        data_banco = linha_selecionada.get('data_conclusao')
        data_inicial = datetime.datetime.strptime(str(data_banco), '%Y-%m-%d').date() if data_banco else datetime.date.today()
        nova_data = col2.date_input("Previsão/Conclusão", value=data_inicial)

        # --- SERVIÇO / INSTALAÇÃO DO ORÇAMENTO ---
        # Exibe o que foi fechado no orçamento original para não esquecer
        servico_original = str(linha_selecionada.get('servicos_adquiridos', ''))
        if servico_original and servico_original != 'None':
            st.markdown("#### 🛠️ Serviço / Instalação Fechada no Orçamento")
            st.text_area("Descrição do Serviço Fechado (Apenas Leitura)", value=servico_original, height=80, disabled=True)

        # --- ITENS E EQUIPAMENTOS ---
        itens_json = linha_selecionada.get('detalhamento_itens', [])
        df_itens = pd.DataFrame(itens_json) if (isinstance(itens_json, list) and len(itens_json) > 0) else pd.DataFrame(columns=['Item', 'Qtd', 'Venda Un.', 'Custo Un.', 'Descrição'])
            
        for col in ['Custo Un.', 'Qtd', 'Venda Un.', 'Item', 'Descrição']:
            if col not in df_itens.columns:
                df_itens[col] = 0.0 if 'Un.' in col or 'Qtd' in col else ""

        # INTELIGÊNCIA: Buscar o Custo Un. no catálogo se estiver R$ 0.00
        for idx in df_itens.index:
            try: custo_atual = float(df_itens.at[idx, 'Custo Un.'])
            except: custo_atual = 0.0
                
            if custo_atual == 0.0 and df_itens.at[idx, 'Item']:
                match = df_produtos_catalogo[df_produtos_catalogo['Item'] == df_itens.at[idx, 'Item']]
                if not match.empty:
                    df_itens.at[idx, 'Custo Un.'] = float(match['Custo (R$)'].values[0])

        df_itens['Custo Un.'] = pd.to_numeric(df_itens['Custo Un.'], errors='coerce').fillna(0.0)
        df_itens['Qtd'] = pd.to_numeric(df_itens['Qtd'], errors='coerce').fillna(0)
        
        st.markdown("#### 🛒 Equipamentos e Produtos")
        st.info("💡 **Você pode adicionar novos produtos** preenchendo a linha em branco no final da tabela. O sistema somará o custo ao projeto.")
        
        config_tabela = {
            "Item": st.column_config.TextColumn("Produto / Item", width="medium"),
            "Descrição": st.column_config.TextColumn("Descrição", width="large"),
            "Qtd": st.column_config.NumberColumn("Qtd", min_value=0),
            "Custo Un.": st.column_config.NumberColumn("Custo Base Un. (R$)", format="R$ %.2f"),
            "Venda Un.": st.column_config.NumberColumn("Venda Un. (R$)", format="R$ %.2f")
        }
        
        df_itens_editado = st.data_editor(df_itens, column_config=config_tabela, num_rows="dynamic", use_container_width=True, key=f"ed_itens_{linha_selecionada['id']}")
        
        df_itens_editado['Custo Un.'] = pd.to_numeric(df_itens_editado['Custo Un.'], errors='coerce').fillna(0.0)
        df_itens_editado['Qtd'] = pd.to_numeric(df_itens_editado['Qtd'], errors='coerce').fillna(0)
        
        custo_equipamentos_base = (df_itens_editado['Custo Un.'] * df_itens_editado['Qtd']).sum()

        # ==========================================
        # CALCULADORA INTELIGENTE DE CUSTOS REAIS
        # ==========================================
        st.markdown("#### 🧮 Custos Operacionais e Fechamento")
        
        with st.container(border=True):
            f1, f2, f3 = st.columns(3)
            
            # 1. VALOR DE VENDA
            venda_final = f1.number_input("Valor da Venda Final (R$)", value=float(linha_selecionada.get('valor_venda_total', 0.0)), format="%.2f")
            
            # 2. NOTA FISCAL
            opcao_nf = f2.radio("Emitir Nota Fiscal?", ["Não", "Sim"], index=1 if float(linha_selecionada.get('custo_impostos', 0.0)) > 0 else 0)
            taxa_nf = 0.0
            if opcao_nf == "Sim" and not df_taxas.empty:
                busca_nf = df_taxas[df_taxas['Item'].str.contains("Nota|NF|Imposto", case=False, na=False)]
                if not busca_nf.empty: taxa_nf = float(busca_nf['Taxa (%)'].values[0])
            
            valor_imposto = venda_final * (taxa_nf / 100)
            f2.caption(f"Custo Imposto ({taxa_nf}%): {utils.to_br_currency(valor_imposto)}")

            # 3. FORMA DE PAGAMENTO
            lista_pagamentos = ["PIX / Dinheiro (Sem Taxa)"]
            if not df_taxas.empty:
                lista_pagamentos.extend(df_taxas['Item'].tolist())
                
            pagamento_banco = str(linha_selecionada.get('forma_pagamento', 'PIX / Dinheiro (Sem Taxa)'))
            if pagamento_banco not in lista_pagamentos: lista_pagamentos.append(pagamento_banco)
            
            recebimento = f3.selectbox("Forma de Recebimento", lista_pagamentos, index=lista_pagamentos.index(pagamento_banco))
            
            taxa_cartao_pct = 0.0
            if recebimento != "PIX / Dinheiro (Sem Taxa)" and not df_taxas.empty:
                busca_cartao = df_taxas[df_taxas['Item'] == recebimento]
                if not busca_cartao.empty: taxa_cartao_pct = float(busca_cartao['Taxa (%)'].values[0])
                
            custo_cartao = venda_final * (taxa_cartao_pct / 100)
            f3.caption(f"Taxa Financeira ({taxa_cartao_pct}%): {utils.to_br_currency(custo_cartao)}")

            st.markdown("---")
            f4, f5, f6 = st.columns(3)
            
            # 4. CUSTOS DE INSTALAÇÃO E TERCEIROS
            custo_mat_extra = f4.number_input("Materiais de Instalação Extras (R$)", value=float(linha_selecionada.get('custo_adicional_materiais', 0.0)), format="%.2f")
            custo_terc = f5.number_input("Terceiros / Instaladores (R$)", value=float(linha_selecionada.get('custo_terceirizados', 0.0)), format="%.2f")
            
            # 5. COMISSÃO EM PERCENTUAL (CÁLCULO AUTOMÁTICO)
            pct_comissao = f6.number_input("Comissão do Vendedor (%)", value=float(linha_selecionada.get('pct_comissao', 0.0)), format="%.2f")
            valor_comissao = venda_final * (pct_comissao / 100)
            f6.caption(f"Valor da Comissão: {utils.to_br_currency(valor_comissao)}")

            # --- MATEMÁTICA DO CUSTO REAL E LUCRO FINAL ---
            custos_operacionais = custo_equipamentos_base + custo_mat_extra + custo_terc + valor_imposto + custo_cartao + valor_comissao
            lucro_liquido_real = venda_final - custos_operacionais
            
            st.markdown("<br>", unsafe_allow_html=True)
            m1, m2 = st.columns(2)
            
            m1.metric("Custo Total Operacional (Real)", utils.to_br_currency(custos_operacionais), delta=f"Desse total, {utils.to_br_currency(custo_equipamentos_base)} são os Equipamentos Base", delta_color="off")
            
            margem = ((lucro_liquido_real / venda_final) * 100) if venda_final > 0 else 0
            m2.metric(
                "LUCRO LÍQUIDO FINAL", 
                utils.to_br_currency(lucro_liquido_real), 
                delta=f"{margem:.1f}% de Margem Líquida",
                delta_color="normal" if lucro_liquido_real > 0 else "inverse"
            )

        notas = st.text_area("Anotações do Projeto (Equipe)", value=str(linha_selecionada.get('notas_internas', '')))

        if st.button("💾 ATUALIZAR E SALVAR PROJETO", type="primary", use_container_width=True):
            dados = {
                "status_projeto": novo_status,
                "data_conclusao": nova_data.strftime('%Y-%m-%d'),
                "detalhamento_itens": df_itens_editado.to_dict('records'),
                "custo_adicional_materiais": custo_mat_extra,
                "custo_terceirizados": custo_terc,
                "pct_comissao": pct_comissao,
                "custo_comissao": valor_comissao,
                "custo_impostos": valor_imposto,
                "forma_pagamento": recebimento,
                "custo_cartao": custo_cartao,
                "valor_venda_total": venda_final,
                "lucro_estimado": lucro_liquido_real,
                "notas_internas": notas
            }
            try:
                st.session_state.supabase.table('servicos_andamento').update(dados).eq('id', linha_selecionada['id']).execute()
                st.success("✅ Projeto salvo! O lucro líquido foi atualizado com base nos custos e taxas reais.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

    if selecao_usuario.selection.rows:
        indice = selecao_usuario.selection.rows[0]
        exibir_painel_detalhado(df_projetos.iloc[indice])
