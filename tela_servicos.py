import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar():
    st.markdown("## 📋 Gestão de Serviços em Andamento (CRM)")
    
    supabase = st.session_state.supabase
    
    # 1. CARREGAMENTO DOS DADOS
    try:
        res = supabase.table('servicos_andamento').select("*").order("id", desc=True).execute()
        df_orcamentos = pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Erro ao carregar serviços: {e}")
        return

    if df_orcamentos.empty:
        st.info("Nenhum orçamento encontrado.")
        return

    # 2. TABELA PRINCIPAL
    st.markdown("### 📊 Lista de Projetos")
    colunas_exibicao = ['id', 'numero_orcamento', 'nome_cliente', 'status_projeto', 'valor_venda_total', 'data_conclusao']
    df_display = df_orcamentos[[c for c in colunas_exibicao if c in df_orcamentos.columns]].copy()
    
    sel_orc = st.dataframe(
        df_display,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True
    )

    # 3. DETALHAMENTO E SIMULADOR FINANCEIRO
    def exibir_detalhes_avancados(row, supabase):
        st.markdown("---")
        st.markdown(f"### 🔍 Projeto: {row.get('nome_cliente', 'Sem Nome')}")
        
        # --- BLOCO DE STATUS E DATA ---
        c1, c2 = st.columns(2)
        status_atual = row.get('status_projeto', 'Orçamento Enviado')
        opcoes_status = ["Orçamento Enviado", "Em Andamento", "Aguardando Peças", "Concluído PIX", "Concluído CARTÃO", "Cancelado"]
        novo_status = c1.selectbox("Status Atual", opcoes_status, index=opcoes_status.index(status_atual) if status_atual in opcoes_status else 0)
        
        data_conc = row.get('data_conclusao')
        data_padrao = datetime.datetime.strptime(str(data_conc), '%Y-%m-%d').date() if data_conc else datetime.date.today()
        nova_data = c2.date_input("Previsão/Conclusão", value=data_padrao)

        # --- TABELA DE ITENS (BLINDADA) ---
        itens_json = row.get('detalhamento_itens', [])
        df_itens = pd.DataFrame(itens_json) if (isinstance(itens_json, list) and len(itens_json) > 0) else pd.DataFrame(columns=['Item', 'Qtd', 'Venda Un.', 'Custo Un.', 'Descrição'])
        
        # Garantia de colunas para não dar KeyError
        for col in ['Custo Un.', 'Qtd', 'Venda Un.', 'Item', 'Descrição']:
            if col not in df_itens.columns:
                df_itens[col] = 0.0 if 'Un.' in col or 'Qtd' in col else ""

        df_itens['Custo Un.'] = pd.to_numeric(df_itens['Custo Un.'], errors='coerce').fillna(0.0)
        df_itens['Qtd'] = pd.to_numeric(df_itens['Qtd'], errors='coerce').fillna(0)
        
        st.markdown("#### 🛒 Itens do Orçamento")
        df_edit_itens = st.data_editor(df_itens, use_container_width=True, key=f"edit_itens_{row['id']}")
        custo_materiais_base = (df_edit_itens['Custo Un.'] * df_edit_itens['Qtd']).sum()

        # --- SIMULADOR FINANCEIRO DE FECHAMENTO ---
        st.markdown("#### 🧮 Simulador de Fechamento e Custos Reais")
        
        with st.container(border=True):
            col_f1, col_f2, col_f3 = st.columns(3)
            
            # 1. Valor da Venda
            venda_final = col_f1.number_input("Valor Total da Venda (R$)", value=float(row.get('valor_venda_total', 0.0)), format="%.2f")
            
            # 2. Impostos (Nota Fiscal)
            tem_nf = col_f2.radio("Emitir Nota Fiscal?", ["Não", "Sim"], index=1 if float(row.get('custo_impostos', 0.0)) > 0 else 0)
            taxa_nf_padrao = 6.0 # 6% de imposto padrão
            valor_imposto = (venda_final * (taxa_nf_padrao / 100)) if tem_nf == "Sim" else 0.0
            col_f2.caption(f"Imposto Est. (6%): {utils.to_br_currency(valor_imposto)}")

            # 3. Forma de Pagamento e Taxas de Cartão
            forma_pagto = col_f3.selectbox("Forma de Recebimento", ["PIX / Dinheiro", "Cartão de Crédito"])
            custo_cartao = 0.0
            if forma_pagto == "Cartão de Crédito":
                parcelas = col_f3.slider("Quantidade de Parcelas", 1, 12, value=1)
                # Tabela de taxas estimadas (ajuste conforme sua maquininha)
                taxas_cartao = {1: 3.5, 2: 4.8, 3: 5.5, 4: 6.2, 5: 6.9, 6: 7.5, 7: 8.2, 8: 8.9, 9: 9.5, 10: 10.2, 11: 10.8, 12: 11.5}
                percentual_taxa = taxas_cartao.get(parcelas, 12.0)
                custo_cartao = venda_final * (percentual_taxa / 100)
                col_f3.caption(f"Taxa Cartão ({percentual_taxa}%): {utils.to_br_currency(custo_cartao)}")
            else:
                col_f3.caption("Taxa PIX: R$ 0,00")

            st.markdown("---")
            col_f4, col_f5, col_f6 = st.columns(3)
            
            # 4. Outros Custos
            custo_materiais_real = col_f4.number_input("Custo Materiais (Real)", value=float(row.get('custo_adicional_materiais', custo_materiais_base)), format="%.2f")
            custo_terceiros = col_f5.number_input("Mão de Obra / Terceiros", value=float(row.get('custo_terceirizados', 0.0)), format="%.2f")
            comissao = col_f6.number_input("Comissão (R$)", value=float(row.get('custo_comissao', 0.0)), format="%.2f")

            # --- RESULTADO FINAL ---
            lucro_liquido = venda_final - valor_imposto - custo_cartao - custo_mater_real - custo_terceiros - comissao
            
            c_res1, c_res2 = st.columns(2)
            c_res1.metric("Custo Total do Projeto", utils.to_br_currency(valor_imposto + custo_cartao + custo_mater_real + custo_terceiros + comissao))
            
            cor_lucro = "normal" if lucro_liquido > 0 else "inverse"
            c_res2.metric("LUCRO LÍQUIDO FINAL", utils.to_br_currency(lucro_liquido), delta=f"{((lucro_liquido/venda_final)*100 if venda_final > 0 else 0):.1f}% Margem", delta_color=cor_lucro)

        notas = st.text_area("Notas Internas", value=str(row.get('notas_internas', '')))

        # --- BOTÃO DE SALVAMENTO ---
        if st.button("💾 ATUALIZAR E SALVAR PROJETO", type="primary", use_container_width=True):
            dados = {
                "status_projeto": novo_status,
                "data_conclusao": nova_data.strftime('%Y-%m-%d'),
                "detalhamento_itens": df_edit_itens.to_dict('records'),
                "custo_adicional_materiais": custo_materiais_real,
                "custo_terceirizados": custo_terceiros,
                "custo_comissao": comissao,
                "custo_impostos": valor_imposto,
                "custo_cartao": custo_cartao,
                "valor_venda_total": venda_final,
                "lucro_estimado": lucro_liquido,
                "notas_internas": notas
            }
            try:
                supabase.table('servicos_andamento').update(dados).eq('id', row['id']).execute()
                st.success("✅ Projeto atualizado! O lucro foi recalculado com as taxas.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

    # Gatilho de seleção
    if sel_orc.selection.rows:
        exibir_detalhes_avancados(df_orcamentos.iloc[sel_orc.selection.rows[0]], supabase)
