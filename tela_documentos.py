import streamlit as st
import pandas as pd
import utils

def renderizar_gerenciador_pasta(nome_pasta):
    """Gera a interface visual de inclusão, visualização e exclusão de arquivos"""
    st.markdown(f"### 📂 Pasta: {nome_pasta.upper()}")
    
    # 1. Zona de Upload de Arquivos
    st.markdown("#### 📤 Upload de Novos Arquivos")
    arquivo_enviado = st.file_uploader(
        f"Arraste ou selecione arquivos para a pasta {nome_pasta}", 
        accept_multiple_files=True, 
        key=f"uploader_{nome_pasta}"
    )
    
    if arquivo_enviado:
        if st.button(f"🚀 Enviar Arquivos para o Drive ({nome_pasta})", key=f"btn_up_{nome_pasta}"):
            # Aqui entrará a chamada da API de upload do Google Drive na Fase 2
            st.info("Visualização de Layout: Na próxima fase este botão fará o envio direto ao Google Drive.")
            
    st.markdown("---")
    
    # 2. Lista de Arquivos da Pasta (Simulada para visualização do layout)
    st.markdown("#### 📄 Arquivos Armazenados")
    
    # Exemplo visual de como os arquivos aparecerão com opção de download e exclusão
    arquivos_mock = [
        {"Nome": f"exemplo_documento_1_{nome_pasta.lower()}.pdf", "Tamanho": "1.2 MB", "Data": utils.hoje.strftime('%d/%m/%Y')},
        {"Nome": f"comprovante_modelo_2_{nome_pasta.lower()}.png", "Tamanho": "450 KB", "Data": utils.hoje.strftime('%d/%m/%Y')}
    ]
    
    for i, arq in enumerate(arquivos_mock):
        with st.container(border=True):
            col_icon, col_txt, col_actions = st.columns([0.5, 5, 2])
            col_icon.markdown("### 📄")
            col_txt.markdown(f"**{arq['Nome']}**<br><small>Tamanho: {arq['Tamanho']} | Adicionado em: {arq['Data']}</small>", unsafe_allow_html=True)
            
            c_down, c_del = col_actions.columns(2)
            c_down.button("📥", key=f"down_{nome_pasta}_{i}", help="Baixar arquivo")
            
            # Botão de exclusão com confirmação de segurança
            if c_del.button("🗑️", key=f"del_{nome_pasta}_{i}", help="Excluir arquivo permanentemente"):
                st.session_state[f"confirm_del_{nome_pasta}_{i}"] = True
                
            if st.session_state.get(f"confirm_del_{nome_pasta}_{i}", False):
                st.error("Tem certeza que deseja apagar?")
                c_conf, c_canc = st.columns(2)
                if c_conf.button("Sim, apagar", key=f"conf_del_{nome_pasta}_{i}"):
                    # Lógica de exclusão do Drive entrará aqui
                    st.success("Arquivo apagado!")
                    del st.session_state[f"confirm_del_{nome_pasta}_{i}"]
                    st.rerun()
                if c_canc.button("Cancelar", key=f"canc_del_{nome_pasta}_{i}"):
                    del st.session_state[f"confirm_del_{nome_pasta}_{i}"]
                    st.rerun()

def renderizar():
    st.markdown("## 📁 Central de Documentos Integrada")
    st.write("Gerencie os arquivos da sua empresa com sincronização em tempo real no Google Drive.")
    st.write("---")
    
    # Criando as 5 abas solicitadas por você
    abas = st.tabs(["📝 Orçamentos", "🤝 Contratos", "🧾 Boletos", "🖼️ Imagens", "📊 Notas Fiscais (NF)"])
    
    with abas[0]:
        st.caption("Todos os orçamentos emitidos pelo sistema são salvos aqui de forma automática.")
        renderizar_gerenciador_pasta("Orçamentos")
        
    with abas[1]:
        st.caption("Contratos de prestação de serviço assinados e validados.")
        renderizar_gerenciador_pasta("Contratos")
        
    with abas[2]:
        st.caption("Controle de boletos de pagamento de fornecedores e insumos.")
        renderizar_gerenciador_pasta("Boletos")
        
    with abas[3]:
        st.caption("Fotos e registros de instalações, vistorias e obras concluídas.")
        renderizar_gerenciador_pasta("Imagens")
        
    with abas[4]:
        st.caption("Arquivo digital das Notas Fiscais (NF) de saída emitidas pela empresa.")
        renderizar_gerenciador_pasta("NF")
