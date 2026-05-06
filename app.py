import streamlit as st
import os

# 1. Configuração da Página sempre deve ser a primeira linha do app.py
st.set_page_config(page_title="Ecoclim ERP", layout="wide", page_icon="🌤️")

# Importa as outras telas (elas precisam estar criadas na mesma pasta)
# Como ainda vamos criá-las, deixei comentado para não dar erro se você testar agora.
# import tela_orcamentos
# import tela_configuracoes
# import tela_financeira

# Carrega o cérebro
import utils

# Conecta ao banco
try:
    supabase = utils.init_connection()
    st.session_state.supabase = supabase # Salva a conexão para os outros arquivos usarem
except Exception as e:
    st.error(f"Erro na conexão Supabase: {e}")

# CSS Global
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; padding-left: 1rem !important; padding-right: 1rem !important; max-width: 100% !important; }
    div.container-tabelas div[data-testid="stVerticalBlock"] { gap: 0px !important; padding: 0px !important; }
    [data-testid="stTable"] { overflow: hidden !important; }
    .stDataFrame table, .stDataEditor table { table-layout: fixed !important; width: 100% !important; }
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { text-align: center !important; font-size: 0.85rem !important; }
    .financeiro div[data-testid="stDataFrame"] thead { display: none !important; }
    </style>
""", unsafe_allow_html=True)

# Lógica de Roteamento (Menu)
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "pagina_atual" not in st.session_state: st.session_state.pagina_atual = "Página Inicial"

if not st.session_state.authenticated:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,1.5,1])
    with col2:
        if os.path.exists("logo.png"): st.image("logo.png", width=200)
        st.subheader("Login Ecoclim ERP")
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.button("Acessar Sistema", use_container_width=True):
            if u == "breno.lima" and p == "Ecoclim2026@":
                st.session_state.authenticated = True; st.rerun()
            else: st.error("Credenciais inválidas.")
else:
    with st.sidebar:
        if os.path.exists("logo.png"): st.image("logo.png")
        st.write("### Menu Principal")
        menu = st.radio("Navegação", ["Página Inicial", "Orçamentos", "Controle Financeiro", "Configurações"], label_visibility="collapsed")
        st.session_state.pagina_atual = menu
        st.write("---")
        if st.button("🚪 Sair"): st.session_state.authenticated = False; st.rerun()

    # Roteador de Telas
    if st.session_state.pagina_atual == "Página Inicial":
        st.markdown("## 🏠 Página Inicial")
        st.write(f"Bem-vindo, Breno. Hoje é {utils.hoje.strftime('%d/%m/%Y')}")
        st.write("---")
        c1, c2 = st.columns(2); c3, c4 = st.columns(2)
        if c1.button("📝\n\nFazer Orçamento", use_container_width=True): st.session_state.pagina_atual = "Orçamentos"; st.rerun()
        if c2.button("📊\n\nControle Financeiro", use_container_width=True): st.session_state.pagina_atual = "Controle Financeiro"; st.rerun()
        if c3.button("⚙️\n\nConfigurações", use_container_width=True): st.session_state.pagina_atual = "Configurações"; st.rerun()
        if c4.button("🚪\n\nSair do Sistema", use_container_width=True): st.session_state.authenticated = False; st.rerun()
        
    elif st.session_state.pagina_atual == "Orçamentos":
        st.info("Módulo de Orçamentos será importado aqui.")
        # tela_orcamentos.renderizar() 
        
    elif st.session_state.pagina_atual == "Controle Financeiro":
        st.info("Módulo Financeiro será importado aqui.")
        # tela_financeira.renderizar()
        
    elif st.session_state.pagina_atual == "Configurações":
        st.info("Módulo de Configurações será importado aqui.")
        # tela_configuracoes.renderizar()
