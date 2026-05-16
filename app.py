import streamlit as st
import os

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA (Deve ser a primeira instrução Streamlit)
# =============================================================================
st.set_page_config(
    page_title="Ecoclim ERP", 
    layout="wide", 
    page_icon="🌤️"
)

# =============================================================================
# 2. IMPORTAÇÃO DOS MÓDULOS
# =============================================================================
import utils
import tela_orcamentos
import tela_servicos
import tela_financeira
import tela_configuracoes
import tela_airnb
import tela_documentos

# =============================================================================
# 3. CONEXÃO COM O BANCO DE DADOS
# =============================================================================
try:
    if "supabase" not in st.session_state:
        st.session_state.supabase = utils.init_connection()
except Exception as e:
    st.error(f"Erro crítico na conexão com o banco de dados: {e}")

# =============================================================================
# 4. ESTILIZAÇÃO CSS GLOBAL (DESIGN CLEAN & MODERNO)
# =============================================================================
st.markdown("""
    <style>
    /* Fundo branco total na barra lateral para sumir com o fundo da logo */
    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e6ecf5;
    }
    
    /* Ajuste de padding e largura total */
    .block-container { 
        padding-top: 2rem !important; 
        padding-left: 2rem !important; 
        padding-right: 2rem !important; 
        max-width: 100% !important; 
    }
    
    /* Remove espaços entre tabelas no módulo financeiro */
    div.container-tabelas div[data-testid="stVerticalBlock"] { 
        gap: 0px !important; 
        padding: 0px !important; 
    }
    
    /* Tabelas e Editores de dados ocupando 100% e centralizados */
    .stDataFrame table, .stDataEditor table { 
        table-layout: fixed !important; 
        width: 100% !important; 
    }
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { 
        text-align: center !important; 
        font-size: 0.85rem !important; 
    }
    
    /* Esconde o cabeçalho das tabelas de resumo no financeiro */
    .financeiro div[data-testid="stDataFrame"] thead { 
        display: none !important; 
    }
    
    /* Títulos padronizados em azul corporativo clean */
    h1, h2, h3 {
        color: #004488 !important;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }

    /* Customização dos botões/cards da página inicial */
    div[data-testid="stColumn"] button {
        background-color: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 25px 15px !important;
        font-size: 1.05rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03) !important;
        transition: all 0.2s ease-in-out !important;
        min-height: 110px !important;
    }

    /* Efeito de hover moderno nos cards */
    div[data-testid="stColumn"] button:hover {
        border-color: #004488 !important;
        color: #004488 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 10px 15px -3px rgba(0, 68, 136, 0.1), 0 4px 6px -2px rgba(0, 68, 136, 0.05) !important;
    }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 5. LÓGICA DE ACESSO (LOGIN)
# =============================================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Controladores de estado de navegação para evitar conflitos de cache
if "menu_option" not in st.session_state:
    st.session_state.menu_option = "Página Inicial"

if not st.session_state.authenticated:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=200)
        
        st.subheader("Login Ecoclim ERP")
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        
        if st.button("Acessar Sistema", use_container_width=True):
            if usuario == "breno.lima" and senha == "Ecoclim2026@":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos. Tente novamente.")
else:
    # =============================================================================
    # 6. MENU DE NAVEGAÇÃO LATERAL (BARRA BRANCA LIMPA)
    # =============================================================================
    with st.sidebar:
        st.markdown("<br>", unsafe_allow_html=True)
        if os.path.exists("logo.png"):
            st.image("logo.png", use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        lista_paginas = [
            "Página Inicial", 
            "Controle Financeiro", 
            "Orçamentos", 
            "Serviços em Andamento", 
            "Documentos",
            "AirBnb e Locações",
            "Configurações"
        ]
        
        # Sincroniza o rádio com o estado global da sessão
        index_atual = lista_paginas.index(st.session_state.menu_option)
        
        menu = st.radio(
            "Navegação", 
            lista_paginas,
            index=index_atual,
            key="radio_navegacao"
        )
        
        # Se mudou pelo clique direto no rádio da barra lateral
        if menu != st.session_state.menu_option:
            st.session_state.menu_option = menu
            st.rerun()
        
        st.write("---")
        if st.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.menu_option = "Página Inicial"
            st.rerun()

    # =============================================================================
    # 7. ROTEADOR DE TELAS (CHAMA OS MÓDULOS)
    # =============================================================================
    
    if st.session_state.menu_option == "Página Inicial":
        st.markdown("<h1>🏠 Centro de Gestão</h1>", unsafe_allow_html=True)
        st.markdown(f"<h5>Olá, Breno. Bem-vindo de volta à central de inteligência da Ecoclim.</h5>", unsafe_allow_html=True)
        st.caption(f"📅 Calendário Operacional: {utils.hoje.strftime('%d/%m/%Y')}")
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        # Grid moderno de ações rápidas
        c1, c2 = st.columns(2)
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        c3, c4 = st.columns(2)
        
        with c1:
            if st.button("📊\tControle Financeiro", use_container_width=True, key=f"btn_nav_financeiro"):
                st.session_state.menu_option = "Controle Financeiro"
                st.rerun()
        with c2:
            if st.button("📝\tFazer Novo Orçamento", use_container_width=True, key=f"btn_nav_orcamentos"):
                st.session_state.menu_option = "Orçamentos"
                st.rerun()
        with c3:
            if st.button("🛠️\tServiços em Andamento", use_container_width=True, key=f"btn_nav_servicos"):
                st.session_state.menu_option = "Serviços em Andamento"
                st.rerun()
        with c4:
            if st.button("📁\tCentral de Documentos", use_container_width=True, key=f"btn_nav_documentos"):
                st.session_state.menu_option = "Documentos"
                st.rerun()

    elif st.session_state.menu_option == "Controle Financeiro":
        tela_financeira.renderizar()

    elif st.session_state.menu_option == "Orçamentos":
        tela_orcamentos.renderizar()

    elif st.session_state.menu_option == "Serviços em Andamento":
        tela_servicos.renderizar()

    elif st.session_state.menu_option == "Documentos":
        tela_documentos.renderizar()

    elif st.session_state.menu_option == "AirBnb e Locações":
        tela_airnb.renderizar()

    elif st.session_state.menu_option == "Configurações":
        tela_configuracoes.renderizar()
