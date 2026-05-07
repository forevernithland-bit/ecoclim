import streamlit as st
import pandas as pd
import utils

def renderizar():
    st.markdown("## 📊 Controle Financeiro")
    
    # Seleção do Ano
    ano_selecionado = st.selectbox(
        "Selecione o Ano de Referência:", 
        [utils.ano_atual - 1, utils.ano_atual, utils.ano_atual + 1], 
        index=1
    )
    
    # Contas padrão (você pode editar ou adicionar novas diretamente na tabela depois)
    contas_padrao = [
        "Receitas com Vendas", 
        "Receitas com Serviços", 
        "Custos de Equipamentos", 
        "Custos com Instaladores", 
        "Impostos e Taxas", 
        "Despesas Operacionais", 
        "Outros"
    ]
    
    st.info("Preencha os valores financeiros correspondentes a cada mês. Você pode adicionar ou renomear categorias clicando diretamente na tabela.")
    
    # Carrega os dados do banco usando a nossa função do utils
    df = utils.load_year_data('controle_financeiro', contas_padrao, ano_selecionado)
    
    # Configuração visual das colunas
    cfg = {"MESES": st.column_config.TextColumn("Categorias / Contas", width="medium")}
    for m in utils.meses_pt:
        cfg[m] = st.column_config.NumberColumn(m, format="R$ %,.2f")
        
    # Tabela editável
    df_edit = st.data_editor(df, column_config=cfg, num_rows="dynamic", use_container_width=True, key="tabela_financeiro")
    
    # Botão de salvar (usa a nossa função do Supabase)
    if st.button("💾 Gravar Alterações Financeiras", type="primary", use_container_width=True):
        utils.save_to_supabase('controle_financeiro', df_edit, ano_selecionado)
        st.success(f"Dados financeiros do ano {ano_selecionado} salvos com sucesso no banco de dados!")
        
    st.markdown("---")
    
    # Exportação para Excel
    st.subheader("📥 Exportar Dados")
    excel_data = utils.to_excel(df_edit)
    st.download_button(
        label="Exportar Planilha para Excel", 
        data=excel_data, 
        file_name=f"Controle_Financeiro_Ecoclim_{ano_selecionado}.xlsx", 
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
