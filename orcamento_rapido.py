import streamlit as st
import pandas as pd
import datetime
import utils

def renderizar(lista_nomes_produtos, limpar_func):
    deve_rerun = False
    cat_produtos = st.session_state.db_produtos

    st.markdown("### ⚡ Calculadora de Custo e Venda Rápida")
    st.caption("Apenas para cálculo interno de margem. Salva como rascunho específico desta aba.")

    if st.session_state.get("show_transfer_success"):
        st.success("✅ Produtos e Valores enviados com sucesso! Acesse a aba **'Orçamento Personalizado'** no topo da página para continuar e gerar o PDF.")
        st.session_state.show_transfer_success = False

    try:
        res_r = st.session_state.supabase.table('servicos_andamento').select('id, nome_cliente, valor_venda_total').eq('status_projeto', 'Rascunho Rápido').execute()
        rascunhos_rapidos = res_r.data
    except Exception: 
        rascunhos_rapidos = []

    if rascunhos_rapidos or st.session_state.get('rapido_rascunho_id'):
        with st.expander("📂 Meus Cálculos Salvos", expanded=True if st.session_state.get('rapido_rascunho_id') else False):
            if st.session_state.get('rapido_rascunho_id'):
                st.success("✏️ Você está editando um cálculo rápido em andamento.")
                if st.button("❌ Fechar e Iniciar Novo Cálculo", use_container_width=True):
                    limpar_func()
                    deve_rerun = True
            else:
                c_sel, c_load, c_del = st.columns([3, 1, 1])
                opcoes_rapidas = {f"{r['nome_cliente']} ({utils.to_br_currency(r['valor_venda_total'])})": r['id'] for r in rascunhos_rapidos}
                sel_r = c_sel.selectbox("Escolha um cálculo:", list(opcoes_rapidas.keys()), key="sel_rapido", label_visibility="collapsed")
                
                if c_load.button("📥 Abrir", use_container_width=True):
                    id_r = opcoes_rapidas[sel_r]
                    data_r = st.session_state.supabase.table('servicos_andamento').select('*').eq('id', id_r).execute().data[0]
                    st.session_state.rapido_rascunho_id = data_r['id']
                    st.session_state.rapido_input_nome_cliente = data_r['nome_cliente']
                    
                    d_ct_r = data_r.get('dados_contrato', {})
                    st.session_state.rapido_custo_servico = float(d_ct_r.get('custo_servico', 0.0))
                    st.session_state.rapido_venda_servico = float(d_ct_r.get('venda_servico', 0.0))
                    st.session_state.rapido_custo_outros = float(d_ct_r.get('custo_outros', 0.0))
                    st.session_state.rapido_venda_outros = float(d_ct_r.get('venda_outros', 0.0))
                    st.session_state.rapido_nf = d_ct_r.get('nf', "Não")
                    st.session_state.rapido_taxa_cartao = d_ct_r.get('taxa_cartao', "Nenhum / Dinheiro / PIX")
                    st.session_state.rapido_comissao = float(d_ct_r.get('comissao', 0.0))

                    itens_r = data_r.get('detalhamento_itens', [])
                    df_rec = []
                    for it in itens_r:
                        p_base = str(it.get("Item", "")).strip()
                        p_man = ""
                        
                        if p_base and p_base not in lista_nomes_produtos and p_base != "OUTRO":
                            p_man = p_base
                            p_base = "OUTRO"
                            
                        df_rec.append({
                            "Produto da Base": p_base,
                            "Produto Manual": p_man,
                            "Quantidade": float(it.get("Qtd", 0)),
                            "Custo (R$)": float(it.get("Custo Un.", 0)),
                            "Venda (R$)": float(it.get("Venda Un.", 0)),
                            "Custo Total": float(it.get("Qtd", 0)) * float(it.get("Custo Un.", 0)),
                            "Venda Total": float(it.get("Qtd", 0)) * float(it.get("Venda Un.", 0))
                        })
                    
                    while len(df_rec) < 5:
                        df_rec.append({"Produto da Base": "", "Produto Manual": "", "Quantidade": 0, "Custo (R$)": 0.0, "Venda (R$)": 0.0, "Custo Total": 0.0, "Venda Total": 0.0})
                        
                    st.session_state.rapido_df_orc = pd.DataFrame(df_rec)
                    if "editor_rapido" in st.session_state:
                        del st.session_state["editor_rapido"]
                    deve_rerun = True
                    
                if c_del.button("🗑️ Apagar", use_container_width=True):
                    st.session_state.supabase.table('servicos_andamento').delete().eq('id', opcoes_rapidas[sel_r]).execute()
                    st.success("Cálculo apagado!")
                    deve_rerun = True

    nome_rapido = st.text_input("Nome do Cliente (Identificação)", key="rapido_input_nome_cliente")

    st.markdown("#### 📦 Equipamentos")
    if 'rapido_df_orc' not in st.session_state:
        st.session_state.rapido_df_orc = pd.DataFrame([{"Produto da Base": "", "Produto Manual": "", "Quantidade": 0, "Custo (R$)": 0.0, "Venda (R$)": 0.0, "Custo Total": 0.0, "Venda Total": 0.0} for _ in range(5)])
    
    cfg_grid = {
        "Produto da Base": st.column_config.SelectboxColumn("Produto", options=[""] + lista_nomes_produtos + ["OUTRO"], width="large"),
        "Produto Manual": st.column_config.TextColumn("Nome Manual", width="medium"),
        "Quantidade": st.column_config.NumberColumn("Qtd", min_value=0, width="small"),
        "Custo (R$)": st.column_config.NumberColumn("Custo Unt.", format="R$ %.2f", width="small"),
        "Venda (R$)": st.column_config.NumberColumn("Venda Unt.", format="R$ %.2f", width="small"),
        "Custo Total": st.column_config.NumberColumn("Custo Total", format="R$ %.2f", disabled=True, width="small"),
        "Venda Total": st.column_config.NumberColumn("Venda Total", format="R$ %.2f", disabled=True, width="small"),
    }
    
    seq_r = ["Produto da Base", "Produto Manual", "Quantidade", "Custo (R$)", "Venda (R$)", "Custo Total", "Venda Total"]

    df_r_ed = st.data_editor(st.session_state.rapido_df_orc, column_config=cfg_grid, column_order=seq_r, num_rows="dynamic", use_container_width=True, key="editor_rapido", hide_index=True)
    
    refresh_rapido = False
    for i in range(len(df_r_ed)):
        p_atual = str(df_r_ed.at[i, "Produto da Base"]).strip()
        
        p_ant = ""
        if i < len(st.session_state.rapido_df_orc):
            p_ant = str(st.session_state.rapido_df_orc.at[i, "Produto da Base"]).strip()
        
        if p_atual != p_ant and p_atual != "" and p_atual != "OUTRO":
            match = cat_produtos[cat_produtos['Item'].astype(str).str.strip() == p_atual]
            if not match.empty:
                try: custo_n = float(match.get('Custo (R$)', pd.Series([0.0])).values[0])
                except: custo_n = 0.0
                try: venda_n = float(match['Venda (R$)'].values[0])
                except: venda_n = 0.0
                
                df_r_ed.at[i, "Custo (R$)"] = custo_n
                df_r_ed.at[i, "Venda (R$)"] = venda_n
                if pd.isna(df_r_ed.at[i, "Quantidade"]) or float(df_r_ed.at[i, "Quantidade"]) <= 0:
                    df_r_ed.at[i, "Quantidade"] = 1
                refresh_rapido = True
        
        qtd = float(df_r_ed.at[i, "Quantidade"]) if pd.notna(df_r_ed.at[i, "Quantidade"]) else 0.0
        c_un = float(df_r_ed.at[i, "Custo (R$)"]) if pd.notna(df_r_ed.at[i, "Custo (R$)"]) else 0.0
        v_un = float(df_r_ed.at[i, "Venda (R$)"]) if pd.notna(df_r_ed.at[i, "Venda (R$)"]) else 0.0
        
        tot_c_calc = qtd * c_un
        tot_v_calc = qtd * v_un
        
        if abs(tot_c_calc - float(df_r_ed.at[i, "Custo Total"])) > 0.01 or abs(tot_v_calc - float(df_r_ed.at[i, "Venda Total"])) > 0.01:
            df_r_ed.at[i, "Custo Total"] = tot_c_calc
            df_r_ed.at[i, "Venda Total"] = tot_v_calc
            refresh_rapido = True

    if refresh_rapido:
        st.session_state.rapido_df_orc = df_r_ed
        deve_rerun = True
        
    st.session_state.rapido_df_orc = df_r_ed

    custo_total_produtos_r = pd.to_numeric(df_r_ed["Custo Total"], errors='coerce').fillna(0).sum()
    venda_total_produtos_r = pd.to_numeric(df_r_ed["Venda Total"], errors='coerce').fillna(0).sum()
    lucro_total_produtos_r = venda_total_produtos_r - custo_total_produtos_r
    
    st.markdown(f"""
        <div style='display: flex; justify-content: flex-end; gap: 25px; margin-top: -10px; margin-bottom: 25px;'>
            <span style='color: #cc0000; font-size: 15px;'><b>Custo Total Produtos:</b> {utils.to_br_currency(custo_total_produtos_r)}</span>
            <span style='color: #004488; font-size: 15px;'><b>Venda Total Produtos:</b> {utils.to_br_currency(venda_total_produtos_r)}</span>
            <span style='color: #006600; font-size: 15px;'><b>Lucro Total Produtos:</b> {utils.to_br_currency(lucro_total_produtos_r)}</span>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 🛠️ Mão de Obra e Outros")
    
    c_s1, c_s2 = st.columns(2)
    c_serv = c_s1.number_input("Custo de Serviço (R$)", min_value=0.0, format="%.2f", key="rapido_custo_servico")
    v_serv = c_s2.number_input("Preço de Venda Serviço (R$)", min_value=0.0, format="%.2f", key="rapido_venda_servico")
    
    c_o1, c_o2 = st.columns(2)
    c_outros = c_o1.number_input("Custo de Outros/Terceiros (R$)", min_value=0.0, format="%.2f", key="rapido_custo_outros")
    v_outros = c_o2.number_input("Preço de Venda Outros (R$)", min_value=0.0, format="%.2f", key="rapido_venda_outros")

    st.markdown("#### 🧮 Impostos e Taxas")
    with st.container(border=True):
        col_t1, col_t2, col_t3 = st.columns(3)
        
        venda_bruta = df_r_ed["Venda Total"].sum() + v_serv + v_outros
        
        emite_nf = col_t1.radio("Nota Fiscal?", ["Não", "Sim"], horizontal=True, key="rapido_nf")
        taxa_nf_val = 6.0
        if not st.session_state.db_taxas.empty:
            for _, t_row in st.session_state.db_taxas.iterrows():
                if "NF" in str(t_row.get('Item', '')).upper() or "NOTA FISCAL" in str(t_row.get('Item', '')).upper():
                    try: taxa_nf_val = float(t_row.get('Taxa (%)', 6.0))
                    except: pass
        
        custo_nf = venda_bruta * (taxa_nf_val/100) if emite_nf == "Sim" else 0.0
        col_t1.caption(f"Custo NF ({taxa_nf_val}%): - {utils.to_br_currency(custo_nf)}")

        opcoes_cartao = ["Nenhum / Dinheiro / PIX"]
        dict_taxas = {"Nenhum / Dinheiro / PIX": 0.0}
        if not st.session_state.db_taxas.empty:
            for _, t_row in st.session_state.db_taxas.iterrows():
                item_nome = str(t_row.get('Item', '')).strip()
                try: taxa_val = float(t_row.get('Taxa (%)', 0.0))
                except: taxa_val = 0.0
                if "NF" not in item_nome.upper() and "NOTA FISCAL" not in item_nome.upper() and item_nome != "":
                    opcoes_cartao.append(item_nome)
                    dict_taxas[item_nome] = taxa_val
        
        sel_cartao = col_t2.selectbox("Parcelamento Cartão", opcoes_cartao, key="rapido_taxa_cartao")
        taxa_c_pct = dict_taxas[sel_cartao]
        custo_cartao = venda_bruta * (taxa_c_pct / 100)
        col_t2.caption(f"Taxa Cartão ({taxa_c_pct}%): - {utils.to_br_currency(custo_cartao)}")

        comissao_pct = col_t3.number_input("Comissão (%)", min_value=0.0, format="%.1f", key="rapido_comissao")
        custo_comissao = venda_bruta * (comissao_pct / 100)
        col_t3.caption(f"Valor Comissão: - {utils.to_br_currency(custo_comissao)}")

    custo_equip = df_r_ed["Custo Total"].sum()
    custo_fixo = custo_equip + c_serv + c_outros
    custo_variavel = custo_nf + custo_cartao + custo_comissao
    custo_total_geral = custo_fixo + custo_variavel
    
    lucro_est = venda_bruta - custo_total_geral
    margem_pct = (lucro_est / venda_bruta * 100) if venda_bruta > 0 else 0.0

    st.markdown("<br>", unsafe_allow_html=True)
    res1, res2, res3 = st.columns(3)
    res1.metric("Custo Total Acumulado", utils.to_br_currency(custo_total_geral))
    res2.metric("Preço de Venda Final", utils.to_br_currency(venda_bruta))
    res3.metric("LUCRO LÍQUIDO", utils.to_br_currency(lucro_est), delta=f"{margem_pct:.1f}% Margem Real")

    st.markdown("<hr style='margin-top: 20px; margin-bottom: 20px;'>", unsafe_allow_html=True)
    col_btn_r1, col_btn_r2 = st.columns(2)
    
    with col_btn_r1:
        if st.button("➡️ ENVIAR PARA ORÇAMENTO PERSONALIZADO", use_container_width=True):
            st.session_state.transferir_agora = True
            st.rerun()

    with col_btn_r2:
        if st.button("💾 SALVAR CÁLCULO RÁPIDO", type="primary", use_container_width=True):
            if not nome_rapido:
                st.error("⚠️ Preencha o Nome do Cliente (Identificação) para poder salvar.")
            else:
                snapshot = []
                for _, r in df_r_ed.iterrows():
                    p_base = str(r.get("Produto da Base", "")).strip()
                    p_man = str(r.get("Produto Manual", "")).strip()
                    
                    if r["Quantidade"] > 0 or p_base != "" or p_man != "":
                        nome_item = p_base if p_base not in ["", "OUTRO", "None"] else p_man
                        snapshot.append({
                            "Item": nome_item, 
                            "Qtd": r["Quantidade"], 
                            "Venda Un.": r["Venda (R$)"], 
                            "Custo Un.": r["Custo (R$)"]
                        })
                
                payload = {
                    "nome_cliente": nome_rapido,
                    "valor_venda_total": venda_bruta,
                    "lucro_estimado": lucro_est,
                    "status_projeto": "Rascunho Rápido",
                    "detalhamento_itens": snapshot,
                    "data_conclusao": datetime.date.today().strftime('%Y-%m-%d'),
                    "dados_contrato": {
                        "custo_servico": c_serv, 
                        "venda_servico": v_serv,
                        "custo_outros": c_outros, 
                        "venda_outros": v_outros,
                        "nf": emite_nf, 
                        "taxa_cartao": sel_cartao, 
                        "comissao": comissao_pct
                    }
                }
                
                if st.session_state.get('rapido_rascunho_id'):
                    st.session_state.supabase.table('servicos_andamento').update(payload).eq('id', st.session_state.rapido_rascunho_id).execute()
                else:
                    res = st.session_state.supabase.table('servicos_andamento').insert(payload).execute()
                    st.session_state.rapido_rascunho_id = res.data[0]['id']
                
                st.success("✅ Cálculo salvo com sucesso! Você pode continuar editando ou criar um novo.")
                deve_rerun = True

    return deve_rerun
