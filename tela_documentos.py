import streamlit as st
import utils
import datetime

def formatar_tamanho(tamanho_bytes):
    try:
        tamanho = int(tamanho_bytes)
        if tamanho < 1024: return f"{tamanho} B"
        elif tamanho < 1024 * 1024: return f"{tamanho / 1024:.1f} KB"
        else: return f"{tamanho / (1024 * 1024):.1f} MB"
    except: return "Desconhecido"

def formatar_data(data_iso):
    try:
        dt = datetime.datetime.fromisoformat(data_iso.replace('Z', '+00:00'))
        return dt.strftime('%d/%m/%Y %H:%M')
    except: return data_iso

def renderizar_aba(nome_principal, subpastas=None, usa_busca=False):
    path_atual = [nome_principal]
    
    col_pesquisa, col_up = st.columns([2, 1])
    
    with col_pesquisa:
        if subpastas:
            sub_sel = st.selectbox("Selecione a Pasta / Mês:", subpastas, key=f"sel_{nome_principal}")
            path_atual.append(sub_sel)
        
        termo_busca = ""
        if usa_busca:
            termo_busca = st.text_input(f"🔍 Buscar em {nome_principal}...", key=f"busca_{nome_principal}").lower()

    with col_up:
        # Pula uma linha apenas se houver o selectbox para alinhar certinho
        if subpastas and not usa_busca: st.markdown("<br>", unsafe_allow_html=True)
        
        with st.expander("📤 Upload de Arquivos"):
            arquivos_enviados = st.file_uploader(
                "Selecione os arquivos", 
                accept_multiple_files=True, 
                key=f"up_{nome_principal}_{path_atual[-1] if subpastas else ''}", 
                label_visibility="collapsed"
            )
            if arquivos_enviados and st.button("🚀 Enviar", key=f"btn_env_{nome_principal}", type="primary", use_container_width=True):
                with st.spinner("Enviando para o Google Drive..."):
                    for arq in arquivos_enviados:
                        utils.upload_to_drive(arq, arq.name, arq.type, path_atual)
                st.success("Arquivos enviados com sucesso!")
                st.rerun()

    st.markdown("---")
    
    # ---------------------------------------------
    # LISTAGEM DE ARQUIVOS (Layout Limpo)
    # ---------------------------------------------
    arquivos = utils.list_drive_files(path_atual)
    
    if not arquivos:
        st.info("Nenhum arquivo encontrado nesta pasta.")
        return

    if termo_busca:
        arquivos = [a for a in arquivos if termo_busca in a['name'].lower()]
        if not arquivos:
            st.warning("Nenhum arquivo corresponde à sua busca.")
            return

    # Cabeçalho da Lista
    st.markdown("""
        <div style='display: flex; font-weight: bold; color: #004488; padding-bottom: 5px; border-bottom: 2px solid #ddd; margin-bottom: 10px;'>
            <div style='flex: 5;'>Nome do Arquivo</div>
            <div style='flex: 2;'>Data de Inclusão</div>
            <div style='flex: 1.5;'>Tamanho</div>
            <div style='flex: 1.5; text-align: center;'>Ações</div>
        </div>
    """, unsafe_allow_html=True)

    # Linhas da Lista
    for arq in arquivos:
        c1, c2, c3, c4 = st.columns([5, 2, 1.5, 1.5])
        
        tam = formatar_tamanho(arq.get('size', 0))
        data = formatar_data(arq.get('createdTime', ''))
        link = arq.get('webViewLink', '#')

        c1.markdown(f"<div style='padding-top:8px;'>📄 <b>{arq['name']}</b></div>", unsafe_allow_html=True)
        c2.markdown(f"<div style='padding-top:8px;'>{data}</div>", unsafe_allow_html=True)
        c3.markdown(f"<div style='padding-top:8px;'>{tam}</div>", unsafe_allow_html=True)
        
        c_view, c_del = c4.columns(2)
        c_view.markdown(f"<a href='{link}' target='_blank' style='display:block; padding-top:5px; text-decoration:none; font-size:18px;' title='Visualizar/Baixar'>👁️</a>", unsafe_allow_html=True)
        
        if c_del.button("🗑️", key=f"del_{arq['id']}", help="Excluir arquivo"):
            st.session_state[f"confirm_del_{arq['id']}"] = True
            
        # Alerta de confirmação de exclusão
        if st.session_state.get(f"confirm_del_{arq['id']}", False):
            st.error("Deseja mesmo apagar este arquivo do Google Drive?")
            cx1, cx2 = c1.columns(2)
            if cx1.button("Sim, apagar", key=f"conf_{arq['id']}", type="primary"):
                utils.delete_drive_file(arq['id'])
                st.success("Apagado com sucesso!")
                del st.session_state[f"confirm_del_{arq['id']}"]
                st.rerun()
            if cx2.button("Cancelar", key=f"canc_{arq['id']}"):
                del st.session_state[f"confirm_del_{arq['id']}"]
                st.rerun()
                
        st.markdown("<hr style='margin: 0px; border-color: #f0f0f0;'>", unsafe_allow_html=True)

def renderizar():
    # Removemos o título superior e as descrições para manter a tela super limpa e direta!
    abas = st.tabs(["📝 Orçamentos", "🤝 Contratos", "🧾 Boletos", "🖼️ Imagens", "📊 Notas Fiscais (NF)"])
    
    with abas[0]: 
        renderizar_aba("Orçamentos", usa_busca=True)
        
    with abas[1]: 
        renderizar_aba("Contratos", usa_busca=True)
        
    with abas[2]: 
        meses_boletos = utils.meses_pt + ["PAGOS"]
        renderizar_aba("Boletos", subpastas=meses_boletos)
        
    with abas[3]: 
        renderizar_aba("Imagens", subpastas=utils.meses_pt)
        
    with abas[4]: 
        renderizar_aba("Notas Fiscais", subpastas=utils.meses_pt)
