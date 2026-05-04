import streamlit as st
import pandas as pd
import numpy as np

# Configuração da Página
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

# --- CSS DEFINITIVO PARA CLONE DO EXCEL ---
st.markdown("""
    <style>
    /* Empurra para o topo */
    .block-container { padding-top: 1rem !important; }
    
    /* Centraliza e força larguras iguais para as colunas em TODAS as tabelas */
    .stDataFrame table, .stDataEditor table { 
        table-layout: fixed !important; 
        width: 100% !important; 
    }
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { 
        text-align: center !important; 
        overflow: hidden; 
        text-overflow: ellipsis; 
        white-space: nowrap;
    }
    
    /* Reduz espaço vertical do Streamlit a ZERO */
    div[data-testid="stVerticalBlock"] > div {
        padding-bottom: 0px !important;
        margin-bottom: 0px !important;
    }
    div.st-emotion-cache-1wivap2 { gap: 0rem !important; }
    
    /* 
       OCULTAR CABEÇALHOS (MESES):
       - Esconde da tabela de resultados do patrimônio
       - Esconde da tabela de edição de entradas
       - Esconde da tabela de resultados das entradas
    */
    div[data-testid="stDataFrame"] table thead,
    div[data-testid="stDataEditor"]:nth-of-type(2) table thead {
        display: none !important;
    }
    
    /* Cola as tabelas puxando as margens para negativo */
    div[data-testid="stDataEditor"] { margin-bottom: -16px !important; z-index: 2; position: relative; }
    div[data-testid="stDataFrame"] { margin-top: 0px !important; margin-bottom: -16px !important; z-index: 1; }
    
    .main { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

# --- MENU LATERAL ---
with st.sidebar:
    st.title("📈 Consorbens")
    menu = st.radio("Navegação", ["🏠 Dashboard Consolidado", "❄️ Ecoclim", "🏠 Airbnb", "📄 Documentos"])
    if st.button("🔄 Limpar Memória do App"):
        st.session_state.clear()
        st.rerun()

meses = ['dez/25', 'JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
linhas_patrimonio = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
linhas_entradas = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

# Memória
if 'df_patrimonio' not in st.session_state or list(st.session_state.df_patrimonio.index) != linhas_patrimonio or list(st.session_state.df_patrimonio.columns) != meses:
    st.session_state.df_patrimonio = pd.DataFrame(0.0, index=linhas_patrimonio, columns=meses)
if 'df_entradas' not in st.session_state or list(st.session_state.df_entradas.index) != linhas_entradas or list(st.session_state.df_entradas.columns) != meses:
    st.session_state.df_entradas = pd.DataFrame(0.0, index=linhas_entradas, columns=meses)

if menu == "🏠 Dashboard Consolidado":
    
    # ------------------------------------------------------------------
    # TABELA 1: PATRIMÔNIO (EDITÁVEL) - A ÚNICA COM MESES NO TOPO
    # ------------------------------------------------------------------
    df_editado_patr = st.data_editor(st.session_state.df_patrimonio, use_container_width=True, height=280)
    st.session_state.df_patrimonio = df_editado_patr
    
    # Cálculos Patrimônio
    patrimonio_liquido = df_editado_patr.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum(axis=0)
    patrimonio_total = patrimonio_liquido + df_editado_patr.loc['IMÓVEIS'] + df_editado_patr.loc['VEÍCULOS']
    var_rs = patrimonio_total.diff().fillna(0)
    var_pct = (patrimonio_total.pct_change().fillna(0) * 100).round(2)

    df_resultados_patr = pd.DataFrame({
        'PATRIMONIO LÍQUIDO': patrimonio_liquido,
        'PATRIMONIO TOTAL': patrimonio_total,
        'Var $ patrimonio': var_rs,
        '% var patrimônio': var_pct
    }).T

    # Cores
    def style_patrimonio(row):
        if row.name == 'PATRIMONIO LÍQUIDO':
            return ['background-color: #FFF2CC; font-weight: bold; color: black; border: 1px solid black;'] * len(row)
        elif row.name == 'PATRIMONIO TOTAL':
            return ['background-color: #FF9900; font-weight: bold; color: black; border: 1px solid black;'] * len(row)
        else:
            return ['background-color: #FFF2CC; color: black;'] * len(row)

    styled_df_patr = df_resultados_patr.style\
        .apply(style_patrimonio, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in df_resultados_patr.columns}, subset=pd.IndexSlice[['PATRIMONIO LÍQUIDO', 'PATRIMONIO TOTAL', 'Var $ patrimonio'], :])\
        .format(formatter={col: '{:.2f}%' for col in df_resultados_patr.columns}, subset=pd.IndexSlice[['% var patrimônio'], :])

    # ------------------------------------------------------------------
    # TABELA 2: RESULTADOS PATRIMÔNIO (COLADA, SEM MESES)
    # ------------------------------------------------------------------
    st.dataframe(styled_df_patr, use_container_width=True, height=180)

    # ------------------------------------------------------------------
    # TABELA 3: ENTRADAS (EDITÁVEL, COLADA, SEM MESES)
    # ------------------------------------------------------------------
    df_editado_entradas = st.data_editor(st.session_state.df_entradas, use_container_width=True, height=180, key="entradas_editor")
    st.session_state.df_entradas = df_editado_entradas
    
    # Cálculos Entradas
    salario_mes = df_editado_entradas.sum(axis=0)
    df_resultado_entradas = pd.DataFrame({'SALÁRIO MÊS:': salario_mes}).T

    # Cores Entradas
    def style_entradas(row):
        return ['background-color: #9BC2E6; font-weight: bold; color: black; border: 1px solid black;'] * len(row)

    styled_df_ent = df_resultado_entradas.style\
        .apply(style_entradas, axis=1)\
        .format('R$ {:,.2f}')
        
    # ------------------------------------------------------------------
    # TABELA 4: RESULTADO ENTRADAS (COLADA, SEM MESES)
    # ------------------------------------------------------------------
    st.dataframe(styled_df_ent, use_container_width=True, height=70)

elif menu == "❄️ Ecoclim":
    st.title("Controle Ecoclim")
elif menu == "🏠 Airbnb":
    st.title("Controle Airbnb")
elif menu == "📄 Documentos":
    st.title("Gerador de Orçamentos e Contratos")
