import streamlit as st
import os
import datetime
import pandas as pd

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
# 3. FUNÇÕES AUXILIARES PARA LEMBRETES NA PÁGINA INICIAL
# =============================================================================
def mover_arquivo_drive_app(file_id, folder_path_list):
    """Move um arquivo no Google Drive para uma nova pasta"""
    try:
        service = utils.get_drive_service()
        file = service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents', []))
        new_folder_id = utils.get_or_create_nested_folder(service, utils.MAIN_DRIVE_FOLDER_ID, folder_path_list)
        service.files().update(
            fileId=file_id, addParents=new_folder_id, removeParents=previous_parents, fields='id, parents'
        ).execute()
        return True
    except: return False

def add_months_app(dt, months):
    """Soma meses na data considerando a virada de anos"""
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, [31, 29 if year % 4 == 0 and not year % 100 == 0 or year % 400 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return dt.replace(year=year, month=month, day=day)

# =============================================================================
# 4. CONEXÃO COM O BANCO DE DADOS
# =============================================================================
try:
    if "supabase" not in st.session_state:
        st.session_state.supabase = utils.init_connection()
except Exception as e:
    st.error(f"Erro crítico na conexão com o banco de dados: {e}")

# =============================================================================
# 5. ESTILIZAÇÃO CSS GLOBAL (DESIGN CLEAN & MODERNO)
# =============================================================================
st.markdown("""
    <style>
    /* Fundo branco total na barra lateral */
    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e6ecf5;
    }
    
    /* Ajuste de padding total */
    .block-container { 
        padding-top: 3.5rem !important; 
        padding-left: 2rem !important; 
        padding-right: 2rem !important; 
        max-width: 100% !important; 
    }
    
    div.container-tabelas div[data-testid="stVerticalBlock"] { 
        gap: 0px !important; 
        padding: 0px !important; 
    }
    
    .stDataFrame table, .stDataEditor table { 
        table-layout: fixed !important; 
        width: 100% !important; 
    }
    
    .stDataFrame td, .stDataFrame th, .stDataEditor td, .stDataEditor th { 
        text-align: center !important; 
        font-size: 0.85rem !important; 
    }
    
    .financeiro div[data-testid="stDataFrame"] thead { 
        display: none !important; 
    }
    
    h1, h2, h3, h4 {
        color: #004488 !important;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }

    /* Alinhamento horizontal absoluto para as colunas */
    div[data-testid="stHorizontalBlock"] {
        align-items: center !important;
    }

    /* ALINHAMENTO MILIMÉTRICO DOS LEMBRETES */
    div[data-testid="stHorizontalBlock"]:has(.card-lembrete) {
        align-items: center !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.card-lembrete) p {
        margin-bottom: 0px !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.card-lembrete) div.stButton {
        padding: 0px !important;
        margin: 0px !important;
    }

    /* BOTÕES PEQUENOS: Usados nos Lembretes (Type Primary) */
    div.stButton > button[kind="primary"] {
        background-color: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #d1d5db !important;
        border-radius: 4px !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        min-height: 38px !important;
        height: 38px !important;
        padding: 0 10px !important;
        margin: 0 !important;
        width: 100% !important;
    }
    div.stButton > button[kind="primary"]:hover {
        border-color: #004488 !important;
        color: #004488 !important;
        background-color: #f8fafc !important;
    }

    /* BOTÕES GRANDES: Usados nos Cards de Navegação (Type Secondary) */
    div.stButton > button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 15px 10px !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        min-height: 80px !important;
        margin-bottom: 5px !important;
        width: 100% !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        border-color: #004488 !important;
        color: #004488 !important;
        transform: translateY(-2px) !important;
    }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 6. LÓGICA DE ACESSO (LOGIN)
# =============================================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "menu_option" not in st.session_state:
    st.session_state.menu_option = "Página Inicial"

if not st.session_state.authenticated:
    
    # CSS Injetado APENAS para a tela de login (Mega compacto para caber na tela)
    st.markdown("""
        <style>
        /* Esconde a barra lateral E o espaço em branco do topo (header) */
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stHeader"] { display: none !important; }
        
        /* Esmaga as margens e paddings nativos do Streamlit */
        .block-container { 
            padding-top: 2rem !important; 
            padding-bottom: 0rem !important;
        }
        
        /* Reduz o espaço entre os itens dentro do form */
        div[data-testid="stVerticalBlock"] {
            gap: 0.5rem !important;
        }
        
        /* Botão de Login Estilizado */
        .login-btn-container div.stButton > button {
            background-color: #004488 !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 8px !important;
            font-size: 1rem !important;
            font-weight: 600 !important;
            min-height: 40px !important;
            height: 40px !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
            transition: all 0.3s ease !important;
            margin-top: 10px !important;
        }
        .login-btn-container div.stButton > button:hover {
            background-color: #003366 !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 12px rgba(0,0,0,0.15) !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Deixei as colunas mais estreitas [1, 1, 1] para o card ficar mais compacto e elegante
    col1, col2, col3 = st.columns([1, 1, 1]) 
    
    with col2:
        with st.container(border=True):
            # Centraliza a Logo
            c_img1, c_img2, c_img3 = st.columns([1, 1.2, 1])
            with c_img2:
                if os.path.exists("logo.png"):
                    st.image("logo.png", use_container_width=True)
            
            # Centraliza o Título e tira as margens dele
            st.markdown("<h4 style='text-align: center; color: #004488; font-weight: 600; margin-top: 0px; margin-bottom: 10px;'>Login Ecoclim ERP</h4>", unsafe_allow_html=True)
            
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            
            # Centraliza o Botão (já colado nos inputs)
            st.markdown('<div class="login-btn-container">', unsafe_allow_html=True)
            c_btn1, c_btn2, c_btn3 = st.columns([1, 1.5, 1])
            with c_btn2:
                if st.button("Acessar Sistema", use_container_width=True):
                    if usuario == "breno.lima" and senha == "Ecoclim2026@":
                        st.session_state.authenticated = True
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos.")
            st.markdown('</div>', unsafe_allow_html=True)

else:
    # =============================================================================
    # 7. MENU DE NAVEGAÇÃO LATERAL (BARRA BRANCA LIMPA)
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
        
        index_atual = lista_paginas.index(st.session_state.menu_option)
        menu = st.radio("Navegação", lista_paginas, index=index_atual)
        
        if menu != st.session_state.menu_option:
            st.session_state.menu_option = menu
            st.rerun()
        
        st.write("---")
        # Definido como primary para pegar o CSS de botão pequeno de 38px
        if st.button("🚪 Sair do Sistema", type="primary", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.menu_option = "Página Inicial"
            st.rerun()

    # =============================================================================
    # 8. ROTEADOR DE TELAS (CHAMA OS MÓDULOS)
    # =============================================================================
    if st.session_state.menu_option == "Página Inicial":
        
        st.caption(f"📅 Calendário Operacional: {utils.hoje.strftime('%d/%m/%Y')}")

        # NOVO: Executa sincronização do Calendar ao entrar na Home para rodar as regras de datas
        if 'calendar_sync_inicial' not in st.session_state:
            utils.sincronizar_boletos_com_calendar()
            st.session_state.calendar_sync_inicial = True

        # =========================================================================
        # NOVO: DASHBOARD DE ALERTAS (EFEITO TABELA COLADA)
        # =========================================================================
        st.markdown("<h4 style='font-weight: 600; margin-bottom: 10px;'>🔔 Lembretes de Pagamento</h4>", unsafe_allow_html=True)
        
        try:
            res_bol = st.session_state.supabase.table('boletos_fornecedores').select('*').eq('status', 'Pendente').order('vencimento').execute()
            
            lembretes_ativos = []
            if res_bol.data:
                hoje_dt = utils.hoje
                for b in res_bol.data:
                    venc_dt = datetime.datetime.strptime(b['vencimento'], "%Y-%m-%d").date()
                    diff_days = (venc_dt - hoje_dt).days
                    
                    if diff_days <= 5:
                        lembretes_ativos.append((b, venc_dt, diff_days))
            
            if lembretes_ativos:
                for idx, (b, venc_dt, diff) in enumerate(lembretes_ativos):
                    
                    if diff < 0:
                        cor_card = "#ffe6e6"; icone = "🚨"; status_txt = "ATRASADO"
                    elif diff == 0:
                        cor_card = "#fff2cc"; icone = "⚠️"; status_txt = "VENCE HOJE"
                    else:
                        cor_card = "#e6ffe6"; icone = "📅"; status_txt = f"EM {diff} DIAS"
                    
                    # MAGIA CSS: Puxa a linha pra cima anulando o gap do Streamlit, grudando feito tabela
                    if idx > 0:
                        st.markdown("<div style='margin-top: -16px;'></div>", unsafe_allow_html=True)
                        
                    col_info, col_btn_doc, col_btn_pagar = st.columns([7.5, 1.2, 1.2])
                    
                    with col_info:
                        # Altura travada em 38px, alinhamento flex perfeito e classe injetada para quebrar a margem do Streamlit
                        st.markdown(f"""
                            <div class="card-lembrete" style="background-color: {cor_card}; border: 1px solid #d1d5db; border-radius: 4px; padding: 0 15px; display: flex; align-items: center; justify-content: space-between; height: 38px; margin: 0px;">
                                <div style="display: flex; align-items: center; gap: 10px; overflow: hidden;">
                                    <span style="font-size: 14px;">{icone}</span>
                                    <span style="font-size: 14px; font-weight: 600; color: #111; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{b['cliente']}</span>
                                </div>
                                <div style="display: flex; align-items: center; gap: 15px;">
                                    <span style="font-size: 12px; color: #555; white-space: nowrap;">Venc: {venc_dt.strftime('%d/%m/%Y')} ({status_txt})</span>
                                    <span style="font-size: 14px; font-weight: 700; color: #004488; white-space: nowrap;">{utils.to_br_currency(b['valor'])}</span>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                    
                    with col_btn_doc:
                        if st.button("📂 Boletos", type="primary", key=f"ir_{b['id']}", use_container_width=True):
                            st.session_state.menu_option = "Documentos"
                            st.rerun()
                            
                    with col_btn_pagar:
                        if st.button("✅ Pagar", type="primary", key=f"pg_{b['id']}", use_container_width=True):
                            with st.spinner("Atualizando..."):
                                id_db = b['id']
                                id_drive = b.get('link_drive_id')
                                
                                # Move arquivo físico no Drive se houver
                                if id_drive and not pd.isna(id_drive) and str(id_drive).strip().lower() not in ["none", "nan", ""]:
                                    mover_arquivo_drive_app(id_drive, ["Boletos", "PAGOS"])
                                    
                                # Atualiza status no banco e mantém a janela de 1 mês projetada!
                                if id_db and not pd.isna(id_db) and str(id_db).strip() != "":
                                    st.session_state.supabase.table('boletos_fornecedores').update({'status': 'Pago'}).eq('id', id_db).execute()
                                    try:
                                        if b.get('is_recorrente'):
                                            venc_antigo = datetime.datetime.strptime(b['vencimento'], "%Y-%m-%d").date()
                                            novo_venc = add_months_app(venc_antigo, 1)
                                            st.session_state.supabase.table('boletos_fornecedores').insert({
                                                'cliente': b.get('cliente'), 
                                                "vencimento": novo_venc.strftime('%Y-%m-%d'),
                                                'valor': b.get('valor'), 
                                                'status': 'Pendente', 
                                                'is_recorrente': True
                                            }).execute()
                                    except: pass
                            
                            # Atualiza no Google Calendar em tempo real após alteração para Pago
                            utils.sincronizar_boletos_com_calendar()
                            st.success("✅ Pago! Lembrete atualizado.")
                            st.rerun()
            else:
                st.info("🎉 Excelente! Nenhuma despesa ou boleto vencendo nos próximos 5 dias.")
        except Exception as e:
            st.caption("Conectando base de lembretes...")

        st.markdown("<hr style='margin-top: 20px; margin-bottom: 20px;'>", unsafe_allow_html=True)
        
        # =========================================================================
        # BOTÕES DE ACESSO RÁPIDO (CARDS GRANDES - TIPO SECONDARY)
        # =========================================================================
        c1, c2 = st.columns(2)
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

    # Roteamento dos módulos importados
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
