import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar():
    st.markdown("## 📋 Gestão de Serviços em Andamento (CRM)")
    
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

    # Carrega as taxas cadastradas lá na tela de Configurações
    df_taxas = utils.load_taxas()

    # ==========================================
    # 2. SEPARAÇÃO DAS TABELAS (O PULO DO GATO)
    # ==========================================
    status_ativos = ["Em Andamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO"]
    
    # Filtra quem está ativo e quem ainda é orçamento pendente/cancelado
    df_ativos = df_projetos[df_projetos['status_projeto'].isin(status_ativos)].reset_index(drop=True)
    df_orcamentos = df_projetos[~df_projetos['status_projeto'].isin(status_ativos)].reset_index(drop=True)

    colunas_exibicao = ['id', 'numero_orcamento', 'nome_cliente', 'status_projeto', 'valor_venda_total', 'data_conclusao']

    st.markdown("### 🚀 Serviços Ativos")
    st.caption("Projetos aprovados e em execução.")
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
    st.caption("Orçamentos enviados aguardando fechamento.")
    sel_orcamentos = st.dataframe(
        df_orcamentos[[c for c in colunas_exibicao if c in df_orcamentos.columns]],
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        key="tab_orcamentos"
    )

    # Identifica de qual tabela o usuário clicou na linha
    linha_sel = None
    if sel_ativos.selection.rows:
        linha_sel = df_ativos.iloc[sel_ativos.selection.rows[0]]
    elif sel_orcamentos.selection.rows:
        linha_sel = df_orcamentos.iloc[sel_orcamentos.selection.rows[0]]

    # ==========================================
    # 3. PAINEL DE FECHAMENTO (A LÓGICA PERFEITA)
    # ==========================================
    if linha_sel is not None:
        st.markdown("---")
        st.markdown(f"### ⚙️ Fechamento do Projeto: **{linha_sel.get('nome_cliente', 'Cliente')}**")
        
        # --- MUDANÇA DE STATUS ---
        c1, c2 = st.columns(2)
        status_atual = linha_sel.get('status_projeto', 'Orçamento Enviado')
        opcoes_status = ["Orçamento Enviado", "Em Andamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO", "Cancelado"]
        
        novo_status = c1.selectbox("Status (Muda o projeto de tabela)", opcoes_status, index=opcoes_status.index(status_atual) if status_atual in opcoes_status else 0)
        
        data_db = linha_sel.get('data_conclusao')
        data_ini = datetime.datetime.strptime(str(data_db), '%Y-%m-%d').date() if data_db else datetime.date.today()
        nova_data = c2.date_input("Data de Conclusão", value=data_ini)

        # --- CÁLCULO DE CUSTO DOS PRODUTOS ---
        itens_json = linha_sel.get('detalhamento_itens', [])
        if isinstance(itens_json, list) and len(itens_json) > 0:
            df_itens = pd.DataFrame(itens_json)
        else:
            df_itens = pd.DataFrame(columns=['Item', 'Qtd', 'Venda Un.', 'Custo Un.'])
            
        # Garante as colunas para não dar erro
        for col in ['Custo Un.', 'Qtd', 'Venda Un.']:
            if col not in df_itens.columns:
                df_itens[col] = 0.0

        # Pega o custo dos equipamentos que foram salvos no orçamento
        df_itens['Custo Un.'] = pd.to_numeric(df_itens['Custo Un.'], errors='coerce').fillna(0.0)
        df_itens['Qtd'] = pd.to_numeric(df_itens['Qtd'], errors='coerce').fillna(0)
        custo_total_produtos = (df_itens['Custo Un.'] * df_itens['Qtd']).sum()

        st.info(f"📦 **Custo de Fábrica dos Equipamentos:** {utils.to_br_currency(custo_total_produtos)}")

        # --- SIMULADOR DE ABATIMENTO DE TAXAS ---
        st.markdown("#### 🧮 Abatimentos e Lucro Real")
        with st.container(border=True):
            # O Valor fechado já vem pronto do orçamento
            valor_venda = float(linha_sel.get('valor_venda_total', 0.0))
            
            # MARGEM INICIAL (Venda - Custo Equipamentos)
            margem_inicial = valor_venda - custo_total_projeto if 'custo_total_projeto' in locals() else valor_venda - custo_total_produtos
            
            st.markdown(f"**Valor do Fechamento:** :blue[{utils.to_br_currency(valor_venda)}] | **Margem Bruta (S/ Taxas):** :orange[{utils.to_br_currency(margem_inicial)}]")
            st.markdown("---")
            
            col_t1, col_t2, col_t3 = st.columns(3)
            
            # 1. IMPOSTO NF
            emite_nf = col_t1.radio("Nota Fiscal?", ["Não", "Sim"], index=1 if float(linha_sel.get('custo_impostos', 0.0)) > 0 else 0)
            valor_imposto = 0.0
            if emite_nf == "Sim":
                busca_nf = df_taxas[df_taxas['Item'].str.contains("Nota Fiscal|NF", case=False, na=False)]
                taxa_nf_pct = float(busca_nf['Taxa (%)'].values[0]) if not busca_nf.empty else 6.0
                valor_imposto = valor_venda * (taxa_nf_pct / 100)
                col_t1.caption(f"Abatimento NF ({taxa_nf_pct}%): - {utils.to_br_currency(valor_imposto)}")
            
            # 2. FORMA DE PAGAMENTO (CARTÃO PUXA A TAXA DO BANCO)
            forma_pagto = col_t2.selectbox("Pagamento", ["PIX / Dinheiro", "Cartão de Crédito"])
            valor_taxa_cartao = 0.0
            if forma_pagto == "Cartão de Crédito":
                parcelas = col_t2.selectbox("Parcelas", [f"{i}x" for i in range(1, 13)])
                busca_cartao = df_taxas[df_taxas['Item'].str.contains(f"Cartão {parcelas}", case=False, na=False)]
                taxa_cartao_pct = float(busca_cartao['Taxa (%)'].values[0]) if not busca_cartao.empty else 0.0
                valor_taxa_cartao = valor_venda * (taxa_cartao_pct / 100)
                col_t2.caption(f"Taxa Maquininha ({taxa_cartao_pct}%): - {utils.to_br_currency(valor_taxa_cartao)}")
            else:
                col_t2.caption("Taxa PIX: R$ 0,00")
                
            # 3. COMISSÃO EM PERCENTUAL
            comissao_pct = col_t3.number_input("Comissão (%)", value=0.0, format="%.1f")
            # Caso a comissão já tenha sido salva como valor antes, converte para exibir.
            # Aqui calculamos sobre o valor de venda.
            valor_comissao = valor_venda * (comissao_pct / 100)
            col_t3.caption(f"Abatimento Comissão: - {utils.to_br_currency(valor_comissao)}")

            st.markdown("---")
            col_e1, col_e2 = st.columns(2)
            # 4. CUSTOS EXTRAS MANUAIS
            custo_materiais_extra = col_e1.number_input("Custos de Instalação/Materiais Extras (R$)", value=float(linha_sel.get('custo_adicional_materiais', 0.0)), format="%.2f")
            custo_terceiros = col_e2.number_input("Mão de Obra / Terceirizados (R$)", value=float(linha_sel.get('custo_terceirizados', 0.0)), format="%.2f")

            # === CÁLCULO FINAL DE LUCRO LÍQUIDO ===
            total_abatimentos = valor_imposto + valor_taxa_cartao + valor_comissao + custo_materiais_extra + custo_terceiros
            lucro_liquido_real = margem_inicial - total_abatimentos
            
            st.markdown("<br>", unsafe_allow_html=True)
            c_res1, c_res2 = st.columns(2)
            c_res1.metric("Total de Custos e Taxas", utils.to_br_currency(custo_total_produtos + total_abatimentos))
            
            margem_final_pct = (lucro_liquido_real / valor_venda * 100) if valor_venda > 0 else 0
            c_res2.metric("LUCRO LÍQUIDO FINAL", utils.to_br_currency(lucro_liquido_real), delta=f"{margem_final_pct:.1f}% de Margem Líquida", delta_color="normal" if lucro_liquido_real > 0 else "inverse")

        notas = st.text_area("Notas / Observações", value=str(linha_sel.get('notas_internas', '')))

        # === SALVAMENTO ===
        if st.button("💾 SALVAR PROJETO", type="primary", use_container_width=True):
            dados_upd = {
                "status_projeto": novo_status,
                "data_conclusao": nova_data.strftime('%Y-%m-%d'),
                "custo_adicional_materiais": custo_materiais_extra,
                "custo_terceirizados": custo_terceiros,
                "custo_comissao": valor_comissao,
                "custo_impostos": valor_imposto,
                "custo_cartao": valor_taxa_cartao,
                "valor_venda_total": valor_venda,
                "lucro_estimado": lucro_liquido_real,
                "notas_internas": notas
            }
            try:
                supabase.table('servicos_andamento').update(dados_upd).eq('id', int(linha_sel['id'])).execute()
                st.success("✅ Fechamento atualizado! As taxas foram abatidas do lucro final e salvas.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
