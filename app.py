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
import tela_documentos  # <--- NOVO MÓDULO ADICIONADO AQUI

# =============================================================================
# 3. CONEXÃO COM O BANCO DE DADOS
# =============================================================================
try:
    # Inicializa a conexão via utils e armazena na sessão para uso global
    if "supabase" not in st.session_state:
        st.session_state.supabase = utils.init_connection()
except Exception as e:
    st.error(f"Erro crítico na conexão com o banco de dados: {e}")

# =============================================================================
# 4. ESTILIZAÇÃO CSS GLOBAL
# =============================================================================
st.markdown("""
    <style>
    /* Ajuste de padding e largura total */
    .block-container { 
        padding-top: 1.5rem !important; 
        padding-left: 1rem !important; 
        padding-right: 1rem !important; 
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
    
    /* Esconde o cabeçalho das tabelas de resumo no financeiro para visual limpo */
    .financeiro div[data-testid="stDataFrame"] thead { 
        display: none !important; 
    }
    
    /* Estilo para títulos de seções */
    h2, h3 {
        color: #004488;
    }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 5. LÓGICA DE ACESSO (LOGIN)
# =============================================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "pagina_atual" not in st.session_state:
    st.session_state.pagina_atual = "Página Inicial"

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
            # Verificação de credenciais
            if usuario == "breno.lima" and senha == "Ecoclim2026@":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos. Tente novamente.")
else:
    # =============================================================================
    # 6. MENU DE NAVEGAÇÃO LATERAL
    # =============================================================================
    with st.sidebar:
        if os.path.exists("logo.png"):
            st.image("logo.png")
        
        st.write("### Menu Principal")
        
        # Menu reordenado conforme solicitado com Documentos incluso
        menu = st.radio(
            "Navegação", 
            [
                "Página Inicial", 
                "Controle Financeiro", 
                "Orçamentos", 
                "Serviços em Andamento", 
                "Documentos",             # <--- NOVO MENU ADICIONADO AQUI
                "AirBnb e Locações",
                "Configurações"
            ],
            label_visibility="collapsed"
        )
        st.session_state.pagina_atual = menu
        
        st.write("---")
        if st.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    # =============================================================================
    # 7. ROTEADOR DE TELAS (CHAMA OS MÓDULOS)
    # =============================================================================
    
    if st.session_state.pagina_atual == "Página Inicial":
        st.markdown("## 🏠 Página Inicial")
        st.write(f"Olá, Breno. Bem-vindo ao centro de gestão da Ecoclim.")
        st.write(f"Hoje é dia {utils.hoje.strftime('%d/%m/%Y')}")
        st.write("---")
        
        # Atalhos rápidos em colunas
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        
        with c1:
            if st.button("📊\n\nControle Financeiro", use_container_width=True):
                st.session_state.pagina_atual = "Controle Financeiro"
                st.rerun()
        with c2:
            if st.button("📝\n\nFazer Novo Orçamento", use_container_width=True):
                st.session_state.pagina_atual = "Orçamentos"
                st.rerun()
        with c3:
            if st.button("🛠️\n\nServiços em Andamento", use_container_width=True):
                st.session_state.pagina_atual = "Serviços em Andamento"
                st.rerun()
        with c4:
            if st.button("🏡\n\nAirBnb e Locações", use_container_width=True):
                st.session_state.pagina_atual = "AirBnb e Locações"
                st.rerun()

    elif st.session_state.pagina_atual == "Controle Financeiro":
        tela_financeira.renderizar()

    elif st.session_state.pagina_atual == "Orçamentos":
        tela_orcamentos.renderizar()

    elif st.session_state.pagina_atual == "Serviços em Andamento":
        tela_servicos.renderizar()

    elif st.session_state.pagina_atual == "Documentos":  # <--- ROTA ADICIONADA AQUI
        tela_documentos.renderizar()

    elif st.session_state.pagina_atual == "AirBnb e Locações":
        tela_airnb.renderizar()

    elif st.session_state.pagina_atual == "Configurações":
        tela_configuracoes.renderizar()
