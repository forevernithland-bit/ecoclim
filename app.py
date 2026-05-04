import streamlit as st
import pandas as pd

# Configuração da Página
st.set_page_config(page_title="Ecoclim & Consorbens", layout="wide", page_icon="❄️")

# Estilo CSS para melhorar o visual
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    .stMetric { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🏦 Gestão Consorbens")
    st.subheader("Menu de Navegação")
    menu = st.radio(
        "Selecione uma área:",
        ["🏠 Dashboard Geral", "❄️ Ecoclim - Gestão", "📄 Gerador de Docs", "🏠 Airbnb", "💰 Lançamentos Faturamento"]
    )
    st.markdown("---")
    st.write("v1.0 - 2026")

# --- PÁGINAS ---

if menu == "🏠 Dashboard Geral":
    st.title("📊 Visão Geral dos Negócios")
    
    # KPIs de exemplo (depois puxaremos do Supabase/Planilha)
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Lucro Ecoclim (Mês)", "R$ 12.500")
    with col2: st.metric("Consorbens", "R$ 8.200")
    with col3: st.metric("Airbnb", "R$ 2.450")
    with col4: st.metric("Total Acumulado", "R$ 23.150")

    st.subheader("📈 Evolução Financeira")
    # Aqui entrará o gráfico consolidado
    st.info("O gráfico será gerado assim que integrarmos os dados da planilha 1_Financeiro_2026.xlsx.")

elif menu == "❄️ Ecoclim - Gestão":
    st.title("❄️ Controle de Serviços - Ecoclim")
    
    tab1, tab2 = st.tabs(["Serviços Ativos", "Novo Lançamento"])
    
    with tab1:
        st.write("Lista de serviços em andamento...")
        # Exemplo de tabela
        dados_teste = pd.DataFrame({
            'Cliente': ['Edmilson', 'Erick'],
            'Valor': [72076.38, 13200.00],
            'Status': ['Pago Sinal', 'Concluído']
        })
        st.table(dados_teste)

    with tab2:
        with st.form("form_servico"):
            st.text_input("Nome do Cliente")
            st.number_input("Valor da Venda", min_value=0.0)
            st.selectbox("Instalador", ["Valdimar", "Outro"])
            st.form_submit_button("Salvar Serviço")

elif menu == "📄 Gerador de Docs":
    st.title("📄 Gerador de Orçamentos e Contratos")
    doc_tipo = st.selectbox("Documento:", ["Orçamento Profissional", "Contrato de Prestação"])
    if st.button("Gerar PDF"):
        st.success("Função de PDF sendo configurada...")

elif menu == "🏠 Airbnb":
    st.title("🏠 Gestão Airbnb")
    st.write("Controle de datas e taxas de cartão.")

elif menu == "💰 Lançamentos Faturamento":
    st.title("💰 Outras Fontes de Renda")
    st.write("Lançamento manual: Consorbens, CLT e Investimentos.")
