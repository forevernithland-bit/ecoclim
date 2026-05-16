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
    """Move um arquivo no Google Drive para uma nova pasta (Cópia da lógica do Docs)"""
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
    /* Fundo branco total na barra lateral para sumir com o fundo da logo */
    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e6ecf5;
    }
    
    /* Ajuste de padding e largura total (Padding-top ajustado para não cortar o topo) */
    .block-container { 
        padding-top: 3.5rem !important; 
        padding-left: 2rem !important; 
        padding-right: 2rem !important; 
        max-width: 100% !important; 
    }
    
    /* Remove espaços entre tabelas no módulo financeiro */
    div.container-tabelas div[data-testid="stVerticalBlock"] { 
        gap: 0px !important; 
        padding: 0px !important; 
    }
    
    /* Títulos padronizados em azul corporativo clean */
    h1, h2, h3 {
        color: #004488 !important;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }

    /* Força alinhamento vertical perfeito nas colunas (Botão e Texto na mesma linha) */
    div[data-testid="stHorizontalBlock"] {
        align-items: center !important;
    }

    /* Customização dos botões: Altura fixa, compacta e igual para todos (Estilo Tabela) */
    div.stButton > button {
        background-color: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #ccc !important;
        border-radius: 4px !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease-in-out !important;
        min-height: 42px !important;
        height: 42px !important;
        margin: 0 !important;
        padding: 0 10px !important;
        width: 100% !important;
    }

    /* Efeito de hover moderno nos botões */
    div.stButton > button:hover {
        border-color: #004488 !important;
        color: #004488 !important;
        box-shadow: 0 2px 4px -1px rgba(0, 68, 136, 0.1) !important;
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
        if st.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.menu_option = "Página Inicial"
            st.rerun()

    # =============================================================================
    # 8. ROTEADOR DE TELAS (CHAMA OS MÓDULOS)
    # =============================================================================
    if st.session_state.menu_option == "Página Inicial":
        
        st.caption(f"📅 Calendário Operacional: {utils.hoje.strftime('%d/%m/%Y')}")

        # =========================================================================
        # NOVO: DASHBOARD DE ALERTAS (LINHA ÚNICA, EFEITO TABELA EMPILHADA)
        # =========================================================================
        st.markdown("<h3>🔔 Lembretes de Pagamento (Próximos 5 Dias & Atrasos)</h3>", unsafe_allow_html=True)
        
        try:
            res_bol = st.session_state.supabase.table('boletos_fornecedores').select('*').eq('status', 'Pendente').order('vencimento').execute()
            
            lembretes_ativos = []
            if res_bol.data:
                hoje_dt = utils.hoje
                for b in res_bol.data:
                    venc_dt = datetime.datetime.strptime(b['vencimento'], "%Y-%m-%d").date()
                    diff_days = (venc_dt - hoje_dt).days
                    
                    # Filtro de tempo: Mostra apenas se atrasado (<=0) ou nos próximos 5 dias
                    if diff_days <= 5:
                        lembretes_ativos.append((b, venc_dt, diff_days))
            
            if lembretes_ativos:
                st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)
                for idx, (b, venc_dt, diff) in enumerate(lembretes_ativos):
                    
                    if diff < 0:
                        cor_card = "#ffe6e6"; icone = "🚨"; status_txt = "ATRASADO"
                    elif diff == 0:
                        cor_card = "#fff2cc"; icone = "⚠️"; status_txt = "VENCE HOJE"
                    else:
                        cor_card = "#e6ffe6"; icone = "📅"; status_txt = f"EM {diff} DIAS"
                    
                    # Puxa a linha para cima colando na anterior para dar efeito de tabela!
                    if idx > 0:
                        st.markdown("<div style='margin-top: -15px;'></div>", unsafe_allow_html=True)
                        
                    col_info, col_btn_doc, col_btn_pagar = st.columns([7, 1.5, 1.5])
                    
                    with col_info:
                        st.markdown(f"""
                            <div style="background-color: {cor_card}; border: 1px solid #ccc; border-radius: 4px; padding: 0 15px; display: flex; align-items: center; height: 42px;">
                                <span style="font-size: 14px; margin-right: 10px;">{icone}</span>
                                <span style="flex-grow: 1; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"><b>{b['cliente']}</b></span>
                                <span style="font-size: 12px; color: #555; margin-right: 15px;">Venc: <b>{venc_dt.strftime('%d/%m/%Y')}</b> ({status_txt})</span>
                                <span style="font-size: 14px; font-weight: bold; color: #004488;">{utils.to_br_currency(b['valor'])}</span>
                            </div>
                        """, unsafe_allow_html=True)
                    
                    with col_btn_doc:
                        if st.button("📂 Boletos", key=f"ir_{b['id']}", use_container_width=True):
                            st.session_state.menu_option = "Documentos"
                            st.rerun()
                            
                    with col_btn_pagar:
                        if st.button("✅ Pagar", key=f"pg_{b['id']}", use_container_width=True):
                            with st.spinner("Atualizando registros..."):
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
                            st.success("✅ Atualizado! Movido para pagos e recorrência gerada (se houver).")
                            st.rerun()
            else:
                st.info("🎉 Excelente! Nenhuma despesa ou boleto vencendo nos próximos 5 dias.")
        except Exception as e:
            st.caption("Conectando base de lembretes...")

        st.markdown("<hr style='margin-top: 15px; margin-bottom: 15px;'>", unsafe_allow_html=True)
        
        # =========================================================================
        # BOTÕES DE ACESSO RÁPIDO (GRID COMPACTO E PADRONIZADO)
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
