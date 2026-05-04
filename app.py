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

meses = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']

# --- FUNÇÃO PARA INICIALIZAR DADOS (Sessão do Streamlit) ---
# Isso cria uma "planilha" em memória para você editar na tela
if 'df_patrimonio' not in st.session_state:
    dados_iniciais = {
        'Capital Giro ML': [0]*12, 'Capital Giro Consorbens': [0]*12,
        'CONTA INTER PF': [0]*12, 'CONTA XP PF': [0]*12, 'FGTS': [0]*12,
        'Imóveis': [0]*12, 'VEÍCULOS': [0]*12
    }
    st.session_state.df_patrimonio = pd.DataFrame(dados_iniciais, index=meses)

if 'df_entradas' not in st.session_state:
    entradas_iniciais = {'Ecoclim': [0]*12, 'Airbnb': [0]*12, 'Consorbens': [0]*12, 'Maggi': [0]*12}
    st.session_state.df_entradas = pd.DataFrame(entradas_iniciais, index=meses)

# ==========================================
# 🏠 DASHBOARD CONSOLIDADO
# ==========================================
if menu == "🏠 Dashboard Consolidado":
    st.title("📊 Painel de Controle de Patrimônio")
    
    st.subheader("1. Controle de Saldos e Patrimônio")
    st.caption("Edite os valores abaixo. Os totais serão calculados automaticamente.")
    
    # Editor Interativo na tela
    df_editado_patr = st.data_editor(st.session_state.df_patrimonio, use_container_width=True)
    st.session_state.df_patrimonio = df_editado_patr # Salva as edições
    
    # --- CÁLCULOS AUTOMÁTICOS DO PATRIMÔNIO ---
    df_calc = df_editado_patr.copy()
    
    # Patrimônio Líquido = Soma de tudo, exceto Imóveis e Veículos
    df_calc['Patrimônio Líquido'] = df_calc[['Capital Giro ML', 'Capital Giro Consorbens', 'CONTA INTER PF', 'CONTA XP PF', 'FGTS']].sum(axis=1)
    
    # Patrimônio Total = Líquido + Imóveis + Veículos
    df_calc['Patrimônio Total'] = df_calc['Patrimônio Líquido'] + df_calc['Imóveis'] + df_calc['VEÍCULOS']
    
    # Variações em relação ao mês anterior (diff e pct_change)
    df_calc['Var $ Patrimônio'] = df_calc['Patrimônio Total'].diff().fillna(0)
    df_calc['Var % Patrimônio'] = (df_calc['Patrimônio Total'].pct_change().fillna(0) * 100).round(2)
    
    # Exibir a tabela com os resultados calculados
    st.markdown("### 📈 Resultados do Patrimônio")
    st.dataframe(df_calc[['Patrimônio Líquido', 'Patrimônio Total', 'Var $ Patrimônio', 'Var % Patrimônio']].style.format({
        'Patrimônio Líquido': 'R$ {:,.2f}', 'Patrimônio Total': 'R$ {:,.2f}', 
        'Var $ Patrimônio': 'R$ {:,.2f}', 'Var % Patrimônio': '{:.2f}%'
    }), use_container_width=True)

    st.divider()

    # ==========================================
    # 2. ENTRADAS MENSAIS (FLUXO DE CAIXA)
    # ==========================================
    st.subheader("2. Entradas Mensais (Renda)")
    
    df_editado_entradas = st.data_editor(st.session_state.df_entradas, use_container_width=True)
    st.session_state.df_entradas = df_editado_entradas
    
    df_entradas_calc = df_editado_entradas.copy()
    df_entradas_calc['Salário Mês Total'] = df_entradas_calc.sum(axis=1)
    
    st.markdown("### 💵 Total de Entradas")
    st.dataframe(df_entradas_calc[['Salário Mês Total']].style.format('R$ {:,.2f}'), use_container_width=True)

    st.divider()

    # ==========================================
    # 3. INDICADORES ANUAIS E MÉDIAS
    # ==========================================
    st.subheader("3. Indicadores de Performance")
    
    # Para as médias, vamos considerar apenas os meses onde houve variação de patrimônio maior que zero para não sujar a média anual com meses vazios
    meses_ativos = df_calc[df_calc['Patrimônio Total'] > 0].shape[0]
    meses_ativos = meses_ativos if meses_ativos > 0 else 1 # evitar divisão por zero

    media_aplicacao = df_calc['Var $ Patrimônio'].sum() / meses_ativos
    soma_salarial = df_entradas_calc['Salário Mês Total'].sum()
    media_salarial = soma_salarial / meses_ativos
    
    # Avanço Anual: Último mês ativo menos o primeiro (ou de dezembro do ano passado, como você pediu, que ajustaremos quando conectarmos banco de dados)
    patrimonio_atual = df_calc['Patrimônio Total'].replace(0, np.nan).dropna().iloc[-1] if not df_calc['Patrimônio Total'].replace(0, np.nan).dropna().empty else 0
    patrimonio_inicial = df_calc['Patrimônio Total'].iloc[0]
    avanco_patrimonial = patrimonio_atual - patrimonio_inicial

    col1, col2, col3 = st.columns(3)
    col1.metric("Média Aplicação Mês (Var $)", f"R$ {media_aplicacao:,.2f}")
    col2.metric("Média Salarial Anual Líq.", f"R$ {media_salarial:,.2f}")
    col3.metric("Soma Salarial Anual", f"R$ {soma_salarial:,.2f}")
    
    col4, col5 = st.columns(2)
    col4.metric("Avanço Anual Patrimonial", f"R$ {avanco_patrimonial:,.2f}")
    col5.metric("Avanço Anual Aplicação (Liquidez)", "Em construção...")

    st.divider()

    # ==========================================
    # 4. CONTROLE DE RENDIMENTOS (INTER E XP)
    # ==========================================
    st.subheader("4. Rendimento de Investimentos (Inter e XP)")
    st.write("Em breve: Aqui faremos a lógica de travar o valor do último dia do mês e comparar com o atual, gerando % e R$ de rendimento!")

# Outras páginas apenas marcadas para expansão futura
elif menu == "❄️ Ecoclim":
    st.title("Controle Ecoclim")
elif menu == "🏠 Airbnb":
    st.title("Controle Airbnb")
elif menu == "📄 Documentos":
    st.title("Gerador de Orçamentos e Contratos")
