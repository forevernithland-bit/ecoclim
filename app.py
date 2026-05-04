import streamlit as st
import pandas as pd
import numpy as np

# Configuração da Página
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

# --- CSS PARA ALINHAMENTO E COLAGEM PERFEITA ---
st.markdown("""
    <style>
    /* Zera os espaços do contêiner principal para o Dashboard ocupar bem a tela */
    .block-container { padding-top: 1rem !important; }
    div.st-emotion-cache-1wivap2 { gap: 0rem !important; }
    
    /* Centraliza os textos */
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { 
        text-align: center !important; 
    }
    
    /* 
       MÁGICA DE COLAGEM:
       A tabela de cima (DataEditor) fica no topo (z-index: 10).
       A tabela de baixo (DataFrame) sobe 38px, escondendo seu cabeçalho embaixo da tabela de cima,
       e zerando completamente o espaçamento!
    */
    /* Bloco Patrimônio */
    div[data-testid="stDataEditor"]:nth-of-type(1) { z-index: 10; position: relative; }
    div[data-testid="stDataFrame"]:nth-of-type(1) { 
        z-index: 1; 
        margin-top: -38px !important; 
        position: relative; 
        margin-bottom: 30px !important; /* Espaço antes da próxima planilha */
    }
    
    /* Bloco Entradas */
    div[data-testid="stDataEditor"]:nth-of-type(2) { z-index: 10; position: relative; }
    div[data-testid="stDataFrame"]:nth-of-type(2) { 
        z-index: 1; 
        margin-top: -38px !important; 
        position: relative; 
    }
    
    .main { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

# --- MENU LATERAL ---
with st.sidebar:
    st.title("📈 Consorbens")
    menu = st.radio("Navegação", ["🏠 Dashboard Consolidado", "❄️ Ecoclim", "🏠 Airbnb", "📄 Documentos"])
    st.write("---")
    if st.button("🔄 Limpar Memória do App"):
        st.session_state.clear()
        st.rerun()

meses = ['dez/25', 'JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
linhas_patrimonio = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
linhas_entradas = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

# Inicializando Banco de Memória (Preparado para o Supabase no futuro)
if 'df_patrimonio' not in st.session_state or 'CONTAS' not in st.session_state.df_patrimonio.columns:
    df_p = pd.DataFrame(0.0, index=range(len(linhas_patrimonio)), columns=meses)
    df_p.insert(0, 'CONTAS', linhas_patrimonio)
    st.session_state.df_patrimonio = df_p

if 'df_entradas' not in st.session_state or 'CONTAS' not in st.session_state.df_entradas.columns:
    df_e = pd.DataFrame(0.0, index=range(len(linhas_entradas)), columns=meses)
    df_e.insert(0, 'CONTAS', linhas_entradas)
    st.session_state.df_entradas = df_e

# =====================================================================
# CONFIGURAÇÃO DE LARGURA DE COLUNAS (O SEGREDO DO ALINHAMENTO)
# Essa regra é aplicada em ambas as tabelas para garantir larguras idênticas
# =====================================================================
col_config = {
    "CONTAS": st.column_config.TextColumn("CONTAS", width="large", disabled=True)
}
for mes in meses:
    col_config[mes] = st.column_config.NumberColumn(mes, width="small")

# ==========================================
# 🏠 DASHBOARD CONSOLIDADO
# ==========================================
if menu == "🏠 Dashboard Consolidado":
    
    # ------------------------------------------------------------------
    # PLANILHA 1: PATRIMÔNIO (Editável - COM MESES)
    # ------------------------------------------------------------------
    df_editado_patr = st.data_editor(st.session_state.df_patrimonio, hide_index=True, column_config=col_config, use_container_width=True, height=283)
    st.session_state.df_patrimonio = df_editado_patr
    
    # Cálculos
    df_num_patr = df_editado_patr.set_index('CONTAS')
    patrimonio_liquido = df_num_patr.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum(axis=0)
    patrimonio_total = patrimonio_liquido + df_num_patr.loc['IMÓVEIS'] + df_num_patr.loc['VEÍCULOS']
    var_rs = patrimonio_total.diff().fillna(0)
    var_pct = (patrimonio_total.pct_change().fillna(0) * 100).round(2)

    df_resultados_patr = pd.DataFrame({'CONTAS': ['PATRIMONIO LÍQUIDO', 'PATRIMONIO TOTAL', 'Var $ patrimonio', '% var patrimônio']})
    for mes in meses:
        df_resultados_patr[mes] = [patrimonio_liquido[mes], patrimonio_total[mes], var_rs[mes], var_pct[mes]]

    # Cores
    def style_patrimonio(row):
        if row['CONTAS'] == 'PATRIMONIO LÍQUIDO':
            return ['background-color: #FFF2CC; font-weight: bold; color: black; border: 1px solid black;'] * len(row)
        elif row['CONTAS'] == 'PATRIMONIO TOTAL':
            return ['background-color: #FF9900; font-weight: bold; color: black; border: 1px solid black;'] * len(row)
        elif row['CONTAS'] == 'Var $ patrimonio':
            return ['background-color: #FFF2CC; color: black;'] * len(row)
        else:
            return ['background-color: #FFFFFF; color: black;'] * len(row)

    styled_df_patr = df_resultados_patr.style\
        .apply(style_patrimonio, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses}, subset=pd.IndexSlice[[0, 1, 2], meses])\
        .format(formatter={col: '{:.2f}%' for col in meses}, subset=pd.IndexSlice[[3], meses])

    # ------------------------------------------------------------------
    # TABELA RESULTADO PATRIMÔNIO (Cabeçalho ocultado e colado na de cima)
    # ------------------------------------------------------------------
    st.dataframe(styled_df_patr, hide_index=True, column_config=col_config, use_container_width=True, height=180)

    # ------------------------------------------------------------------
    # PLANILHA 2: ENTRADAS (Editável - COM MESES)
    # ------------------------------------------------------------------
    df_editado_entradas = st.data_editor(st.session_state.df_entradas, hide_index=True, column_config=col_config, use_container_width=True, height=180)
    st.session_state.df_entradas = df_editado_entradas
    
    # Cálculo
    df_num_ent = df_editado_entradas.set_index('CONTAS')
    salario_mes = df_num_ent.sum(axis=0)

    df_resultado_entradas = pd.DataFrame({'CONTAS': ['SALÁRIO MÊS:']})
    for mes in meses:
        df_resultado_entradas[mes] = [salario_mes[mes]]

    # Cor Azul
    def style_entradas(row):
        return ['background-color: #9BC2E6; font-weight: bold; color: black; border: 1px solid black;'] * len(row)

    styled_df_ent = df_resultado_entradas.style\
        .apply(style_entradas, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses})
        
    # ------------------------------------------------------------------
    # TABELA RESULTADO ENTRADAS (Cabeçalho ocultado e colado na de cima)
    # ------------------------------------------------------------------
    st.dataframe(styled_df_ent, hide_index=True, column_config=col_config, use_container_width=True, height=73)

elif menu == "❄️ Ecoclim":
    st.title("Controle Ecoclim")
elif menu == "🏠 Airbnb":
    st.title("Controle Airbnb")
elif menu == "📄 Documentos":
    st.title("Gerador de Orçamentos e Contratos")
