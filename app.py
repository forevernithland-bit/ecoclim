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
import estilo
import tela_orcamentos
import tela_servicos
import tela_financeira
import tela_configuracoes
import tela_airnb
import tela_documentos
import tela_relatorios

# =============================================================================
# 3. FUNÇÕES AUXILIARES PARA LEMBRETES NA PÁGINA INICIAL
# =============================================================================
def mover_arquivo_drive_app(file_id, folder_path_list):
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
# 5. TEMA / DESIGN SYSTEM GLOBAL (Parte 8) — claro/escuro, fontes, componentes
# =============================================================================
estilo.init_tema()
estilo.aplicar_tema()

# =============================================================================
# 6. LÓGICA DE ACESSO (LOGIN NO SUPABASE)
# =============================================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "menu_option" not in st.session_state:
    st.session_state.menu_option = "Página Inicial"

if not st.session_state.authenticated:

    # ===== LOGIN estilo Consorbens: fundo claro + cena ilustrada no rodapé =====
    st.markdown(estilo.css_fundo_login(), unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1.2, 1, 1.2])
    
    with col2:
        with st.container(border=True):
            c_img1, c_img2, c_img3 = st.columns([1, 1.2, 1])
            with c_img2:
                if os.path.exists("logo.png"):
                    st.image("logo.png", use_container_width=True)
            
            st.markdown(
                "<div class='login-head'>"
                "<div class='wel'>Acesse sua conta</div>"
                "<div class='sub'>Painel <b>Ecoclim ERP</b></div>"
                "</div>",
                unsafe_allow_html=True,
            )
            
            usuario = st.text_input("Usuário", value="breno.lima")
            senha = st.text_input("Senha", type="password")
            
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            if st.button("Acessar Sistema", use_container_width=True, key="btn_acessar"):
                if not usuario or not senha:
                    st.warning("Preencha usuário e senha.")
                else:
                    with st.spinner("Autenticando..."):
                        try:
                            usuario_tratado = usuario.strip().lower()
                            res = st.session_state.supabase.table('usuarios_erp').select('*').eq('usuario', usuario_tratado).execute()

                            if res.data and len(res.data) > 0:
                                dados_bd = res.data[0]
                                if dados_bd['senha'] == senha and dados_bd.get('ativo', True):
                                    st.session_state.authenticated = True
                                    st.session_state.usuario_logado = dados_bd.get('nome_completo', 'Usuário')
                                    st.session_state.perfil_logado = dados_bd.get('perfil', 'Admin')
                                    st.rerun()
                                else:
                                    st.error("Usuário ou senha incorretos.")
                            else:
                                st.error("Usuário ou senha incorretos.")
                        except Exception as e:
                            st.error(f"Erro ao conectar com o banco de dados: {e}")

            st.markdown(
                "<div class='login-chips'>"
                "<span>☀️ 10+ anos</span><span>🤝 +4 mil clientes</span><span>💡 Até 60% de economia</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            st.markdown("<div class='login-foot'>Especialistas em energia solar e sustentabilidade</div>", unsafe_allow_html=True)

else:
    # =============================================================================
    # 7. MENU DE NAVEGAÇÃO LATERAL (BARRA BRANCA LIMPA)
    # =============================================================================
    # ----- Permissões por perfil (Parte 6): Admin vê tudo; perfis restritos limitados -----
    perfil = st.session_state.get('perfil_logado', 'Admin')
    TODAS_PAGINAS = [
        "Página Inicial", "Controle Financeiro", "Orçamentos",
        "Serviços em Andamento", "Documentos", "AirBnb e Locações",
        "Relatórios", "Configurações",
    ]
    PAGINAS_POR_PERFIL = {
        "Contador": ["Notas Fiscais"],
    }
    lista_paginas = PAGINAS_POR_PERFIL.get(perfil, TODAS_PAGINAS)
    # Blindagem: se a página atual não é permitida ao perfil, volta para a 1ª permitida.
    if st.session_state.menu_option not in lista_paginas:
        st.session_state.menu_option = lista_paginas[0]

    with st.sidebar:
        st.markdown("<br>", unsafe_allow_html=True)
        if os.path.exists("logo.png"):
            st.image("logo.png", use_container_width=True)

        nome_logado = st.session_state.get('usuario_logado', 'Usuário')
        st.markdown(
            f"<div style='text-align:center; padding:8px 0 2px;'>"
            f"<div style=\"font-family:'Plus Jakarta Sans',sans-serif; font-weight:800; color:var(--ink);\">👤 {nome_logado}</div>"
            f"<div style='display:inline-block; margin-top:7px; font-size:.66rem; font-weight:700; letter-spacing:.09em;"
            f" text-transform:uppercase; color:#ffffff;"
            f" background:linear-gradient(135deg,var(--brand),var(--brand-dark)); padding:3px 11px; border-radius:999px;'>"
            f"{perfil}</div></div>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        index_atual = lista_paginas.index(st.session_state.menu_option) if st.session_state.menu_option in lista_paginas else 0
        menu = st.radio("Navegação", lista_paginas, index=index_atual, label_visibility="collapsed")

        if menu != st.session_state.menu_option:
            st.session_state.menu_option = menu
            st.rerun()

        estilo.render_seletor_tema_sidebar()
        
        st.write("---")
        if st.button("🚪 Sair do Sistema", type="primary", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.menu_option = "Página Inicial"
            # Limpa os dados do usuário ao sair
            if 'usuario_logado' in st.session_state: del st.session_state['usuario_logado']
            if 'perfil_logado' in st.session_state: del st.session_state['perfil_logado']
            st.rerun()

    # =============================================================================
    # 8. ROTEADOR DE TELAS (CHAMA OS MÓDULOS)
    # =============================================================================
    if st.session_state.menu_option == "Página Inicial":

        hoje_br = utils.obter_data_atual_br()

        # ---------- Cabeçalho do painel (claro e clean) ----------
        st.markdown(
            f"<div class='eco-hero'>"
            f"<span class='chip'>📅 {hoje_br.strftime('%d/%m/%Y')}</span>"
            f"<div class='htitle'>Painel operacional</div>"
            f"<div class='sub'>Mais conforto, mais economia, mais sustentabilidade.</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # ---------- KPIs (somente leitura, sem alterar regras de negócio) ----------
        try:
            _sa = st.session_state.supabase.table('servicos_andamento').select(
                'status_projeto, valor_venda_total, data_conclusao').execute().data or []
        except Exception:
            _sa = []
        _mes = hoje_br.strftime('%Y-%m')
        _em_and = sum(1 for r in _sa if str(r.get('status_projeto')) == 'Em Andamento')
        _orc = sum(1 for r in _sa if str(r.get('status_projeto')) == 'Orçamento Enviado')
        _fat = 0.0
        for r in _sa:
            stt = str(r.get('status_projeto', ''))
            # Faturamento do mês = concluído no mês atual + tudo que está em andamento agora.
            eh_concluido_mes = stt.startswith('Concluído') and str(r.get('data_conclusao', '')).startswith(_mes)
            if eh_concluido_mes or stt == 'Em Andamento':
                try:
                    _fat += float(r.get('valor_venda_total') or 0)
                except Exception:
                    pass
        try:
            _bp = st.session_state.supabase.table('boletos_fornecedores').select('valor').eq('status', 'Pendente').execute().data or []
            _pend = sum(float(x.get('valor') or 0) for x in _bp)
        except Exception:
            _pend = 0.0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🛠️ Serviços em andamento", str(_em_and))
        k2.metric("📝 Orçamentos enviados", str(_orc))
        k3.metric("💰 Faturamento do mês", utils.to_br_currency(_fat))
        k4.metric("📄 Boletos a pagar", utils.to_br_currency(_pend))

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='eco-sectiontitle'>🔔 Lembretes de Pagamento</div>", unsafe_allow_html=True)
        
        try:
            res_bol = st.session_state.supabase.table('boletos_fornecedores').select('*').eq('status', 'Pendente').order('vencimento').execute()
            
            lembretes_ativos = []
            if res_bol.data:
                hoje_dt = hoje_br
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
                    
                    if idx > 0:
                        st.markdown("<div style='margin-top: -16px;'></div>", unsafe_allow_html=True)
                        
                    col_info, col_btn_doc, col_btn_pagar = st.columns([7.5, 1.2, 1.2])
                    
                    with col_info:
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
                            st.session_state.doc_ir_para = "Boletos"
                            st.rerun()
                            
                    with col_btn_pagar:
                        if st.button("✅ Pagar", type="primary", key=f"pg_{b['id']}", use_container_width=True):
                            with st.spinner("Atualizando..."):
                                id_db = b['id']
                                id_drive = b.get('link_drive_id')
                                
                                if id_drive and not pd.isna(id_drive) and str(id_drive).strip().lower() not in ["none", "nan", ""]:
                                    mover_arquivo_drive_app(id_drive, ["Boletos", "PAGOS"])
                                    
                                if id_db and not pd.isna(id_db) and str(id_db).strip() != "":
                                    st.session_state.supabase.table('boletos_fornecedores').update({'status': 'Pago'}).eq('id', id_db).execute()
                                    try:
                                        if b.get('is_recorrente'):
                                            venc_antigo = datetime.datetime.strptime(b['vencimento'], "%Y-%m-%d").date()
                                            novo_venc = add_months_app(venc_antigo, 1)
                                            st.session_state.supabase.table('boletos_fornecedores').insert({
                                                'cliente': b.get('cliente'), 
                                                'categoria': b.get('categoria', 'Outros'), 
                                                "vencimento": novo_venc.strftime('%Y-%m-%d'),
                                                'valor': b.get('valor'), 
                                                'status': 'Pendente', 
                                                'is_recorrente': True
                                            }).execute()
                                    except: pass
                            
                            utils.sincronizar_boletos_com_calendar()
                            st.success("✅ Pago! Lembrete atualizado.")
                            st.rerun()
            else:
                st.info("🎉 Excelente! Nenhuma despesa ou boleto vencendo nos próximos 5 dias.")
        except Exception as e:
            st.caption("Conectando base de lembretes...")

        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='eco-sectiontitle'>⚡ Acessos rápidos</div>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        with c1:
            if st.button("📊  Controle Financeiro", use_container_width=True, key="btn_nav_financeiro"):
                st.session_state.menu_option = "Controle Financeiro"; st.rerun()
        with c2:
            if st.button("📝  Fazer Novo Orçamento", use_container_width=True, key="btn_nav_orcamentos"):
                st.session_state.menu_option = "Orçamentos"; st.rerun()
        with c3:
            if st.button("🛠️  Serviços em Andamento", use_container_width=True, key="btn_nav_servicos"):
                st.session_state.menu_option = "Serviços em Andamento"; st.rerun()
        with c4:
            if st.button("📁  Central de Documentos", use_container_width=True, key="btn_nav_documentos"):
                st.session_state.menu_option = "Documentos"; st.rerun()

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
        
    elif st.session_state.menu_option == "Relatórios":
        tela_relatorios.renderizar()

    elif st.session_state.menu_option == "Configurações":
        tela_configuracoes.renderizar()

    elif st.session_state.menu_option == "Notas Fiscais":
        # Acesso exclusivo do perfil Contador (Parte 6): somente Notas Fiscais,
        # com mês atual + histórico via seletor de mês da própria aba.
        st.markdown("<div class='eco-sectiontitle'>📊 Notas Fiscais</div>", unsafe_allow_html=True)
        tela_documentos.renderizar_aba("Notas Fiscais", subpastas=utils.meses_pt)
