import streamlit as st
import pandas as pd
import utils

def renderizar():
    st.markdown("## 📊 Controle Financeiro e DRE")
    
    # Filtro de Ano
    ano_selecionado = st.selectbox("Selecione o Ano para visualização e edição:", 
                                   [utils.ano_atual - 1, utils.ano_atual, utils.ano_atual + 1], 
                                   index=1)
    
    tabs = st.tabs(["💰 Receitas", "🛒 Custos Variáveis", "🏢 Custos Fixos", "🏛️ Impostos", "📈 DRE (Resumo)"])
    
    # Estruturas de Contas Padrão
    contas_receitas = ["Venda de Equipamentos", "Serviços e Instalação", "Manutenção", "Outras Receitas"]
    contas_cv = ["Custo de Equipamentos (CMV)", "Comissões", "Fretes e Logística", "Instaladores/Terceirizados"]
    contas_cf = ["Aluguel", "Água / Energia", "Internet / Telefone", "Sistemas / TI", "Marketing / Anúncios", "Salários / Encargos", "Pró-labore", "Contabilidade"]
    contas_imp = ["DAS (Simples Nacional)", "Outros Impostos"]

    def criar_aba_financeira(nome_tabela, contas_padrao, titulo):
        st.subheader(titulo)
        # Carrega os dados da tabela correspondente no banco
        df = utils.load_year_data(nome_tabela, contas_padrao, ano_selecionado)
        
        # Configuração visual das colunas
        cfg = {"MESES": st.column_config.TextColumn("Categoria / Conta", width="medium")}
        for m in utils.meses_pt:
            cfg[m] = st.column_config.NumberColumn(m, format="R$ %,.2f")
            
        # Data Editor para o usuário preencher a planilha
        df_edit = st.data_editor(df, column_config=cfg, num_rows="dynamic", use_container_width=True, key=f"ed_{nome_tabela}")
        
        # Botão de Salvar
        if st.button(f"💾 Salvar {titulo}", type="primary", key=f"btn_{nome_tabela}"):
            utils.save_to_supabase(nome_tabela, df_edit, ano_selecionado)
            st.success(f"{titulo} salvos com sucesso no banco de dados!")
        
        return df_edit

    # Renderizando as Abas
    with tabs[0]:
        df_rec = criar_aba_financeira('financeiro_receitas', contas_receitas, "Entradas e Faturamento (Receitas)")
    with tabs[1]:
        df_cv = criar_aba_financeira('financeiro_custos_variaveis', contas_cv, "Custos Variáveis (Diretos)")
    with tabs[2]:
        df_cf = criar_aba_financeira('financeiro_custos_fixos', contas_cf, "Custos Fixos (Operacionais)")
    with tabs[3]:
        df_imp = criar_aba_financeira('financeiro_impostos', contas_imp, "Impostos e Taxas")
        
    with tabs[4]:
        st.subheader(f"📈 Demonstração do Resultado do Exercício (DRE) - {ano_selecionado}")
        
        # Matemática Financeira Automática
        totais_rec = df_rec[utils.meses_pt].sum()
        totais_cv = df_cv[utils.meses_pt].sum()
        totais_cf = df_cf[utils.meses_pt].sum()
        totais_imp = df_imp[utils.meses_pt].sum()
        
        receita_liquida = totais_rec - totais_imp
        lucro_bruto = receita_liquida - totais_cv
        lucro_liquido = lucro_bruto - totais_cf
        
        # Montagem da Tabela Resumo do DRE
        dre_data = {
            "DRE": [
                "1. Receita Bruta Total",
                "2. (-) Impostos e Taxas",
                "3. (=) Receita Líquida",
                "4. (-) Custos Variáveis (CMV)",
                "5. (=) Lucro Bruto",
                "6. (-) Custos Fixos (Operacionais)",
                "7. (=) Resultado Líquido (Lucro/Prejuízo)",
                "Margem de Lucro Líquida (%)"
            ]
        }
        
        for m in utils.meses_pt:
            r_bruta = totais_rec[m]
            imp = totais_imp[m]
            r_liq = receita_liquida[m]
            cv = totais_cv[m]
            l_bruto = lucro_bruto[m]
            cf = totais_cf[m]
            l_liq = lucro_liquido[m]
            margem = (l_liq / r_bruta * 100) if r_bruta > 0 else 0.0
            
            dre_data[m] = [r_bruta, imp, r_liq, cv, l_bruto, cf, l_liq, margem]
            
        df_dre = pd.DataFrame(dre_data)
        
        # Configuração visual do DRE
        cfg_dre = {"DRE": st.column_config.TextColumn("Métricas Financeiras", width="medium")}
        for m in utils.meses_pt:
            cfg_dre[m] = st.column_config.NumberColumn(m, format="%,.2f")
        
        st.dataframe(df_dre, column_config=cfg_dre, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Cards de Totais Anuais
        total_ano_receita = totais_rec.sum()
        total_ano_lucro = lucro_liquido.sum()
        margem_ano = (total_ano_lucro / total_ano_receita * 100) if total_ano_receita > 0 else 0.0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Faturamento Anual Bruto", utils.to_br_currency(total_ano_receita))
        c2.metric("Lucro Líquido Anual", utils.to_br_currency(total_ano_lucro))
        c3.metric("Margem Média Anual", f"{margem_ano:.2f}%")
        
        # Botão de Exportação para o Excel
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📥 Exportar DRE para Excel", use_container_width=True, type="secondary"):
            excel_data = utils.to_excel(df_dre)
            st.download_button(
                label="Clique aqui para Baixar a Planilha", 
                data=excel_data, 
                file_name=f"DRE_Ecoclim_{ano_selecionado}.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
