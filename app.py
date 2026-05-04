import streamlit as st
import pandas as pd
import numpy as np

# Configuração da Página
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

# --- CSS PARA SOBREPOSIÇÃO E ALINHAMENTO PERFEITO ---
st.markdown("""
    <style>
    /* Empurra o dashboard para o topo e zera espaços entre componentes */
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    div[data-testid="stVerticalBlock"] > div { padding-bottom: 0px !important; margin-bottom: 0px !important; }
    div.st-emotion-cache-1wivap2 { gap: 0rem !important; }
    
    /* Centraliza o texto nas células */
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { text-align: center !important; }
    
    /* 
       A MÁGICA: Puxar as tabelas para cima para esconder os cabeçalhos.
       Cada tabela fica "embaixo" da tabela anterior (Z-index menor), 
       e o margin-top de -36px esconde o cabeçalho perfeitamente!
    */
    /* Tabela 1: Patrimônio (Topo - Fica por cima de todas) */
    div[data-testid="stDataEditor"]:nth-of-type(1) { z-index: 10; position: relative; }
    
    /* Tabela 2: Resultados Patrimônio (Fica embaixo da Tabela 1) */
    div[data-testid="stDataFrame"]:nth-of-type(1) { z-index: 9; position: relative; margin-top: -36px !important; }
    
    /* Tabela 3: Entradas Editáveis (Fica embaixo da Tabela 2) */
    div[data-testid="stDataEditor"]:nth-of-type(2) { z-index: 8; position: relative; margin-top: -36px !important; }
    
    /* Tabela 4: Salário Mês (Fica embaixo da Tabela 3) */
    div[data-testid="stDataFrame"]:nth-of-type(2) { z-index: 7; position: relative; margin-top: -36px !important; }
    
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

# Inicializando Dados (Agora com a coluna "CONTAS" fixa para garantir alinhamento)
if 'df_patrimonio' not in st.session_state or 'CONTAS' not in st.session_state.df_patrimonio.columns:
    df_p = pd.DataFrame(0.0, index=range(len(linhas_patrimonio)), columns=meses)
    df_p.insert(0, 'CONTAS', linhas_patrimonio)
    st.session_state.df_patrimonio = df_p

if 'df_entradas' not in st.session_state or 'CONTAS' not in st.session_state.df_entradas.columns:
    df_e = pd.DataFrame(0.0, index=range(len(linhas_entradas)), columns=meses)
    df_e.insert(0, 'CONTAS', linhas_entradas)
    st.session_state.df_entradas = df_e

# CONFIGURAÇÃO DE COLUNA (Isto é o que trava a largura para todas as tabelas ficarem idênticas)
base_config = {
    "CONTAS": st.column_config.TextColumn("CONTAS", width=280, disabled=True)
}
for mes in meses:
    base_config[mes] = st.column_config.NumberColumn(mes, format="%.2f")

# ==========================================
# 🏠 DASHBOARD CONSOLIDADO
# ==========================================
if menu == "🏠 Dashboard Consolidado":
    
    # ------------------------------------------------------------------
    # TABELA 1: PATRIMÔNIO EDITÁVEL (A única que mostra o Cabeçalho)
    # ------------------------------------------------------------------
    df_editado_patr = st.data_editor(st.session_state.df_patrimonio, hide_index=True, column_config=base_config, use_container_width=True, height=283)
    st.session_state.df_patrimonio = df_editado_patr
    
    # Cálculos Patrimônio
    df_num_patr = df_editado_patr.set_index('CONTAS')
    patrimonio_liquido = df_num_patr.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum(axis=0)
    patrimonio_total = patrimonio_liquido + df_num_patr.loc['IMÓVEIS'] + df_num_patr.loc['VEÍCULOS']
    var_rs = patrimonio_total.diff().fillna(0)
    var_pct = (patrimonio_total.pct_change().fillna(0) * 100).round(2)

    df_resultados_patr = pd.DataFrame({'CONTAS': ['PATRIMONIO LÍQUIDO', 'PATRIMONIO TOTAL', 'Var $ patrimonio', '% var patrimônio']})
    for mes in meses:
        df_resultados_patr[mes] = [patrimonio_liquido[mes], patrimonio_total[mes], var_rs[mes], var_pct[mes]]

    # Cores (O mesmo padrão da sua imagem)
    def style_patrimonio(row):
        if row['CONTAS'] == 'PATRIMONIO LÍQUIDO':
            return ['background-color: #FFF2CC; font-weight: bold; color: black; border: 1px solid black;'] * len(row)
        elif row['CONTAS'] == 'PATRIMONIO TOTAL':
            return ['background-color: #FF9900; font-weight: bold; color: black; border: 1px solid black;'] * len(row)
        else:
            return ['background-color: #FFF2CC; color: black;'] * len(row)

    styled_df_patr = df_resultados_patr.style\
        .apply(style_patrimonio, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses}, subset=pd.IndexSlice[[0, 1, 2], meses])\
        .format(formatter={col: '{:.2f}%' for col in meses}, subset=pd.IndexSlice[[3], meses])

    # ------------------------------------------------------------------
    # TABELA 2: RESULTADOS PATRIMÔNIO (Cabeçalho escondido pela Tabela 1)
    # ------------------------------------------------------------------
    st.dataframe(styled_df_patr, hide_index=True, column_config=base_config, use_container_width=True, height=180)

    # ------------------------------------------------------------------
    # TABELA 3: ENTRADAS EDITÁVEL (Cabeçalho escondido pela Tabela 2)
    # ------------------------------------------------------------------
    df_editado_entradas = st.data_editor(st.session_state.df_entradas, hide_index=True, column_config=base_config, use_container_width=True, height=180)
    st.session_state.df_entradas = df_editado_entradas
    
    # Cálculos Entradas
    df_num_ent = df_editado_entradas.set_index('CONTAS')
    salario_mes = df_num_ent.sum(axis=0)

    df_resultado_entradas = pd.DataFrame({'CONTAS': ['SALÁRIO MÊS:']})
    for mes in meses:
        df_resultado_entradas[mes] = [salario_mes[mes]]

    # Cor Azul da Entradas
    def style_entradas(row):
        return ['background-color: #9BC2E6; font-weight: bold; color: black; border: 1px solid black;'] * len(row)

    styled_df_ent = df_resultado_entradas.style\
        .apply(style_entradas, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in meses})
        
    # ------------------------------------------------------------------
    # TABELA 4: RESULTADO ENTRADAS (Cabeçalho escondido pela Tabela 3)
    # ------------------------------------------------------------------
    st.dataframe(styled_df_ent, hide_index=True, column_config=base_config, use_container_width=True, height=73)

elif menu == "❄️ Ecoclim":
    st.title("Controle Ecoclim")
elif menu == "🏠 Airbnb":
    st.title("Controle Airbnb")
elif menu == "📄 Documentos":
    st.title("Gerador de Orçamentos e Contratos")
