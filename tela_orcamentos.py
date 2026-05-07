import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar():
    st.markdown("## 📝 Novo Orçamento")
    
    st.session_state.db_produtos = utils.load_catalog('catalogo_produtos')
    st.session_state.db_servicos = utils.load_catalog('catalogo_servicos')
    st.session_state.db_outros = utils.load_catalog('catalogo_outros')

    cat_p = st.session_state.db_produtos
    lista_p = cat_p['Item'].tolist() if not cat_p.empty else []
    
    with st.container(border=True):
        st.subheader("👤 Dados do Cliente")
        c1, c2 = st.columns(2)
        nome_c = c1.text_input("Nome do Cliente", key="nome_cliente_orc")
        tel_c = c2.text_input("WhatsApp", key="tel_cliente_orc")
        
        # PRÉ-SELECIONADO O VÁCUO ACOPLADO
        capa = st.selectbox("Modelo para Capa", [
            "AQUECEDOR SOLAR TRADICIONAL", 
            "AQUECEDOR SOLAR A VÁCUO ACOPLADO", 
            "AQUECEDOR SOLAR MODULAR", 
            "AQUECEDOR DE PISCINA - TRADICIONAL", 
            "AQUECEDOR DE PISCINA - TROCADOR DE CALOR", 
            "SISTEMAS DE PRESSURIZAÇÃO"
        ], index=1)

    with st.container(border=True):
        st.subheader("⚙️ 1. Equipamentos")
        # DESMARCADO POR PADRÃO
        mostrar_pdf = st.checkbox("Mostrar Preços Unitários no PDF?", value=False)
        
        # COLUNA DE DESCRIÇÃO ADICIONADA E QUANTIDADE ZERADA
        if 'df_orc' not in st.session_state:
            st.session_state.df_orc = pd.DataFrame([{"Produto da Base": "", "Produto Manual": "", "Descrição": "", "Quantidade": 0, "Venda (R$)": 0.0, "Venda Total": 0.0} for _ in range(5)])
        else:
            if "Venda Total" not in st.session_state.df_orc.columns:
                st.session_state.df_orc["Venda Total"] = 0.0
            if "Descrição" not in st.session_state.df_orc.columns:
                st.session_state.df_orc["Descrição"] = ""
        
        cfg = {
            "Produto da Base": st.column_config.SelectboxColumn("Produto", options=[""] + lista_p + ["OUTRO"], width="medium"), 
            "Produto Manual": st.column_config.TextColumn("Produto Manual", width="medium"),
            "Descrição": st.column_config.TextColumn("Detalhes / Garantia", width="large"),
            "Quantidade": st.column_config.NumberColumn("Qtd", min_value=0, step=1),
            "Venda (R$)": st.column_config.NumberColumn("Preço Un. (R$)", format="R$ %,.2f"),
            "Venda Total": st.column_config.NumberColumn("Venda Total (R$)", format="R$ %,.2f", disabled=True)
        }
        
        df_ed = st.data_editor(st.session_state.df_orc, column_config=cfg, num_rows="dynamic", use_container_width=True)
        df_ed = df_ed.reset_index(drop=True)
        
        df_ed['Quantidade'] = pd.to_numeric(df_ed['Quantidade'], errors='coerce').fillna(0).astype(int)
        df_ed['Venda (R$)'] = pd.to_numeric(df_ed['Venda (R$)'], errors='coerce').fillna(0.0).astype(float)
        
        if "Venda Total" not in df_ed.columns:
            df_ed["Venda Total"] = 0.0
        if "Descrição" not in df_ed.columns:
            df_ed["Descrição"] = ""

        precisa_atualizar = False
        for i in range(len(df_ed)):
            p = df_ed.at[i, 'Produto da Base']
            if p in lista_p:
                match = cat_p[cat_p['Item'] == p]
                if not match.empty:
                    if df_ed.at[i, 'Venda (R$)'] == 0:
                        df_ed.at[i, 'Venda (R$)'] = float(match['Venda (R$)'].values[0])
                        precisa_atualizar = True
                    
                    # Puxa a descrição da base e joga na tabela na hora
                    if str(df_ed.at[i, 'Descrição']).strip() == "" and 'Descrição' in match.columns:
                        desc_bd = str(match['Descrição'].values[0])
                        if desc_bd != "nan" and desc_bd.strip() != "":
                            df_ed.at[i, 'Descrição'] = desc_bd
                            precisa_atualizar = True
                
        nova_venda_total = df_ed['Venda (R$)'] * df_ed['Quantidade']
        if not df_ed['Venda Total'].equals(nova_venda_total):
            df_ed['Venda Total'] = nova_venda_total
            precisa_atualizar = True
        
        if precisa_atualizar:
            st.session_state.df_orc = df_ed
            st.rerun()
            
        st.session_state.df_orc = df_ed
        total_equip = df_ed['Venda Total'].sum()
        st.markdown(f"**Subtotal Equipamentos:** :blue[{utils.to_br_currency(total_equip)}]")

    with st.container(border=True):
        st.subheader("🛠️ 2. Serviços / Diversos")
        
        lista_s = st.session_state.db_servicos['Item'].tolist() if not st.session_state.db_servicos.empty else []
        s_sel = st.selectbox("Selecionar Serviço Principal:", [""] + lista_s + ["Manual"])
        if s_sel == "Manual": 
            d_s = st.text_area("Descreva o Serviço:")
            v_s = st.number_input("Valor do Serviço (R$):", min_value=0.0, format="%.2f")
        elif s_sel != "":
            d_s = f"{s_sel}\n{st.session_state.db_servicos.loc[st.session_state.db_servicos['Item']==s_sel, 'Descrição'].values[0]}" if 'Descrição' in st.session_state.db_servicos.columns else s_sel
            v_s = float(st.session_state.db_servicos.loc[st.session_state.db_servicos['Item']==s_sel, 'Venda (R$)'].values[0])
            st.write(f"Valor do Serviço: {utils.to_br_currency(v_s)}")
        else: 
            d_s, v_s = "", 0.0
        
        lista_o = st.session_state.db_outros['Item'].tolist() if not st.session_state.db_outros.empty else []
        o_sel = st.selectbox("Adicionar Outros/Diversos:", [""] + lista_o + ["Manual"])
        if o_sel == "Manual": 
            d_o = st.text_area("Descreva Diversos:")
            v_o = st.number_input("Valor Adicional (R$):", min_value=0.0, format="%.2f")
        elif o_sel != "":
            d_o = f"{o_sel}\n{st.session_state.db_outros.loc[st.session_state.db_outros['Item']==o_sel, 'Descrição'].values[0]}" if 'Descrição' in st.session_state.db_outros.columns else o_sel
            v_o = float(st.session_state.db_outros.loc[st.session_state.db_outros['Item']==o_sel, 'Venda (R$)'].values[0])
            st.write(f"Valor Adicional: {utils.to_br_currency(v_o)}")
        else: 
            d_o, v_o = "", 0.0

    total_geral = total_equip + v_s + v_o
    
    st.markdown(f"<h3 style='color:#004488;'>💰 INVESTIMENTO TOTAL: {utils.to_br_currency(total_geral)}</h3>", unsafe_allow_html=True)
    obs = st.text_area("Observações no PDF:", value="Material Hidráulico não incluído na proposta")

    st.markdown("---")
    st.subheader("🚀 Finalização")

    col_prev, col_salvar = st.columns(2)

    with col_prev:
        st.info("👁️ **Passo 1: Conferência**\nGere um PDF de rascunho para verificar dados e formatação antes de registrá-lo.")
        if st.button("GERAR PRÉVIA DO PDF", use_container_width=True):
            if not nome_c:
                st.warning("Preencha o nome do cliente!")
            else:
                st.session_state['pdf_previa'] = utils.gerar_pdf_orcamento(nome_c, tel_c, capa, df_ed, d_s, v_s, d_o, v_o, total_geral, obs, mostrar_pdf)
                st.session_state['nome_previa'] = nome_c
        
        if 'pdf_previa' in st.session_state and st.session_state.get('nome_previa') == nome_c:
            st.download_button("📥 BAIXAR RASCUNHO (Conferir)", data=st.session_state['pdf_previa'], file_name=f"RASCUNHO_{nome_c}.pdf", mime="application/pdf", use_container_width=True)

    with col_salvar:
        st.warning("💾 **Passo 2: Salvar Oficial**\nRegistra no sistema, cria número oficial e congela os preços atuais da base.")
        if st.button("SALVAR ORÇAMENTO NO SISTEMA", type="primary", use_container_width=True):
            if not nome_c:
                st.error("Preencha o nome do cliente!")
            else:
                custo_real_equip = 0.0
                resumo_produtos = []
                detalhamento_snapshot = []
                
                for _, row in df_ed.iterrows():
                    nome_p = row['Produto da Base']
                    desc_m = row['Produto Manual']
                    qtd = int(row['Quantidade'])
                    venda_un = float(row['Venda (R$)'])
                    desc_prod = str(row.get('Descrição', ""))
                    
                    if qtd <= 0 or (nome_p == "" and desc_m.strip() == ""): continue
                    
                    if nome_p in lista_p:
                        c_un = float(cat_p.loc[cat_p['Item'] == nome_p, 'Custo (R$)'].values[0])
                        custo_real_equip += (c_un * qtd)
                        resumo_produtos.append(f"{qtd}x {nome_p}")
                        detalhamento_snapshot.append({"Item": nome_p, "Descrição Manual": desc_prod, "Qtd": qtd, "Custo Un.": c_un, "Venda Un.": venda_un})
                    elif desc_m.strip() != "":
                        resumo_produtos.append(f"{qtd}x {desc_m}")
                        detalhamento_snapshot.append({"Item": "OUTRO / MANUAL", "Descrição Manual": desc_prod if desc_prod else desc_m, "Qtd": qtd, "Custo Un.": 0.0, "Venda Un.": venda_un})

                if s_sel != "":
                    if s_sel == "Manual":
                        detalhamento_snapshot.append({"Item": "OUTRO / MANUAL", "Descrição Manual": d_s, "Qtd": 1, "Custo Un.": 0.0, "Venda Un.": v_s})
                    else:
                        c_s = float(st.session_state.db_servicos.loc[st.session_state.db_servicos['Item']==s_sel, 'Custo (R$)'].values[0])
                        detalhamento_snapshot.append({"Item": s_sel, "Descrição Manual": "", "Qtd": 1, "Custo Un.": c_s, "Venda Un.": v_s})
                        resumo_produtos.append(f"1x {s_sel}")
                        
                if o_sel != "":
                    if o_sel == "Manual":
                        detalhamento_snapshot.append({"Item": "OUTRO / MANUAL", "Descrição Manual": d_o, "Qtd": 1, "Custo Un.": 0.0, "Venda Un.": v_o})
                    else:
                        c_o = float(st.session_state.db_outros.loc[st.session_state.db_outros['Item']==o_sel, 'Custo (R$)'].values[0])
                        detalhamento_snapshot.append({"Item": o_sel, "Descrição Manual": "", "Qtd": 1, "Custo Un.": c_o, "Venda Un.": v_o})
                        resumo_produtos.append(f"1x {o_sel}")

                num_orc = f"ORC-{datetime.datetime.now().strftime('%y%m%d-%H%M')}"
                
                try:
                    st.session_state.supabase.table("servicos_andamento").insert({
                        "numero_orcamento": num_orc,
                        "nome_cliente": nome_c, 
                        "telefone_cliente": tel_c, 
                        "produtos_adquiridos": ", ".join(resumo_produtos),
                        "servicos_adquiridos": d_s,
                        "valor_venda_total": total_geral,
                        "valor_custo_equipamentos": custo_real_equip,
                        "lucro_estimado": total_geral - custo_real_equip,
                        "status_projeto": "Orçamento Enviado",
                        "detalhamento_itens": detalhamento_snapshot
                    }).execute()
                    
                    st.session_state['pdf_oficial'] = utils.gerar_pdf_orcamento(nome_c, tel_c, capa, df_ed, d_s, v_s, d_o, v_o, total_geral, obs, mostrar_pdf)
                    st.session_state['oficial_filename'] = f"{num_orc}_{nome_c}.pdf"
                    st.session_state['msg_sucesso'] = f"✅ Orçamento {num_orc} salvo com sucesso!"
                except Exception as e:
                    st.error(f"Erro ao salvar no banco: {e}")

        if 'pdf_oficial' in st.session_state and 'msg_sucesso' in st.session_state:
            st.success(st.session_state['msg_sucesso'])
            st.download_button("📥 BAIXAR ORÇAMENTO OFICIAL", data=st.session_state['pdf_oficial'], file_name=st.session_state['oficial_filename'], mime="application/pdf", type="primary", use_container_width=True)
            
            if st.button("🔄 Criar Novo Orçamento", use_container_width=True):
                for key in ['pdf_previa', 'pdf_oficial', 'msg_sucesso', 'df_orc', 'nome_previa']:
                    st.session_state.pop(key, None)
                st.rerun()
