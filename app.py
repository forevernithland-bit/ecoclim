import streamlit as st
import pandas as pd
import numpy as np

# Configuração da Página
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

# --- CSS AGRESSIVO PARA MODO "EXCEL" ---
st.markdown("""
    <style>
    /* 1. Empurra tudo pro topo da tela */
    .block-container { padding-top: 1rem !important; }
    
    /* 2. Centraliza textos nas tabelas */
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { 
        text-align: center !important; 
    }
    
    /* 3. A MÁGICA DE COLAR AS TABELAS: Remove todos os espaços e gaps verticais do Streamlit */
    div[data-testid="stVerticalBlock"] > div {
        padding-bottom: 0px !important;
        margin-bottom: 0px !important;
    }
    div.st-emotion-cache-1wivap2 { gap: 0rem !important; } /* Força gap zero no container principal */
    
    /* 4. Esconde o cabeçalho (meses) das tabelas de resultado para parecer continuação da de cima */
    div[data-testid="stDataFrame"] table thead {
        display: none !important;
    }
    
    /* 5. Tira as margens específicas dos componentes de tabela */
    div[data-testid="stDataEditor"] {
        margin-bottom: -15px !important; 
        z-index: 2;
        position: relative;
    }
    div[data-testid="stDataFrame"] {
        margin-top: 0px !important;
        margin-bottom: -15px !important;
        z-index: 1;
    }
    
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

# --- DADOS ---
# Adicionado dez/25 conforme sua imagem
meses = ['dez/25', 'JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']

linhas_patrimonio = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
linhas_entradas = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

# Sistema de Segurança para a memória
if 'df_patrimonio' not in st.session_state or list(st.session_state.df_patrimonio.index) != linhas_patrimonio or list(st.session_state.df_patrimonio.columns) != meses:
    st.session_state.df_patrimonio = pd.DataFrame(0.0, index=linhas_patrimonio, columns=meses)
if 'df_entradas' not in st.session_state or list(st.session_state.df_entradas.index) != linhas_entradas or list(st.session_state.df_entradas.columns) != meses:
    st.session_state.df_entradas = pd.DataFrame(0.0, index=linhas_entradas, columns=meses)

# ==========================================
# 🏠 DASHBOARD CONSOLIDADO
# ==========================================
if menu == "🏠 Dashboard Consolidado":
    
    # ==========================================
    # BLOCO 1: PATRIMÔNIO (Tudo Colado)
    # ==========================================
    
    # 1. Tabela Editável (Com os meses no topo)
    df_editado_patr = st.data_editor(st.session_state.df_patrimonio, use_container_width=True, height=280)
    st.session_state.df_patrimonio = df_editado_patr
    
    # Cálculos
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

    # Estilo igual da foto
    def style_patrimonio(row):
        if row.name == 'PATRIMONIO LÍQUIDO':
            return ['background-color: #FFF2CC; font-weight: bold; color: black; border: 1px solid black;'] * len(row) # Amarelo claro
        elif row.name == 'PATRIMONIO TOTAL':
            return ['background-color: #FF9900; font-weight: bold; color: black; border: 1px solid black;'] * len(row) # Laranja forte
        else:
            return ['background-color: #FFF2CC; color: black;'] * len(row) # Fundo do Var

    styled_df_patr = df_resultados_patr.style\
        .apply(style_patrimonio, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in df_resultados_patr.columns}, subset=pd.IndexSlice[['PATRIMONIO LÍQUIDO', 'PATRIMONIO TOTAL', 'Var $ patrimonio'], :])\
        .format(formatter={col: '{:.2f}%' for col in df_resultados_patr.columns}, subset=pd.IndexSlice[['% var patrimônio'], :])

    # 2. Tabela de Resultados do Patrimônio (Colada na de cima, sem cabeçalho)
    st.dataframe(styled_df_patr, use_container_width=True, height=180)

    # ==========================================
    # BLOCO 2: ENTRADAS (Coladas no bloco de cima)
    # ==========================================
    
    # 3. Tabela de Entradas Editável (Sem cabeçalho)
    st.markdown('<style>div[data-testid="stDataEditor"]:nth-of-type(2) table thead {display: none !important;}</style>', unsafe_allow_html=True)
    df_editado_entradas = st.data_editor(st.session_state.df_entradas, use_container_width=True, height=180)
    st.session_state.df_entradas = df_editado_entradas
    
    # Cálculo
    salario_mes = df_editado_entradas.sum(axis=0)
    df_resultado_entradas = pd.DataFrame({'SALÁRIO MÊS:': salario_mes}).T

    # Estilo
    def style_entradas(row):
        return ['background-color: #9BC2E6; font-weight: bold; color: black; border: 1px solid black;'] * len(row)

    styled_df_ent = df_resultado_entradas.style\
        .apply(style_entradas, axis=1)\
        .format('R$ {:,.2f}')
        
    # 4. Resultado Final (Colado na de entradas)
    st.dataframe(styled_df_ent, use_container_width=True, height=70)

elif menu == "❄️ Ecoclim":
    st.title("Controle Ecoclim")
elif menu == "🏠 Airbnb":
    st.title("Controle Airbnb")
elif menu == "📄 Documentos":
    st.title("Gerador de Orçamentos e Contratos")
    
