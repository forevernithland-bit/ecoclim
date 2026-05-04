import streamlit as st
import pandas as pd
import numpy as np

# Configuração da Página
st.set_page_config(page_title="Consorbens Wealth", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .main { background-color: #f8f9fa; }
    h2 { color: #2c3e50; }
    </style>
    """, unsafe_allow_html=True)

# --- MENU LATERAL ---
with st.sidebar:
    st.title("📈 Consorbens")
    menu = st.radio("Navegação", ["🏠 Dashboard Consolidado", "❄️ Ecoclim", "🏠 Airbnb", "📄 Documentos"])

# MESES NAS COLUNAS
meses = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']

# CONTROLES NAS LINHAS
linhas_patrimonio = [
    'Capital de Giro Ml', 'Capital de Giro Consorbens', 'CONTA INTER PF', 
    'CONTA XP PF', 'FGTS', 'Imóveis', 'VEÍCULOS'
]

linhas_entradas = ['Ecoclim', 'Airnb', 'Cons. Investimentos', 'Maggi']

# --- FUNÇÃO PARA INICIALIZAR DADOS INVERTIDOS ---
if 'df_patrimonio' not in st.session_state:
    # Cria o DataFrame com 0.0, usando contas como linhas (index) e meses como colunas
    st.session_state.df_patrimonio = pd.DataFrame(0.0, index=linhas_patrimonio, columns=meses)

if 'df_entradas' not in st.session_state:
    st.session_state.df_entradas = pd.DataFrame(0.0, index=linhas_entradas, columns=meses)

# ==========================================
# 🏠 DASHBOARD CONSOLIDADO
# ==========================================
if menu == "🏠 Dashboard Consolidado":
    st.title("📊 Painel de Controle de Patrimônio")
    
    st.subheader("1. Controle de Saldos e Patrimônio")
    st.caption("Preencha os saldos nas linhas. Os cálculos serão feitos automaticamente para cada mês.")
    
    # Editor Interativo na tela
    df_editado_patr = st.data_editor(st.session_state.df_patrimonio, use_container_width=True)
    st.session_state.df_patrimonio = df_editado_patr # Salva as edições
    
    # --- CÁLCULOS AUTOMÁTICOS DO PATRIMÔNIO ---
    # Patrimônio Líquido (soma das contas selecionadas mês a mês)
    patrimonio_liquido = df_editado_patr.loc[['Capital de Giro Ml', 'Capital de Giro Consorbens', 'CONTA INTER PF', 'CONTA XP PF', 'FGTS']].sum(axis=0)
    
    # Patrimônio Total (Líquido + Imóveis + Veículos)
    patrimonio_total = patrimonio_liquido + df_editado_patr.loc['Imóveis'] + df_editado_patr.loc['VEÍCULOS']
    
    # Variações em relação ao mês anterior
    var_rs = patrimonio_total.diff().fillna(0)
    var_pct = (patrimonio_total.pct_change().fillna(0) * 100).round(2)
    
    # Montando a tabela de Resultados
    df_resultados_patr = pd.DataFrame({
        'Patrimônio Liquido': patrimonio_liquido,
        'Patrimônio Total': patrimonio_total,
        'Var $ patrimônio': var_rs,
        'Var % patrimônio': var_pct
    }).T # O .T inverte novamente para mostrar os resultados com os meses nas colunas
    
    st.markdown("### 📈 Resultados do Patrimônio")
    st.dataframe(df_resultados_patr, use_container_width=True)

    st.divider()

    # ==========================================
    # 2. ENTRADAS MENSAIS (FLUXO DE CAIXA)
    # ==========================================
    st.subheader("2. Entradas Mensais (Renda)")
    
    df_editado_entradas = st.data_editor(st.session_state.df_entradas, use_container_width=True)
    st.session_state.df_entradas = df_editado_entradas
    
    # Cálculo do Salário Mês
    salario_mes = df_editado_entradas.sum(axis=0)
    
    df_resultado_entradas = pd.DataFrame({
        'Salário mês': salario_mes
    }).T
    
    st.markdown("### 💵 Total de Entradas")
    st.dataframe(df_resultado_entradas, use_container_width=True)

    st.divider()

    # ==========================================
    # 3. INDICADORES ANUAIS E MÉDIAS
    # ==========================================
    st.subheader("3. Indicadores de Performance")
    
    # Identificar quantos meses têm movimento para fazer as médias corretas
    meses_ativos = patrimonio_total[patrimonio_total > 0].shape[0]
    meses_ativos = meses_ativos if meses_ativos > 0 else 1 # evitar divisão por zero

    media_aplicacao = var_rs.sum() / meses_ativos
    soma_salarial = salario_mes.sum()
    media_salarial = soma_salarial / meses_ativos
    
    # Avanço Anual Patrimonial (Último mês preenchido - Janeiro)
    patr_atual = patrimonio_total.replace(0, np.nan).dropna().iloc[-1] if not patrimonio_total.replace(0, np.nan).dropna().empty else 0
    patr_inicial = patrimonio_total.iloc[0]
    avanco_patrimonial = patr_atual - patr_inicial
    
    # Avanço Anual de Aplicação (Líquido)
    liq_atual = patrimonio_liquido.replace(0, np.nan).dropna().iloc[-1] if not patrimonio_liquido.replace(0, np.nan).dropna().empty else 0
    liq_inicial = patrimonio_liquido.iloc[0]
    avanco_aplicacao = liq_atual - liq_inicial

    col1, col2, col3 = st.columns(3)
    col1.metric("MÉDIA APLICAÇÃO MÊS", f"R$ {media_aplicacao:,.2f}")
    col2.metric("MÉDIA SALÁRIAL ANUAL LÍQ.", f"R$ {media_salarial:,.2f}")
    col3.metric("SOMA SALÁRIAL ANUAL", f"R$ {soma_salarial:,.2f}")
    
    col4, col5 = st.columns(2)
    col4.metric("AVANÇO ANUAL DE APLICAÇÃO", f"R$ {avanco_aplicacao:,.2f}")
    col5.metric("AVANÇO ANUAL PATRIMONIAL", f"R$ {avanco_patrimonial:,.2f}")

    st.divider()

    # ==========================================
    # 4. CONTROLE DE RENDIMENTOS (INTER E XP)
    # ==========================================
    st.subheader("4. Rendimento de Investimentos (Inter e XP)")
    st.write("Em breve: Aqui vamos configurar a lógica para travar o saldo no último dia do mês e calcular a rentabilidade (R$ e %)!")

elif menu == "❄️ Ecoclim":
    st.title("Controle Ecoclim")
elif menu == "🏠 Airbnb":
    st.title("Controle Airbnb")
elif menu == "📄 Documentos":
    st.title("Gerador de Orçamentos e Contratos")
