import streamlit as st
import pandas as pd
import numpy as np

# Configuração da Página
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

# --- CSS PARA CENTRALIZAR E ESTILIZAR ---
st.markdown("""
    <style>
    .stDataFrame td, .stDataFrame th { text-align: center !important; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
    .main { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

# --- MENU LATERAL ---
with st.sidebar:
    st.title("📈 Consorbens")
    menu = st.radio("Navegação", ["🏠 Dashboard Consolidado", "❄️ Ecoclim", "🏠 Airbnb", "📄 Documentos"])
    
    # Botão de emergência para limpar o cache caso dê erro de novo
    if st.button("🔄 Limpar Memória do App"):
        st.session_state.clear()
        st.rerun()

meses = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']

# Nomes EXATAMENTE iguais à sua planilha da imagem
linhas_patrimonio = ['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS', 'IMÓVEIS', 'VEÍCULOS']
linhas_entradas = ['ECOCLIM', 'AIRNB', 'CONS INVESTIMENTOS', 'MAGGI CONSORCIOS']

# Sistema de Segurança: Se os dados antigos estiverem na memória, ele reseta
if 'df_patrimonio' not in st.session_state or list(st.session_state.df_patrimonio.index) != linhas_patrimonio:
    st.session_state.df_patrimonio = pd.DataFrame(0.0, index=linhas_patrimonio, columns=meses)
if 'df_entradas' not in st.session_state or list(st.session_state.df_entradas.index) != linhas_entradas:
    st.session_state.df_entradas = pd.DataFrame(0.0, index=linhas_entradas, columns=meses)

# ==========================================
# 🏠 DASHBOARD CONSOLIDADO
# ==========================================
if menu == "🏠 Dashboard Consolidado":
    st.title("📊 Painel de Controle de Patrimônio")
    
    # ---------------------------------------------------
    st.subheader("1. Edição de Saldos")
    
    df_editado_patr = st.data_editor(st.session_state.df_patrimonio, use_container_width=True)
    st.session_state.df_patrimonio = df_editado_patr
    
    # Cálculos com os nomes atualizados
    patrimonio_liquido = df_editado_patr.loc[['CAPITAL DE GIRO (ML)', 'CAPITAL DE GIRO CONSOR (ITAU)', 'CONTA INTER', 'INVESTIMENTO XP', 'FGTS']].sum(axis=0)
    patrimonio_total = patrimonio_liquido + df_editado_patr.loc['IMÓVEIS'] + df_editado_patr.loc['VEÍCULOS']
    var_rs = patrimonio_total.diff().fillna(0)
    var_pct = (patrimonio_total.pct_change().fillna(0) * 100).round(2)

    df_resultados_patr = pd.DataFrame({
        'PATRIMONIO LIQUIDO': patrimonio_liquido,
        'PATRIMONIO TOTAL': patrimonio_total,
        'Var $ patrimonio': var_rs,
        '% var patrimônio': var_pct
    }).T

    # ---------------------------------------------------
    st.markdown("### 📈 Visualização do Patrimônio")
    
    def style_patrimonio(row):
        styles = [''] * len(row)
        if row.name == 'PATRIMONIO LIQUIDO':
            styles = ['background-color: #E6F2FF; font-weight: bold; color: black'] * len(row)
        elif row.name == 'PATRIMONIO TOTAL':
            styles = ['background-color: #FFB347; font-weight: bold; color: black'] * len(row)
        return styles

    styled_df_patr = df_resultados_patr.style\
        .apply(style_patrimonio, axis=1)\
        .format(formatter={col: 'R$ {:,.2f}' for col in df_resultados_patr.columns}, subset=pd.IndexSlice[['PATRIMONIO LIQUIDO', 'PATRIMONIO TOTAL', 'Var $ patrimonio'], :])\
        .format(formatter={col: '{:.2f}%' for col in df_resultados_patr.columns}, subset=pd.IndexSlice[['% var patrimônio'], :])

    st.dataframe(styled_df_patr, use_container_width=True)
    st.divider()

    # ---------------------------------------------------
    st.subheader("2. Entradas Mensais (Renda)")
    
    df_editado_entradas = st.data_editor(st.session_state.df_entradas, use_container_width=True)
    st.session_state.df_entradas = df_editado_entradas
    
    salario_mes = df_editado_entradas.sum(axis=0)
    df_resultado_entradas = pd.DataFrame({'SALARIO MES': salario_mes}).T

    def style_entradas(row):
        return ['background-color: #99CCFF; font-weight: bold; color: black'] * len(row) if row.name == 'SALARIO MES' else [''] * len(row)

    styled_df_ent = df_resultado_entradas.style\
        .apply(style_entradas, axis=1)\
        .format('R$ {:,.2f}')
        
    st.dataframe(styled_df_ent, use_container_width=True)
    st.divider()

    # ---------------------------------------------------
    st.subheader("3. Indicadores e Médias")
    meses_ativos = patrimonio_total[patrimonio_total > 0].shape[0]
    meses_ativos = meses_ativos if meses_ativos > 0 else 1 

    media_aplicacao = var_rs.sum() / meses_ativos
    soma_salarial = salario_mes.sum()
    media_salarial = soma_salarial / meses_ativos
    
    patr_atual = patrimonio_total.replace(0, np.nan).dropna().iloc[-1] if not patrimonio_total.replace(0, np.nan).dropna().empty else 0
    patr_inicial = patrimonio_total.iloc[0]
    avanco_patrimonial = patr_atual - patr_inicial
    
    col1, col2, col3 = st.columns(3)
    col1.metric("MÉDIA APLICAÇÃO MÊS", f"R$ {media_aplicacao:,.2f}")
    col2.metric("MÉDIA SALÁRIAL LÍQUIDA", f"R$ {media_salarial:,.2f}")
    col3.metric("SOMA SALÁRIAL ANUAL", f"R$ {soma_salarial:,.2f}")
    
    col4, col5 = st.columns(2)
    col4.metric("AVANÇO ANUAL DE APLICAÇÃO", "Em breve...")
    col5.metric("AVANÇO ANUAL PATRIMONIAL", f"R$ {avanco_patrimonial:,.2f}")

elif menu == "❄️ Ecoclim":
    st.title("Controle Ecoclim")
elif menu == "🏠 Airbnb":
    st.title("Controle Airbnb")
elif menu == "📄 Documentos":
    st.title("Gerador de Orçamentos e Contratos")
