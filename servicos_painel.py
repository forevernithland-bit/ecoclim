import streamlit as st
import pandas as pd
import datetime
import utils
import traceback
import gestao_click
import push
import movimentacoes

def safe_float(val):
    try:
        if pd.isna(val) or val is None or str(val).strip() == '': 
            return 0.0
        if isinstance(val, str):
            val = val.replace('R$', '').replace(' ', '').replace(',', '.')
        return float(val)
    except:
        return 0.0

def renderizar_galeria_midias(supabase, midias, permitir_excluir=True):
    """Mostra fotos/vídeos em grade de 3 colunas e áudios em lista embaixo —
    reaproveitado tanto no painel do cliente quanto na notificação de Agenda,
    pra sempre dar pra ver/ouvir o que o instalador anexou sem precisar caçar
    em outro lugar do sistema. Com `permitir_excluir`, cada mídia ganha um
    botão de excluir (apaga do Storage e do registro — não dá pra desfazer)."""
    _url_base = st.secrets["SUPABASE_URL"].rstrip('/')
    _midias_audio = [m for m in midias if m.get('tipo') == 'audio']
    _midias_visuais = [m for m in midias if m.get('tipo') != 'audio']

    def _excluir_midia(m):
        try:
            supabase.storage.from_('instalacao-midias').remove([m['storage_path']])
        except Exception:
            pass  # se já não existir no Storage por algum motivo, remove o registro do mesmo jeito
        try:
            supabase.table('servico_midias').delete().eq('id', m['id']).execute()
            st.success("🗑️ Mídia excluída.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao excluir: {e}")

    _cols_midia = st.columns(3)
    for _i_m, _m in enumerate(_midias_visuais):
        _url_m = f"{_url_base}/storage/v1/object/public/instalacao-midias/{_m['storage_path']}"
        with _cols_midia[_i_m % 3]:
            if _m.get('tipo') == 'video':
                st.video(_url_m)
            else:
                st.image(_url_m, use_container_width=True)
            if permitir_excluir and st.button("🗑️ Excluir", key=f"del_midia_{_m['id']}", use_container_width=True):
                _excluir_midia(_m)
    for _m in _midias_audio:
        _url_m = f"{_url_base}/storage/v1/object/public/instalacao-midias/{_m['storage_path']}"
        if permitir_excluir:
            _ca, _cb = st.columns([6, 1])
            _ca.audio(_url_m)
            if _cb.button("🗑️", key=f"del_midia_{_m['id']}"):
                _excluir_midia(_m)
        else:
            st.audio(_url_m)


def selecionar_itens_produtos(df_produtos, session_key, itens_iniciais=None):
    """Editor de itens com busca no catálogo de produtos — mesmo motor usado
    no fechamento de Em Andamento/Orçamentos/Finalizados: escolhe o produto
    numa lista (ao invés de digitar à mão), já traz o custo/venda cadastrado,
    calcula o total por linha e o agregado. Reaproveitado também no "Mover
    Cliente para Em Andamento" da Agenda, pra não duplicar essa lógica.
    Retorna (df_itens_final, custo_total, venda_total, lucro_total)."""
    lista_prod = df_produtos['Item'].dropna().tolist() if not df_produtos.empty and 'Item' in df_produtos.columns else []

    colunas_padrao = ['Item', 'Descrição', 'Qtd', 'Custo Un.', 'Venda Un.', 'Custo Total', 'Venda Total']
    itens_json = itens_iniciais or []

    clean_data = []
    if isinstance(itens_json, list):
        for linha in itens_json:
            if isinstance(linha, dict):
                clean_data.append({
                    'Item': str(linha.get('Item', '')),
                    'Descrição': str(linha.get('Descrição', '')),
                    'Qtd': safe_float(linha.get('Qtd', 0)),
                    'Custo Un.': safe_float(linha.get('Custo Un.', 0)),
                    'Venda Un.': safe_float(linha.get('Venda Un.', 0)),
                    'Custo Total': safe_float(linha.get('Custo Total', 0)),
                    'Venda Total': safe_float(linha.get('Venda Total', 0)),
                })

    df_itens = pd.DataFrame(clean_data, columns=colunas_padrao)

    if session_key not in st.session_state:
        if not df_produtos.empty and 'Item' in df_produtos.columns:
            for idx in df_itens.index:
                if safe_float(df_itens.loc[idx, 'Custo Un.']) == 0.0:
                    nome_procurado = str(df_itens.loc[idx, 'Item']).strip().upper()
                    match = df_produtos[df_produtos['Item'].astype(str).str.strip().str.upper() == nome_procurado]
                    if not match.empty:
                        df_itens.loc[idx, 'Custo Un.'] = safe_float(match.iloc[0].get('Custo (R$)', 0))
                if safe_float(df_itens.loc[idx, 'Venda Un.']) == 0.0:
                    nome_procurado = str(df_itens.loc[idx, 'Item']).strip().upper()
                    match = df_produtos[df_produtos['Item'].astype(str).str.strip().str.upper() == nome_procurado]
                    if not match.empty:
                        df_itens.loc[idx, 'Venda Un.'] = safe_float(match.iloc[0].get('Venda (R$)', 0))
        st.session_state[session_key] = df_itens.copy()

    config_itens = {
        "Item": st.column_config.SelectboxColumn("Produto", options=[""] + lista_prod + ["OUTRO"], width="large"),
        "Descrição": st.column_config.TextColumn("Descrição", width="medium"),
        "Qtd": st.column_config.NumberColumn("Qtd", min_value=0, width="small"),
        "Custo Un.": st.column_config.NumberColumn("Custo Fábrica", format="R$ %.2f", width="small"),
        "Venda Un.": st.column_config.NumberColumn("Venda Unt.", format="R$ %.2f", width="small"),
        "Custo Total": st.column_config.NumberColumn("Custo Total", format="R$ %.2f", disabled=True, width="small"),
        "Venda Total": st.column_config.NumberColumn("Venda Total", format="R$ %.2f", disabled=True, width="small"),
    }

    df_itens_editavel = st.data_editor(
        st.session_state[session_key],
        column_config=config_itens,
        column_order=colunas_padrao,
        num_rows="dynamic",
        use_container_width=True,
        key=f"edit_{session_key}",
    )

    precisa_atualizar = False
    for idx in df_itens_editavel.index:
        item_atual = str(df_itens_editavel.loc[idx, 'Item']).strip() if 'Item' in df_itens_editavel.columns and pd.notna(df_itens_editavel.loc[idx, 'Item']) else ""
        item_ant = ""
        if idx in st.session_state[session_key].index:
            item_ant = str(st.session_state[session_key].loc[idx, 'Item']).strip() if 'Item' in st.session_state[session_key].columns and pd.notna(st.session_state[session_key].loc[idx, 'Item']) else ""

        if item_atual != item_ant and item_atual != "" and item_atual != "OUTRO":
            if not df_produtos.empty and 'Item' in df_produtos.columns:
                match = df_produtos[df_produtos['Item'].astype(str).str.strip().str.upper() == item_atual.upper()]
                if not match.empty:
                    df_itens_editavel.loc[idx, 'Custo Un.'] = safe_float(match.iloc[0].get('Custo (R$)', 0))
                    df_itens_editavel.loc[idx, 'Venda Un.'] = safe_float(match.iloc[0].get('Venda (R$)', 0))
                    qtd_atual = df_itens_editavel.loc[idx, 'Qtd'] if 'Qtd' in df_itens_editavel.columns else 0
                    if pd.isna(qtd_atual) or safe_float(qtd_atual) <= 0:
                        df_itens_editavel.loc[idx, 'Qtd'] = 1
                    precisa_atualizar = True

        qtd_calc = safe_float(df_itens_editavel.loc[idx, 'Qtd']) if 'Qtd' in df_itens_editavel.columns else 0.0
        c_un_calc = safe_float(df_itens_editavel.loc[idx, 'Custo Un.']) if 'Custo Un.' in df_itens_editavel.columns else 0.0
        v_un_calc = safe_float(df_itens_editavel.loc[idx, 'Venda Un.']) if 'Venda Un.' in df_itens_editavel.columns else 0.0

        tot_c = qtd_calc * c_un_calc
        tot_v = qtd_calc * v_un_calc

        c_tot_atual = safe_float(df_itens_editavel.loc[idx, 'Custo Total']) if 'Custo Total' in df_itens_editavel.columns else 0.0
        v_tot_atual = safe_float(df_itens_editavel.loc[idx, 'Venda Total']) if 'Venda Total' in df_itens_editavel.columns else 0.0

        if abs(tot_c - c_tot_atual) > 0.01 or abs(tot_v - v_tot_atual) > 0.01:
            df_itens_editavel.loc[idx, 'Custo Total'] = tot_c
            df_itens_editavel.loc[idx, 'Venda Total'] = tot_v
            precisa_atualizar = True

    if precisa_atualizar:
        st.session_state[session_key] = df_itens_editavel
        if f"edit_{session_key}" in st.session_state:
            del st.session_state[f"edit_{session_key}"]
        st.rerun()

    df_itens_final = df_itens_editavel
    custo_total = pd.to_numeric(df_itens_final['Custo Total'], errors='coerce').fillna(0).sum() if 'Custo Total' in df_itens_final.columns else 0.0
    venda_total = pd.to_numeric(df_itens_final['Venda Total'], errors='coerce').fillna(0).sum() if 'Venda Total' in df_itens_final.columns else 0.0
    lucro_total = venda_total - custo_total
    return df_itens_final, custo_total, venda_total, lucro_total


def montar_itens_material(supabase, catalogo_mat, opcoes_catalogo, chave_itens):
    """UI reaproveitável pra montar uma lista de itens de material — colar
    texto do WhatsApp (interpretado contra o catálogo), buscar no catálogo,
    ou digitar manual. Escreve direto em st.session_state[chave_itens]
    (lista de {item, qtd, unidade, categoria}); quem chama inicializa essa
    chave antes e desenha o data_editor final + botão de salvar (o que se
    salva muda conforme o caso: lista de cliente x lista padrão)."""
    chave_pendentes = f"pendentes_whats_{chave_itens}"
    if chave_pendentes not in st.session_state:
        st.session_state[chave_pendentes] = []

    st.markdown("###### 📋 Colar lista do WhatsApp")
    st.caption("Cole aqui o texto que o instalador manda no WhatsApp. O sistema tenta achar cada item no catálogo e já preenche a quantidade — o que não reconhecer, pergunta pra você escolher.")
    texto_whats = st.text_area(
        "Cole aqui a lista", key=f"texto_whats_{chave_itens}", height=140,
        placeholder="Material Água Quente - CPVC\n2 joelhos cpvc 22mm 90°\n3 conectores 22x3/4\n...",
    )
    if st.button("🔍 Interpretar lista", key=f"btn_interpretar_whats_{chave_itens}"):
        _reconhecidos, _nao_reconhecidos = utils.interpretar_lista_whatsapp(texto_whats, catalogo_mat)
        st.session_state[chave_itens].extend(_reconhecidos)
        st.session_state[chave_pendentes] = _nao_reconhecidos
        if _reconhecidos:
            st.success(f"{len(_reconhecidos)} item(ns) reconhecido(s) e adicionado(s) à lista abaixo.")
        if _nao_reconhecidos:
            st.warning(f"{len(_nao_reconhecidos)} item(ns) eu não reconheci — escolha abaixo o que cada um é.")
        if not _reconhecidos and not _nao_reconhecidos:
            st.info("Não achei nenhuma linha com quantidade + item nesse texto.")
        st.rerun()

    if st.session_state[chave_pendentes]:
        st.markdown("**❓ Não reconheci estes itens — escolha manualmente:**")
        _opcoes_pendente = ["-- escolher no catálogo --"] + list(opcoes_catalogo.keys())
        _pendentes_restantes = []
        for _i, _p in enumerate(st.session_state[chave_pendentes]):
            with st.container(border=True):
                st.caption(f"Texto original: \"{_p['qtd']} {_p['texto_original']}\"")
                _escolha = st.selectbox("O que é este item?", _opcoes_pendente, key=f"whats_pend_sel_{chave_itens}_{_i}")
                _col_ok, _col_manual = st.columns(2)
                _confirmado = False
                if _col_ok.button("✅ Usar este", key=f"whats_pend_ok_{chave_itens}_{_i}", disabled=(_escolha == "-- escolher no catálogo --")):
                    _c = opcoes_catalogo[_escolha]
                    st.session_state[chave_itens].append({"item": _c['item'], "qtd": _p['qtd'], "unidade": _c.get('unidade', 'un'), "categoria": _c.get('categoria')})
                    _confirmado = True
                if _col_manual.button("📝 Manter como veio", key=f"whats_pend_manual_{chave_itens}_{_i}"):
                    st.session_state[chave_itens].append({"item": _p['texto_original'], "qtd": _p['qtd'], "unidade": "un", "categoria": None})
                    utils.sugerir_novo_material(supabase, _p['texto_original'])
                    st.toast(f"\"{_p['texto_original']}\" não está no catálogo — adicionado mesmo assim, e já registrado pro Breno avaliar incluir.", icon="⚠️")
                    _confirmado = True
                if not _confirmado:
                    _pendentes_restantes.append(_p)
        if len(_pendentes_restantes) != len(st.session_state[chave_pendentes]):
            st.session_state[chave_pendentes] = _pendentes_restantes
            st.rerun()

    st.markdown("###### 🔎 Ou busque item por item")
    col_cat, col_man = st.columns(2)
    with col_cat:
        sel_catalogo = st.multiselect(
            "Buscar no catálogo", options=list(opcoes_catalogo.keys()),
            key=f"multisel_{chave_itens}",
        )
        if st.button("➕ Adicionar selecionados", key=f"btn_add_sel_{chave_itens}"):
            for _label in sel_catalogo:
                _c = opcoes_catalogo[_label]
                st.session_state[chave_itens].append({"item": _c['item'], "qtd": 1, "unidade": _c.get('unidade', 'un'), "categoria": _c.get('categoria')})
            del st.session_state[f"multisel_{chave_itens}"]
            st.rerun()
    with col_man:
        _item_manual = st.text_input("Ou item manual (fora do catálogo)", key=f"input_manual_{chave_itens}")
        if st.button("➕ Adicionar item manual", key=f"btn_add_manual_{chave_itens}") and _item_manual.strip():
            st.session_state[chave_itens].append({"item": _item_manual.strip(), "qtd": 1, "unidade": "un", "categoria": None})
            utils.sugerir_novo_material(supabase, _item_manual.strip())
            st.toast(f"\"{_item_manual.strip()}\" não está no catálogo — adicionado mesmo assim, e já registrado pro Breno avaliar incluir.", icon="⚠️")
            st.rerun()


def exibir_painel_detalhado(projeto_selecionado, supabase, df_taxas_config, df_produtos, prefix_key, lista_instaladores):
    # =========================================================================
    # ARMADURA ANTI-CRASH GLOBAL DO PAINEL
    # =========================================================================
    try:
        st.markdown("---")
        st.markdown(f"### ⚙️ Detalhes e Fechamento")
        
        id_projeto = int(projeto_selecionado.get('id', 0))

        aba_eq, aba_fiscal, aba_midia, aba_mat = st.tabs(["🛠️ Equipamento/Serviços", "🧾 Fiscal/Boletos", "📷 Mídia/Fotos/Contrato", "📋 Lista de Materiais"])

        with aba_eq:
            c_cad1, c_cad2 = st.columns(2)
            novo_nome_cliente = c_cad1.text_input("Nome do Cliente", value=str(projeto_selecionado.get('nome_cliente', 'Sem Nome')), key=f"edit_nome_{prefix_key}")
            novo_tel_cliente = c_cad2.text_input("Telefone / WhatsApp", value=str(projeto_selecionado.get('telefone_cliente', '')), key=f"edit_tel_{prefix_key}")
            _end_banco = str(projeto_selecionado.get('endereco_cliente', '') or '')
            novo_endereco_cliente = st.text_input("Endereço (opcional)", value='' if _end_banco.lower() in ('nan', 'none') else _end_banco,
                                                  placeholder="Rua, número, bairro, cidade - UF", key=f"edit_end_{prefix_key}")
            _bairro_banco = str(projeto_selecionado.get('bairro_cliente', '') or '')
            novo_bairro_cliente = st.text_input("Bairro", value='' if _bairro_banco.lower() in ('nan', 'none') else _bairro_banco,
                                                placeholder="Ex: Duquesa I", key=f"edit_bairro_{prefix_key}",
                                                help="Aparece junto do nome nas telas do instalador, pra ficar mais fácil de identificar qual instalação é qual.")
            _cpf_banco = str(projeto_selecionado.get('cpf_cnpj_cliente', '') or '')
            if _cpf_banco.lower() in ('nan', 'none', ''):
                # Já tem CPF preenchido de quando gerou um Contrato pra esse
                # cliente? Aproveita como valor inicial em vez de pedir de novo.
                _d_ct_fallback_cpf = projeto_selecionado.get('dados_contrato')
                _cpf_banco = (_d_ct_fallback_cpf or {}).get('cpf', '') if isinstance(_d_ct_fallback_cpf, dict) else ''
            novo_cpf_cliente = st.text_input("CPF/CNPJ", value=_cpf_banco, placeholder="000.000.000-00",
                                             key=f"edit_cpf_{prefix_key}",
                                             help="Usado pra emitir Nota Fiscal (contrato e futura integração com o Gestão Click).")
        
            col_esq, col_meio, col_dir = st.columns(3)
        
            status_atual = projeto_selecionado.get('status_projeto', 'Orçamento Enviado')
            if status_atual == "Cancelado": status_atual = "Orçamento Cancelado"
            if status_atual == "Aguardando Peças": status_atual = "Aguardando Pagamento"

            todas_opcoes = [
                "Orçamento Enviado", "Orçamento Cancelado", "Em Andamento", 
                "Aguardando Pagamento", "Concluído PIX", "Concluído CARTÃO", "Excluir"
            ]
            novo_status = col_esq.selectbox("Alterar Status", todas_opcoes, index=todas_opcoes.index(status_atual) if status_atual in todas_opcoes else 0, key=f"status_{prefix_key}")
        
            data_banco = projeto_selecionado.get('data_conclusao')
            data_inicial = datetime.date.today()
            if pd.notna(data_banco) and str(data_banco).lower() not in ['none', 'nan', 'nat', '']:
                try: data_inicial = pd.to_datetime(data_banco).date()
                except: pass

            if f"last_status_{prefix_key}" not in st.session_state:
                st.session_state[f"last_status_{prefix_key}"] = status_atual

            if f"data_edit_{prefix_key}" not in st.session_state:
                st.session_state[f"data_edit_{prefix_key}"] = data_inicial

            if novo_status != st.session_state[f"last_status_{prefix_key}"]:
                if novo_status in ["Concluído PIX", "Concluído CARTÃO"] and st.session_state[f"last_status_{prefix_key}"] not in ["Concluído PIX", "Concluído CARTÃO"]:
                    hoje = datetime.date.today()
                    st.session_state[f"data_edit_{prefix_key}"] = hoje
                    st.session_state[f"data_{prefix_key}"] = hoje
                
                st.session_state[f"last_status_{prefix_key}"] = novo_status
                st.rerun()

            label_data = "Data de Término" if novo_status in ["Concluído PIX", "Concluído CARTÃO"] else "Data de Inclusão / Previsão"
        
            nova_data = col_meio.date_input(label_data, value=st.session_state[f"data_edit_{prefix_key}"], format="DD/MM/YYYY", key=f"data_{prefix_key}")
        
            st.session_state[f"data_edit_{prefix_key}"] = nova_data

            instalador_atual = str(projeto_selecionado.get('instalador', ''))
            if instalador_atual.lower() in ['nan', 'none']: instalador_atual = ""
        
            opcoes_inst = [""] + lista_instaladores
            idx_inst = opcoes_inst.index(instalador_atual) if instalador_atual in opcoes_inst else 0
            novo_instalador = col_dir.selectbox("Instalador Responsável", opcoes_inst, index=idx_inst, key=f"inst_{prefix_key}")

            st.markdown("#### 🛒 Itens Vendidos (Ajuste Quantidades e Custos)")

            df_itens_final, custo_total_produtos, venda_total_produtos, lucro_total_produtos = selecionar_itens_produtos(
                df_produtos, f"itens_state_{prefix_key}", projeto_selecionado.get('detalhamento_itens', [])
            )

            st.markdown(f"""
                <div style='display: flex; justify-content: flex-end; gap: 25px; margin-top: -10px; margin-bottom: 25px;'>
                    <span style='color: #cc0000; font-size: 15px;'><b>Custo Total Produtos:</b> {utils.to_br_currency(custo_total_produtos)}</span>
                    <span style='color: #006600; font-size: 15px;'><b>Lucro Total Produtos:</b> {utils.to_br_currency(lucro_total_produtos)}</span>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("#### 🧮 Abatimentos e Impostos")
            with st.container(border=True):
                f_col1, f_col2 = st.columns(2)
                venda_final = f_col1.number_input("Valor da Venda (R$)", value=safe_float(projeto_selecionado.get('valor_venda_total')), format="%.2f", step=None, key=f"venda_{prefix_key}")
                f_col1.caption(f"Custo Produtos: - {utils.to_br_currency(custo_total_produtos)}")

                emite_nf = f_col2.radio("Nota Fiscal?", ["Não", "Sim"], index=1 if safe_float(projeto_selecionado.get('custo_impostos')) > 0 else 0, key=f"nf_{prefix_key}")
                valor_nf = 0.0
                if emite_nf == "Sim":
                    taxa_nf_pct = 6.0
                    if not df_taxas_config.empty:
                        for _, t_row in df_taxas_config.iterrows():
                            if "NOTA FISCAL" in str(t_row.get('Item', '')).upper() or "NF" in str(t_row.get('Item', '')).upper():
                                taxa_nf_pct = safe_float(t_row.get('Taxa (%)'))
                                break
                    valor_nf = venda_final * (taxa_nf_pct / 100)
                    f_col2.caption(f"Imposto ({taxa_nf_pct}%): - {utils.to_br_currency(valor_nf)}")
                else:
                    f_col2.caption("&nbsp;", unsafe_allow_html=True)

                opcoes_cartao = ["Nenhum / Dinheiro / PIX"]
                dict_taxas = {"Nenhum / Dinheiro / PIX": 0.0}

                if not df_taxas_config.empty:
                    for _, t_row in df_taxas_config.iterrows():
                        item_nome = str(t_row.get('Item', '')).strip()
                        taxa_val = safe_float(t_row.get('Taxa (%)', 0.0))
                        if "NF" not in item_nome.upper() and "NOTA FISCAL" not in item_nome.upper() and item_nome != "":
                            opcoes_cartao.append(item_nome)
                            dict_taxas[item_nome] = taxa_val

                custo_c_salvo = safe_float(projeto_selecionado.get('custo_cartao'))
                perc_previo = (custo_c_salvo / venda_final * 100) if venda_final > 0 else 0.0

                # -----------------------------------------------------------
                # Pagamentos recebidos — antes era UM percentual de cartão pra
                # venda inteira. Na prática o cliente costuma dividir (ex.:
                # metade PIX, metade cartão) e pagar em etapas (entrada na
                # assinatura, resto na entrega) — um percentual único cobrava
                # taxa de cartão em cima de dinheiro que nunca passou no
                # cartão, e não sobrava registro de quanto já tinha entrado
                # de entrada. Cada linha aqui é um recebimento de verdade —
                # forma + valor (+ data/obs opcionais, ex. "Entrada"). A taxa
                # de cartão final é a soma só das linhas cuja forma tem taxa
                # (PIX/Dinheiro ficam em 0, igual antes).
                # -----------------------------------------------------------
                session_pag_key = f"pagamentos_{prefix_key}"
                if session_pag_key not in st.session_state:
                    pagamentos_salvos = projeto_selecionado.get('pagamentos_recebidos')
                    if isinstance(pagamentos_salvos, list) and pagamentos_salvos:
                        linhas_pag = [{
                            "Forma": p.get('forma') if p.get('forma') in dict_taxas else opcoes_cartao[0],
                            "Valor (R$)": safe_float(p.get('valor')),
                            "Data": p.get('data'),
                            "Obs": p.get('obs') or "",
                        } for p in pagamentos_salvos]
                    elif custo_c_salvo > 0 or venda_final > 0:
                        # Migra o registro antigo (uma taxa só, pra venda inteira)
                        # pra uma primeira linha, em vez de simplesmente sumir.
                        _forma_antiga = opcoes_cartao[0]
                        for _opt in opcoes_cartao:
                            if abs(dict_taxas[_opt] - perc_previo) < 0.01:
                                _forma_antiga = _opt
                                break
                        linhas_pag = [{"Forma": _forma_antiga, "Valor (R$)": venda_final, "Data": None, "Obs": ""}]
                    else:
                        linhas_pag = [{"Forma": opcoes_cartao[0], "Valor (R$)": 0.0, "Data": None, "Obs": ""}]
                    st.session_state[session_pag_key] = pd.DataFrame(linhas_pag, columns=["Forma", "Valor (R$)", "Data", "Obs"])

                st.markdown("**💳 Pagamentos Recebidos**")
                st.caption("Uma linha por recebimento — se o cliente pagou parte em PIX e parte no cartão, ou pagou entrada e o resto depois, lance cada um separado. Assim a taxa de cartão é cobrada só em cima do que realmente foi pago com cartão, e fica registrado quanto já entrou (útil pra lembrar o valor da entrada lá na frente).")
                config_pag = {
                    "Forma": st.column_config.SelectboxColumn("Forma de Pagamento", options=opcoes_cartao, width="medium", required=True),
                    "Valor (R$)": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", min_value=0.0, width="small"),
                    "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", width="small"),
                    "Obs": st.column_config.TextColumn("Obs (ex: Entrada, Parcela final)", width="medium"),
                }
                df_pagamentos_ed = st.data_editor(
                    st.session_state[session_pag_key], column_config=config_pag, num_rows="dynamic",
                    hide_index=True, use_container_width=True, key=f"edit_pag_{prefix_key}",
                )
                st.session_state[session_pag_key] = df_pagamentos_ed

                valor_cartao_taxa = 0.0
                total_recebido = 0.0
                lista_pagamentos_salvar = []
                for _, _linha_pag in df_pagamentos_ed.iterrows():
                    _forma_pag = str(_linha_pag.get('Forma') or '').strip()
                    _valor_pag = safe_float(_linha_pag.get('Valor (R$)'))
                    if not _forma_pag and _valor_pag == 0:
                        continue
                    total_recebido += _valor_pag
                    valor_cartao_taxa += _valor_pag * (dict_taxas.get(_forma_pag, 0.0) / 100)
                    _data_pag = _linha_pag.get('Data')
                    lista_pagamentos_salvar.append({
                        "forma": _forma_pag,
                        "valor": _valor_pag,
                        "data": _data_pag.strftime('%Y-%m-%d') if pd.notna(_data_pag) and hasattr(_data_pag, 'strftime') else None,
                        "obs": str(_linha_pag.get('Obs') or ''),
                    })

                falta_receber = venda_final - total_recebido
                c_rec1, c_rec2, c_rec3 = st.columns(3)
                c_rec1.metric("💰 Total já recebido", utils.to_br_currency(total_recebido))
                c_rec2.metric("⏳ Falta receber", utils.to_br_currency(falta_receber))
                c_rec3.metric("💳 Taxa de cartão (proporcional)", utils.to_br_currency(valor_cartao_taxa))

                st.markdown("---")
                f_col4, f_col5, f_col6 = st.columns(3)
            
                perc_comissao_salvo = (safe_float(projeto_selecionado.get('custo_comissao')) / venda_final * 100) if venda_final > 0 else 0.0
                comissao_pct = f_col4.number_input("Comissão (%)", value=float(perc_comissao_salvo), format="%.1f", step=None, key=f"com_{prefix_key}")
                valor_comissao = venda_final * (comissao_pct / 100)
                f_col4.caption(f"Valor: - {utils.to_br_currency(valor_comissao)}")

                d_ct_fallback = projeto_selecionado.get('dados_contrato')
                if not isinstance(d_ct_fallback, dict): d_ct_fallback = {}
            
                val_mo_salvo = safe_float(projeto_selecionado.get('custo_terceirizados'))
                if val_mo_salvo == 0.0 and safe_float(d_ct_fallback.get('val_servico')) > 0:
                    val_mo_salvo = safe_float(d_ct_fallback.get('val_servico'))
                
                val_ext_salvo = safe_float(projeto_selecionado.get('custo_adicional_materiais'))
                if val_ext_salvo == 0.0 and safe_float(d_ct_fallback.get('val_outros')) > 0:
                    val_ext_salvo = safe_float(d_ct_fallback.get('val_outros'))

                custo_ext = f_col5.number_input("Materiais Extras (R$)", value=val_ext_salvo, format="%.2f", step=None, key=f"mat_{prefix_key}")
                f_col5.caption("&nbsp;", unsafe_allow_html=True) 

                custo_mo = f_col6.number_input("Mão de Obra / Terceiros (R$)", value=val_mo_salvo, format="%.2f", step=None, key=f"mao_{prefix_key}")
                f_col6.caption("&nbsp;", unsafe_allow_html=True)

                # Financeiro do instalador — "Mão de Obra / Terceiros" acima É o
                # "Valor Instalação" que o app do instalador mostra. Aqui só
                # marca se já foi pago a ele (alimenta a aba Financeiro do PWA).
                f_pago1, f_pago2 = st.columns([1, 2])
                pago_instalador_salvo = bool(projeto_selecionado.get('pago_instalador', False))
                novo_pago_instalador = f_pago1.checkbox("💰 Pago ao instalador", value=pago_instalador_salvo, key=f"pago_inst_{prefix_key}")
                data_pag_inst_banco = projeto_selecionado.get('data_pagamento_instalador')
                data_pag_inst_inicial = datetime.date.today()
                if pd.notna(data_pag_inst_banco) and str(data_pag_inst_banco).lower() not in ('none', 'nan', 'nat', ''):
                    try: data_pag_inst_inicial = pd.to_datetime(data_pag_inst_banco).date()
                    except Exception: pass
                if novo_pago_instalador:
                    nova_data_pag_inst = f_pago2.date_input("Data do pagamento", value=data_pag_inst_inicial, format="DD/MM/YYYY", key=f"data_pago_inst_{prefix_key}")
                else:
                    nova_data_pag_inst = None

                abatimentos = valor_nf + valor_cartao_taxa + valor_comissao + custo_ext + custo_mo
                lucro_equipamento_servico = venda_final - custo_total_produtos - abatimentos

                # Lucro de materiais hidráulicos vendidos com a Ecoclim neste
                # serviço (botão "Adquirir materiais" na aba Lista de
                # Materiais) — somado sempre a partir de vendas_materiais, não
                # um campo acumulador solto, pra nunca dessincronizar do que
                # foi de fato registrado.
                try:
                    res_vendas_mat_lucro = supabase.table('vendas_materiais').select('lucro_total').eq('servico_id', id_projeto).execute()
                    lucro_materiais_hidraulicos = sum(float(v.get('lucro_total') or 0) for v in (res_vendas_mat_lucro.data or []))
                except Exception:
                    lucro_materiais_hidraulicos = 0.0

                lucro_final = lucro_equipamento_servico + lucro_materiais_hidraulicos

                st.markdown("<br>", unsafe_allow_html=True)
                r1, r2 = st.columns(2)
                r1.metric("Custo Total (Produtos + Taxas)", utils.to_br_currency(custo_total_produtos + abatimentos))
                margem_r = (lucro_final / venda_final * 100) if venda_final > 0 else 0
                r2.metric("LUCRO LÍQUIDO FINAL", utils.to_br_currency(lucro_final), delta=f"{margem_r:.1f}% Margem")
                r3, r4 = st.columns(2)
                r3.metric("Lucro Equipamento/Serviço", utils.to_br_currency(lucro_equipamento_servico))
                r4.metric("💧 Lucro Materiais Hidráulicos", utils.to_br_currency(lucro_materiais_hidraulicos))

            # ---------------------------------------------------------------
            # Reportado pelo Instalador (app do instalador) — só leitura aqui.
            # Ajustes são feitos direto no orçamento/painel, não por este campo.
            # ---------------------------------------------------------------
            _concluida_inst = bool(projeto_selecionado.get('instalacao_concluida_instalador', False))
            _obs_inst = str(projeto_selecionado.get('observacao_instalador', '') or '').strip()
            if _obs_inst.lower() in ('nan', 'none'): _obs_inst = ''
            if _concluida_inst or _obs_inst:
                with st.container(border=True):
                    st.markdown("##### 📲 Reportado pelo Instalador")
                    if _concluida_inst:
                        _data_ci = projeto_selecionado.get('data_conclusao_instalador')
                        _data_ci_str = ""
                        try:
                            if pd.notna(_data_ci) and str(_data_ci).lower() not in ('none', 'nan', 'nat', ''):
                                _data_ci_str = pd.to_datetime(_data_ci).strftime('%d/%m/%Y')
                        except Exception:
                            pass
                        st.success(f"✅ Instalação marcada como concluída pelo instalador{f' em {_data_ci_str}' if _data_ci_str else ''}.")
                    if _obs_inst:
                        st.caption("Observação do instalador:")
                        st.markdown(f"> {_obs_inst}")

            # ---------------------------------------------------------------
            # Garantia — a contagem começa, por padrão, no dia em que o
            # instalador marca "concluída" pelo app. Editável aqui pra casos
            # como obra em construção, onde o cliente pede pra garantia só
            # começar quando ele se mudar pra casa.
            # ---------------------------------------------------------------
            nova_data_garantia = None
            _garantia_banco = projeto_selecionado.get('data_inicio_garantia')
            _tem_garantia_salva = pd.notna(_garantia_banco) and str(_garantia_banco).lower() not in ('none', 'nan', 'nat', '')
            # Só mostra depois que existe algum sinal real de conclusão — nunca
            # antes disso, pra não carimbar a data de hoje num serviço que ainda
            # está "Em Andamento" só porque o painel foi salvo por outro motivo.
            _tem_sinal_conclusao = (
                bool(projeto_selecionado.get('instalacao_concluida_instalador', False))
                or str(projeto_selecionado.get('status_projeto', '')) in ('Concluído PIX', 'Concluído CARTÃO')
                or _tem_garantia_salva
            )
            if _tem_sinal_conclusao:
                with st.container(border=True):
                    st.markdown("##### 🛡️ Garantia")
                    _garantia_inicial = None
                    if _tem_garantia_salva:
                        try: _garantia_inicial = pd.to_datetime(_garantia_banco).date()
                        except Exception: pass
                    if _garantia_inicial is None:
                        for _fallback in (projeto_selecionado.get('data_conclusao_instalador'), projeto_selecionado.get('data_conclusao')):
                            if pd.notna(_fallback) and str(_fallback).lower() not in ('none', 'nan', 'nat', ''):
                                try:
                                    _garantia_inicial = pd.to_datetime(_fallback).date()
                                    break
                                except Exception:
                                    pass
                    if _garantia_inicial is None:
                        _garantia_inicial = datetime.date.today()
                    nova_data_garantia = st.date_input(
                        "Início da contagem da garantia", value=_garantia_inicial, format="DD/MM/YYYY",
                        key=f"garantia_{prefix_key}",
                        help="Padrão: dia em que o instalador marcou como concluída. Ajuste aqui se o cliente pediu pra garantia começar em outra data (ex.: casa em construção, garantia só a partir da mudança).")
                    st.caption("Salvo junto com o botão 💾 SALVAR PROJETO, no final da página.")


        with aba_fiscal:
            nova_nf_entrada = ""
            novo_venc_boleto = None
            pago_avista = bool(projeto_selecionado.get('pago_avista_fornecedor', False))

            if novo_status not in ["Orçamento Enviado", "Orçamento Cancelado", "Excluir"]:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("#### 🧾 Informações Fiscais e Boletos")
            
                c_nf, c_venc = st.columns(2)
            
                nf_entrada_banco = projeto_selecionado.get('nf_entrada', '')
                venc_boleto_banco = projeto_selecionado.get('vencimento_boleto')
            
                pago_avista_banco = bool(projeto_selecionado.get('pago_avista_fornecedor', False))
                venc_boleto_inicial = None
                if pd.notna(venc_boleto_banco) and str(venc_boleto_banco).lower() not in ['none', 'nan', 'nat', '']:
                    try: venc_boleto_inicial = pd.to_datetime(venc_boleto_banco).date()
                    except: pass

                try:
                    res_bol_check = supabase.table('boletos_fornecedores').select('*').eq('servico_id', id_projeto).execute()
                    boletos_importados = res_bol_check.data
                except:
                    boletos_importados = []
                
                if boletos_importados and venc_boleto_inicial is None:
                    try:
                        venc_b_temp = boletos_importados[0].get('vencimento')
                        if venc_b_temp:
                            venc_boleto_inicial = pd.to_datetime(venc_b_temp).date()
                    except:
                        pass
            
                nova_nf_entrada = c_nf.text_input("NF de Entrada", value=str(nf_entrada_banco) if str(nf_entrada_banco) != 'nan' else '', placeholder="Opcional", key=f"nf_ent_{prefix_key}")
                pago_avista = c_venc.checkbox("✅ Pago à vista (equipamento já pago)", value=pago_avista_banco, key=f"avista_{prefix_key}")
                if pago_avista:
                    c_venc.caption("Sem vencimento — marcado como pago à vista.")
                    novo_venc_boleto = None
                else:
                    novo_venc_boleto = c_venc.date_input("Vencimento Boleto (Cliente)", value=venc_boleto_inicial, format="DD/MM/YYYY", key=f"venc_bol_{prefix_key}")

                with st.container(border=True):
                    st.markdown("##### 📥 Importar Boleto de Fornecedor (PDF)")
                
                    if boletos_importados:
                        st.success(f"✅ {len(boletos_importados)} boleto(s) de fornecedor(es) já importado(s).")
                        for i_bol, b_imp in enumerate(boletos_importados):
                            dt_str = "Sem data"
                            try: 
                                dt_b = pd.to_datetime(b_imp.get('vencimento'))
                                if pd.notna(dt_b): dt_str = dt_b.strftime('%d/%m/%Y')
                            except: pass
                        
                            val_str = utils.to_br_currency(b_imp.get('valor', 0))
                            link = b_imp.get('link_drive_id', '')
                            b_id = b_imp.get('id', f'desc_{i_bol}')
                        
                            c_bol1, c_bol2 = st.columns([4, 1])
                            with c_bol1:
                                if link:
                                    st.markdown(f"📄 **Venc:** {dt_str} | **Valor:** {val_str} | <a href='https://drive.google.com/file/d/{link}/view' target='_blank'>👁️ Ver PDF</a>", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"📄 **Venc:** {dt_str} | **Valor:** {val_str}")
                            with c_bol2:
                                if st.button("🗑️ Remover", key=f"del_bol_{b_id}_{prefix_key}"):
                                    try:
                                        supabase.table('boletos_fornecedores').delete().eq('id', b_id).execute()
                                        if link: utils.delete_drive_file(link)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao remover: {e}")
                        st.markdown("---")
                
                    upload_key = f"up_bol_k_{prefix_key}"
                    if upload_key not in st.session_state:
                        st.session_state[upload_key] = 0
                    
                    arquivo_boleto = st.file_uploader("Anexar PDF do Boleto para leitura de IA", type=["pdf"], key=f"up_bol_{prefix_key}_{st.session_state[upload_key]}")
                
                    if arquivo_boleto:
                        if f"dados_bol_{prefix_key}" not in st.session_state:
                            with st.spinner("🤖 Lendo dados do boleto..."):
                                venc_ext, val_ext = utils.extrair_dados_boleto(arquivo_boleto)
                                st.session_state[f"dados_bol_{prefix_key}"] = {"vencimento": venc_ext, "valor": val_ext}

                        dados_ext = st.session_state[f"dados_bol_{prefix_key}"]
                    
                        st.caption("Verifique e corrija os dados extraídos pelo sistema:")
                        col_b1, col_b2 = st.columns(2)
                    
                        venc_obj = datetime.date.today()
                        if dados_ext['vencimento']:
                            try: venc_obj = datetime.datetime.strptime(dados_ext['vencimento'], "%d/%m/%Y").date()
                            except: pass
                    
                        data_confirmada = col_b1.date_input("Vencimento do Fornecedor", value=venc_obj, format="DD/MM/YYYY", key=f"conf_data_{prefix_key}")
                        valor_confirmado = col_b2.number_input("Valor Extraído (R$)", value=float(dados_ext['valor']), format="%.2f", step=None, key=f"conf_val_{prefix_key}")
                    
                        if st.button("🚀 Salvar Boleto e Criar Lembrete", type="primary", use_container_width=True, key=f"btn_salvar_bol_{prefix_key}"):
                            with st.spinner("Salvando no Drive e no ERP..."):
                                mes_idx = data_confirmada.month
                                nome_mes_pasta = utils.meses_pt[mes_idx - 1]
                            
                                nome_cliente_limpo = novo_nome_cliente.split()[0] if novo_nome_cliente else "Cliente"
                                timestamp_str = datetime.datetime.now().strftime('%H%M%S')
                                nome_arquivo_drive = f"FORNECEDOR_{nome_cliente_limpo}_{data_confirmada.strftime('%d%m%Y')}_{timestamp_str}.pdf"
                            
                                arquivo_boleto.seek(0)
                            
                                sucesso, link_id = utils.upload_to_drive(
                                    file_buffer=arquivo_boleto, 
                                    filename=nome_arquivo_drive, 
                                    mimetype="application/pdf", 
                                    folder_path=["Boletos", nome_mes_pasta]
                                )
                            
                                if sucesso:
                                    novo_boleto = {
                                        "cliente": novo_nome_cliente,
                                        "servico_id": id_projeto,
                                        "vencimento": data_confirmada.strftime("%Y-%m-%d"),
                                        "valor": valor_confirmado,
                                        "link_drive_id": link_id,
                                        "status": "Pendente"
                                    }
                                    try:
                                        supabase.table('boletos_fornecedores').insert(novo_boleto).execute()
                                        utils.sincronizar_boletos_com_calendar()
                                    
                                        if pd.isna(venc_boleto_banco) or str(venc_boleto_banco).lower() in ['none', 'nan', 'nat', '']:
                                            supabase.table('servicos_andamento').update({'vencimento_boleto': data_confirmada.strftime('%Y-%m-%d')}).eq('id', id_projeto).execute()
                                    
                                        st.success(f"✅ Boleto salvo com sucesso!")
                                        del st.session_state[f"dados_bol_{prefix_key}"]
                                        st.session_state[upload_key] += 1 
                                        st.rerun() 
                                    except Exception as e:
                                        st.error(f"Erro no banco de dados. Tabela 'boletos_fornecedores' existe? Erro: {e}")
                                else:
                                    st.error(f"Erro ao fazer o upload para o Google Drive. Detalhes: {link_id}")

        with aba_midia:
            # ---------------------------------------------------------------
            # Pasta do cliente no Drive (criada automaticamente ao entrar Em
            # Andamento) + fotos/vídeos que o instalador já enviou. Roda só pro
            # item aberto agora (não a lista inteira), pra não pesar a página.
            # ---------------------------------------------------------------
            _pasta_drive_id, _erro_pasta = utils.garantir_pasta_drive_cliente(projeto_selecionado)
            if _pasta_drive_id:
                _n_sync, _erro_sync = utils.sincronizar_midias_pendentes_drive(id_projeto, _pasta_drive_id)
                st.markdown(
                    f"📁 <a href='https://drive.google.com/drive/folders/{_pasta_drive_id}' target='_blank'>Abrir pasta do cliente no Drive</a>",
                    unsafe_allow_html=True)
                if _erro_sync:
                    st.warning(f"⚠️ Nem todas as fotos/vídeos sincronizaram com o Drive ainda: {_erro_sync}")
            elif _erro_pasta:
                st.warning(f"⚠️ Não deu pra criar a pasta do cliente no Drive: {_erro_pasta}")

            try:
                _res_midias = supabase.table('servico_midias').select('*').eq('servico_id', id_projeto).order('criado_em').execute()
                _midias = _res_midias.data or []
            except Exception:
                _midias = []

            if _midias:
                with st.container(border=True):
                    st.markdown(f"##### 📷 Fotos, Vídeos e Áudios do Instalador ({len(_midias)})")
                    renderizar_galeria_midias(supabase, _midias)

            notas = st.text_area("Observações", value=str(projeto_selecionado.get('notas_internas', '')) if str(projeto_selecionado.get('notas_internas', '')) != 'nan' else '', key=f"notas_{prefix_key}")

            st.markdown("<br>", unsafe_allow_html=True)
        
            with st.expander("📄 GERAR PDF DO ORÇAMENTO"):
                col_pdf1, col_pdf2 = st.columns([1, 1])
                modelo_capa = col_pdf1.selectbox("Modelo para Capa", [
                    "Aquecedor Solar Tradicional", "Aquecedor Solar a Vácuo Acoplado", 
                    "Aquecedor Solar Modular", "Aquecedor de Piscina - Tradicional", 
                    "Aquecedor de Piscina - Trocador de Calor", "Sistema de Pressurização"
                ], index=3, key=f"capa_{prefix_key}")
                detalhar_itens_pdf_srv = st.checkbox("Detalhar valor de cada item no PDF?", value=False,
                                                      help="Desmarcado (padrão): o PDF mostra só o subtotal de Equipamentos, sem preço por item.", key=f"detalhar_itens_pdf_{prefix_key}")

                if col_pdf2.button("GERAR PRÉVIA DO PDF", use_container_width=True, key=f"btn_pdf_{prefix_key}"):
                    df_pdf = df_itens_final.copy()
                    if not df_pdf.empty:
                        df_pdf['Quantidade'] = df_pdf.get('Qtd', 0)
                        df_pdf['Produto da Base'] = df_pdf.get('Item', '')
                        df_pdf['Produto Manual'] = ""
                        df_pdf['Venda Total'] = df_pdf['Quantidade'] * df_pdf.get('Venda Un.', 0)
                        df_pdf['Descrição'] = df_pdf.get('Descrição', "")
                    else:
                        df_pdf = pd.DataFrame(columns=['Quantidade', 'Produto da Base', 'Produto Manual', 'Venda Total', 'Descrição'])
                
                    obs_pdf = str(projeto_selecionado.get('notas_internas', 'Material Hidráulico não incluído na proposta'))
                    if obs_pdf == 'nan' or obs_pdf.strip() == '': obs_pdf = "Material Hidráulico não incluído na proposta"

                    pdf_bytes = utils.gerar_pdf_orcamento(
                        nome=novo_nome_cliente, tel=novo_tel_cliente,
                        capa=modelo_capa, df_items=df_pdf, d_s=str(projeto_selecionado.get('servicos_adquiridos', '')).replace('nan',''),
                        v_s=0.0, d_o="", v_o=0.0, total=safe_float(projeto_selecionado.get('valor_venda_total')), obs=obs_pdf, mostrar_un=False,
                        detalhar_itens=detalhar_itens_pdf_srv
                    )
                    st.session_state[f'pdf_gerado_{prefix_key}'] = pdf_bytes
                
                if f'pdf_gerado_{prefix_key}' in st.session_state:
                    st.download_button("📥 BAIXAR PDF DO ORÇAMENTO", data=st.session_state[f'pdf_gerado_{prefix_key}'], file_name=f"ORCAMENTO_{novo_nome_cliente}.pdf", mime="application/pdf", use_container_width=True, key=f"dl_pdf_{prefix_key}")

            status_contrato_permitido = ["Em Andamento", "Aguardando Pagamento", "Concluído PIX", "Concluído CARTÃO"]
            if novo_status in status_contrato_permitido:
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("📝 GERAR CONTRATO"):
                
                    d_ct = projeto_selecionado.get('dados_contrato')
                    if not isinstance(d_ct, dict): d_ct = {}

                    st.markdown("#### Dados do Cliente para o Contrato")
                    c_tipo = st.radio("Tipo de Cliente", ["Pessoa Física", "Pessoa Jurídica"], horizontal=True, index=0 if d_ct.get('tipo', 'Pessoa Física') == 'Pessoa Física' else 1, key=f"ct_tipo_{prefix_key}")
                    c_nome = st.text_input("Nome Completo / Razão Social", value=d_ct.get('nome', novo_nome_cliente), key=f"ct_nome_{prefix_key}")
                    c_cpf = st.text_input("CPF" if c_tipo == "Pessoa Física" else "CNPJ", value=d_ct.get('cpf', ''), key=f"ct_cpf_{prefix_key}")

                    st.markdown("#### Endereço do Cliente")
                    col_cep1, col_cep2 = st.columns([1, 2])
                
                    if f"ct_rua_{prefix_key}" not in st.session_state: st.session_state[f"ct_rua_{prefix_key}"] = d_ct.get('rua', '')
                    if f"ct_num_{prefix_key}" not in st.session_state: st.session_state[f"ct_num_{prefix_key}"] = d_ct.get('num', '')
                    if f"ct_bairro_{prefix_key}" not in st.session_state: st.session_state[f"ct_bairro_{prefix_key}"] = d_ct.get('bairro', '')
                    if f"ct_cid_{prefix_key}" not in st.session_state: st.session_state[f"ct_cid_{prefix_key}"] = d_ct.get('cidade', '')
                    if f"ct_uf_{prefix_key}" not in st.session_state: st.session_state[f"ct_uf_{prefix_key}"] = d_ct.get('uf', '')

                    c_cep = col_cep1.text_input("CEP", placeholder="00000-000", value=d_ct.get('cep', ''), key=f"ct_cep_{prefix_key}")

                    if col_cep2.button("🔍 Buscar CEP", key=f"btn_cep_{prefix_key}"):
                        end_dados = utils.buscar_cep(c_cep)
                        if end_dados:
                            st.session_state[f"ct_rua_{prefix_key}"] = end_dados.get('logradouro', '')
                            st.session_state[f"ct_bairro_{prefix_key}"] = end_dados.get('bairro', '')
                            st.session_state[f"ct_cid_{prefix_key}"] = end_dados.get('localidade', '')
                            st.session_state[f"ct_uf_{prefix_key}"] = end_dados.get('uf', '')
                            st.rerun() 
                        else:
                            st.error("CEP não encontrado ou inválido.")

                    c_rua = st.text_input("Rua / Logradouro", key=f"ct_rua_{prefix_key}")
                    col_num, col_bairro = st.columns([1, 2])
                    c_num = col_num.text_input("Número", key=f"ct_num_{prefix_key}")
                    c_bairro = col_bairro.text_input("Bairro", key=f"ct_bairro_{prefix_key}")

                    col_cid, col_uf = st.columns([2, 1])
                    c_cidade = col_cid.text_input("Cidade", key=f"ct_cid_{prefix_key}")
                    c_uf = col_uf.text_input("Estado (UF)", key=f"ct_uf_{prefix_key}")

                    st.markdown("#### Estrutura do Contrato")
                    c_objeto = st.text_area("Objeto do Contrato (Opcional)", value=d_ct.get('objeto', ''), height=80, key=f"ct_obj_{prefix_key}")
                    c_mat = st.radio("Materiais Hidráulicos Inclusos na Proposta?", ["Não", "Sim"], index=0 if d_ct.get('mat_inclusos', 'Não') == 'Não' else 1, horizontal=True, key=f"ct_mat_{prefix_key}")
                
                    data_t = datetime.date.today()
                    if d_ct.get('data_termino'):
                        try: data_t = datetime.datetime.strptime(d_ct.get('data_termino'), "%Y-%m-%d").date()
                        except: pass
                    c_data_term = st.date_input("Data de Término do Serviço (Para base da Garantia)", value=data_t, format="DD/MM/YYYY", key=f"ct_term_{prefix_key}")
                
                    st.markdown("#### Valores e Pagamento")
                    col_val1, col_val2 = st.columns(2)
                    c_val_base = col_val1.number_input("Valor Base / Equipamentos (R$)", value=float(d_ct.get('val_base', venda_final)), format="%.2f", step=None, key=f"ct_val_base_{prefix_key}")
                    c_val_inst = col_val2.number_input("Valor da Instalação (R$ - Opcional)", value=float(d_ct.get('val_inst', 0.0)), format="%.2f", step=None, key=f"ct_val_inst_{prefix_key}")
                
                    col_val3, col_val4 = st.columns(2)
                    c_val_hidr = col_val3.number_input("Valor Materiais Hidráulicos (R$ - Opcional)", value=float(d_ct.get('val_hidr', 0.0)), format="%.2f", step=None, key=f"ct_val_hidr_{prefix_key}")
                    c_val_outros = col_val4.number_input("Valor Outros Serviços (R$ - Opcional)", value=float(d_ct.get('val_outros', 0.0)), format="%.2f", step=None, key=f"ct_val_outros_{prefix_key}")
                
                    c_desc_outros = ""
                    if c_val_outros > 0:
                        c_desc_outros = st.text_input("Descrição dos Outros Serviços", value=d_ct.get('desc_outros', ''), key=f"ct_desc_outros_{prefix_key}")

                    lista_pag = ["PIX", "Cartão de Crédito", "Cartão de Débito", "Boleto", "Dinheiro", "Transferência Bancária"]
                    c_pagamento = st.selectbox("Forma de Pagamento Acordada", lista_pag, index=lista_pag.index(d_ct.get('pagamento', 'PIX')), key=f"ct_pag_{prefix_key}")
                    c_obs_pag = st.text_input("Observações do Pagamento (Opcional)", value=d_ct.get('obs_pagamento', ''), key=f"ct_obs_pag_{prefix_key}")

                    total_ct = c_val_base + c_val_inst + c_val_hidr + c_val_outros
                    st.markdown(f"<span style='color:#004488; font-weight:bold;'>Total do Contrato: {utils.to_br_currency(total_ct)}</span>", unsafe_allow_html=True)

                    st.markdown("<br>", unsafe_allow_html=True)
                
                    col_b1, col_b2 = st.columns(2)
                
                    if col_b1.button("💾 SALVAR DADOS DO CONTRATO", use_container_width=True, key=f"btn_sv_ct_{prefix_key}"):
                        payload = {
                            "tipo": c_tipo, "nome": c_nome, "cpf": c_cpf, "cep": c_cep, "rua": c_rua, "num": c_num, 
                            "bairro": c_bairro, "cidade": c_cidade, "uf": c_uf, "objeto": c_objeto, "mat_inclusos": c_mat, 
                            "data_termino": c_data_term.strftime("%Y-%m-%d"), "pagamento": c_pagamento, "obs_pagamento": c_obs_pag, 
                            "val_base": c_val_base, "val_inst": c_val_inst, "val_hidr": c_val_hidr, 
                            "val_outros": c_val_outros, "desc_outros": c_desc_outros
                        }
                        try:
                            supabase.table('servicos_andamento').update({"dados_contrato": payload}).eq('id', id_projeto).execute()
                            st.success("✅ Dados do contrato salvos com sucesso!")
                        except Exception as e:
                            st.error("⚠️ ERRO: Certifique-se de que a coluna 'dados_contrato' existe no Supabase.")

                    if col_b2.button("📄 GERAR PDF DO CONTRATO", type="primary", use_container_width=True, key=f"btn_gerar_pdf_ct_{prefix_key}"):
                        if not c_nome or not c_cpf or not c_rua or not c_num:
                            st.warning("Preencha Nome, CPF/CNPJ, Rua e Número para gerar o contrato!")
                        else:
                            end_completo = f"{c_rua}, nº {c_num} - {c_bairro}, {c_cidade} - {c_uf}, CEP: {c_cep}"
                        
                            df_ct_itens = df_itens_final.copy()
                            descricoes = []
                            for _, r in df_ct_itens.iterrows():
                                match = df_produtos[df_produtos['Item'] == r['Item']]
                                descricoes.append(match['Descrição'].values[0] if not match.empty else "")
                            df_ct_itens['Descrição'] = descricoes

                            pdf_ct_bytes = utils.gerar_pdf_contrato(
                                nome=c_nome, doc=c_cpf, tipo_cliente=c_tipo, endereco=end_completo,
                                objeto=c_objeto, df_items=df_ct_itens, mat_inclusos=c_mat,
                                forma_pagamento=c_pagamento, obs_pagamento=c_obs_pag, data_termino=c_data_term,
                                val_base=c_val_base, val_inst=c_val_inst, val_hidr=c_val_hidr, 
                                val_outros=c_val_outros, desc_outros=c_desc_outros
                            )
                            st.session_state[f'pdf_contrato_{prefix_key}'] = pdf_ct_bytes
                            # Salva AUTOMATICAMENTE na pasta "Contratos" do Drive
                            _hoje_ct = datetime.datetime.now().strftime("%Y_%m_%d")
                            _p_ct = c_nome.strip().split()
                            _nf_ct = (f"{_p_ct[0]}_{_p_ct[-1]}".lower() if len(_p_ct) >= 2 else (_p_ct[0].lower() if _p_ct else "cliente"))
                            _fname_ct = f"contrato_{_hoje_ct}_{_nf_ct}.pdf"
                            try:
                                _ok_ct, _res_ct = utils.upload_to_drive_folder_id(file_buffer=pdf_ct_bytes, filename=_fname_ct, mimetype="application/pdf", folder_id=utils.DRIVE_FOLDER_CONTRATOS)
                            except Exception as _e_ct:
                                _ok_ct, _res_ct = False, str(_e_ct)
                            if _ok_ct:
                                st.session_state[f'ct_drive_link_{prefix_key}'] = _res_ct
                                st.success(f"✅ Contrato gerado e **salvo automaticamente** no Drive (pasta *Contratos*) como **{_fname_ct}**.")
                                if _pasta_drive_id:
                                    utils.criar_atalho_drive(_res_ct, _pasta_drive_id, _fname_ct)
                            else:
                                st.warning(f"Contrato gerado, mas o envio automático ao Drive falhou ({_res_ct}). Use o envio manual abaixo.")

                    if f'pdf_contrato_{prefix_key}' in st.session_state:
                        st.download_button("📥 BAIXAR CONTRATO (PDF)", data=st.session_state[f'pdf_contrato_{prefix_key}'], file_name=f"CONTRATO_{c_nome.split()[0]}.pdf", mime="application/pdf", use_container_width=True, key=f"dl_ct_{prefix_key}")
                        if st.session_state.get(f'ct_drive_link_{prefix_key}'):
                            _lnk_ct = st.session_state[f'ct_drive_link_{prefix_key}']
                            st.markdown(f"☁️ <a href='https://drive.google.com/file/d/{_lnk_ct}/view' target='_blank'>Abrir contrato salvo no Drive</a>", unsafe_allow_html=True)

                        with st.container(border=True):
                            st.markdown("☁️ **Reenviar / salvar com outro nome (opcional)** — já foi salvo automaticamente na pasta *Contratos*.")
                        
                            hoje_str = datetime.datetime.now().strftime("%Y_%m_%d")
                            partes_nome = c_nome.strip().split()
                            if len(partes_nome) >= 2:
                                nome_formatado = f"{partes_nome[0]}_{partes_nome[-1]}".lower()
                            else:
                                nome_formatado = partes_nome[0].lower() if partes_nome else "cliente"
                        
                            nome_sugerido = f"contrato_{hoje_str}_{nome_formatado}.pdf"
                        
                            nome_arquivo_drive = st.text_input("Nome do arquivo do contrato:", value=nome_sugerido, key=f"input_nome_ct_drive_{prefix_key}")
                        
                            if st.button("🔁 Reenviar para o Drive", use_container_width=True, key=f"btn_upload_ct_drive_{prefix_key}"):
                                with st.spinner("Salvando na pasta Contratos..."):
                                    sucesso, msg = utils.upload_to_drive_folder_id(
                                        file_buffer=st.session_state[f'pdf_contrato_{prefix_key}'],
                                        filename=nome_arquivo_drive,
                                        mimetype="application/pdf",
                                        folder_id=utils.DRIVE_FOLDER_CONTRATOS
                                    )
                                    if sucesso:
                                        st.success(f"✅ Contrato {nome_arquivo_drive} salvo com sucesso no Drive!")
                                    else:
                                        st.error(f"Erro ao salvar: {msg}")

        with aba_mat:
            st.markdown("##### 📋 Lista de Materiais utilizada")
            st.caption("Lista que o instalador registrou pelo app, com os materiais usados nesta instalação.")
            try:
                res_mat_sid = supabase.table('listas_materiais').select('*').eq('servico_id', id_projeto).order('atualizado_em', desc=True).execute()
                listas_mat = res_mat_sid.data or []
            except Exception:
                listas_mat = []

            # Fallback pra listas antigas/avulsas sem servico_id vinculado —
            # hoje o app do instalador ainda não deixa escolher a instalação
            # ao criar uma lista, só digitar o nome do cliente à mão. Enquanto
            # isso não for corrigido lá, tenta casar pelo nome aqui.
            if not listas_mat:
                _nome_busca = str(projeto_selecionado.get('nome_cliente', '') or '').strip()
                if _nome_busca:
                    try:
                        res_mat_nome = supabase.table('listas_materiais').select('*').is_('servico_id', 'null').ilike('cliente_nome', f"%{_nome_busca}%").order('atualizado_em', desc=True).execute()
                        listas_mat = res_mat_nome.data or []
                        if listas_mat:
                            st.caption("⚠️ Encontrada(s) só pelo nome do cliente — ainda não vinculada(s) formalmente a este serviço.")
                    except Exception:
                        pass

            if not listas_mat:
                st.info("Nenhuma lista de materiais registrada pra este cliente ainda.")
            else:
                _editando_key = f"editando_lista_mat_{prefix_key}"

                # Preço/estoque de cada material (pro botão "Adquirir") e quais
                # listas deste serviço já viraram venda — buscados uma vez só,
                # fora do loop, pra não repetir a mesma consulta por lista.
                try:
                    res_cat_mat = supabase.table('materiais_padrao').select('*').execute()
                    _mapa_materiais_precos = {c['item']: c for c in (res_cat_mat.data or [])}
                except Exception:
                    _mapa_materiais_precos = {}
                try:
                    res_vendas_mat_srv = supabase.table('vendas_materiais').select('*').eq('servico_id', id_projeto).execute()
                    _vendas_por_lista = {v['lista_materiais_id']: v for v in (res_vendas_mat_srv.data or []) if v.get('lista_materiais_id')}
                except Exception:
                    _vendas_por_lista = {}

                for lm in listas_mat:
                    with st.container(border=True):
                        _data_lm = ""
                        try:
                            _data_lm = pd.to_datetime(lm.get('atualizado_em')).strftime('%d/%m/%Y %H:%M')
                        except Exception:
                            pass
                        st.markdown(f"**{lm.get('instalador', 'Instalador')}** — {_data_lm}")
                        _itens_lm = lm.get('itens') or []
                        _cols_lm = ['item', 'qtd', 'unidade']
                        if _itens_lm:
                            df_lm = pd.DataFrame(_itens_lm)
                            # Custo/Venda aparecem pro admin conferir e, se precisar,
                            # ir ajustar o preço no catálogo (Materiais Hidráulicos)
                            # antes de gerar o PDF ou adquirir — pedido do Breno
                            # (2026-09-03). Mesma fonte que "Adquirir materiais" já usa
                            # (_mapa_materiais_precos), pra nunca mostrar valor diferente
                            # do que a operação de baixa de estoque vai usar de fato.
                            df_lm['custo_unitario'] = df_lm['item'].map(
                                lambda n: float((_mapa_materiais_precos.get(n) or {}).get('custo') or 0))
                            # `venda_override` (desconto pontual dado na hora de montar
                            # a lista) tem prioridade sobre o preço do catálogo.
                            if 'venda_override' in df_lm.columns:
                                df_lm['venda_unitario'] = df_lm.apply(
                                    lambda r: float(r['venda_override']) if pd.notna(r.get('venda_override')) else float((_mapa_materiais_precos.get(r['item']) or {}).get('venda') or 0),
                                    axis=1)
                            else:
                                df_lm['venda_unitario'] = df_lm['item'].map(
                                    lambda n: float((_mapa_materiais_precos.get(n) or {}).get('venda') or 0))
                            _cols_presentes = [c for c in _cols_lm + ['custo_unitario', 'venda_unitario', 'obs'] if c in df_lm.columns]
                            st.dataframe(
                                df_lm[_cols_presentes] if _cols_presentes else df_lm, use_container_width=True, hide_index=True,
                                column_config={
                                    "custo_unitario": st.column_config.NumberColumn("Custo Unit.", format="R$ %.2f"),
                                    "venda_unitario": st.column_config.NumberColumn("Venda Unit.", format="R$ %.2f"),
                                },
                            )

                            # PDF pro cliente ANTES de "Adquirir materiais" — mostra o
                            # orçamento pra aprovação, sem mexer em estoque nenhum
                            # (mesmo formato/preço do botão em Materiais Hidráulicos).
                            _pdf_key_mat = f"pdf_lista_mat_{lm['id']}_{prefix_key}"
                            if st.button("📄 Gerar PDF pro cliente", key=f"btn_pdf_mat_{lm['id']}_{prefix_key}", use_container_width=True):
                                try:
                                    _pdf_buf, _total_pdf, _sem_preco = utils.gerar_pdf_lista_materiais(
                                        supabase, projeto_selecionado.get('nome_cliente') or "Cliente",
                                        projeto_selecionado.get('telefone_cliente') or "", _itens_lm,
                                    )
                                    st.session_state[_pdf_key_mat] = _pdf_buf.getvalue()
                                    if _sem_preco:
                                        st.warning(f"⚠️ {len(_sem_preco)} item(ns) sem preço de venda cadastrado, entraram como R$ 0,00: {', '.join(_sem_preco)}")
                                    st.success(f"PDF gerado — total {utils.to_br_currency(_total_pdf)}")
                                except Exception as e:
                                    st.error(f"Erro ao gerar PDF: {e}")
                            if st.session_state.get(_pdf_key_mat):
                                st.download_button(
                                    "⬇️ Baixar PDF", data=st.session_state[_pdf_key_mat],
                                    file_name=f"materiais_{(projeto_selecionado.get('nome_cliente') or 'cliente').replace(' ', '_')}.pdf",
                                    mime="application/pdf", key=f"dl_pdf_mat_{lm['id']}_{prefix_key}", use_container_width=True,
                                )
                        else:
                            st.caption("Lista sem itens.")

                        col_ed, col_ex = st.columns(2)
                        if col_ed.button("✏️ Editar", key=f"btn_edit_mat_{lm['id']}_{prefix_key}", use_container_width=True):
                            st.session_state[_editando_key] = lm['id'] if st.session_state.get(_editando_key) != lm['id'] else None
                            st.rerun()
                        if col_ex.button("🗑️ Excluir lista", key=f"btn_del_mat_{lm['id']}_{prefix_key}", use_container_width=True):
                            try:
                                supabase.table('listas_materiais').delete().eq('id', lm['id']).execute()
                                st.success("Lista excluída.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir: {e}")

                        # --- Adquirir materiais com a Ecoclim (venda + baixa de estoque) ---
                        _venda_existente = _vendas_por_lista.get(lm['id'])
                        if _venda_existente:
                            st.success(f"✅ Materiais já adquiridos com a Ecoclim — Lucro: {utils.to_br_currency(_venda_existente.get('lucro_total'))}")
                        else:
                            _preview_key = f"preview_adquirir_{lm['id']}_{prefix_key}"
                            if st.button("💰 Adquirir materiais com a Ecoclim", key=f"btn_iniciar_adquirir_{lm['id']}_{prefix_key}", use_container_width=True):
                                st.session_state[_preview_key] = True
                                st.rerun()

                            if st.session_state.get(_preview_key):
                                _linhas_preview = []
                                _custo_total_op = 0.0
                                _venda_total_op = 0.0
                                _tem_sem_preco = False
                                for it in _itens_lm:
                                    _mat = _mapa_materiais_precos.get(it.get('item'))
                                    _qtd = float(it.get('qtd') or 0)
                                    if not _mat:
                                        _tem_sem_preco = True
                                        _linhas_preview.append({"item": it.get('item'), "qtd": _qtd, "custo_unitario": 0.0, "venda_unitario": 0.0, "estoque_insuficiente": "sem preço no catálogo"})
                                        continue
                                    _custo_un = float(_mat.get('custo') or 0)
                                    # `venda_override` (desconto pontual dado na hora de
                                    # montar a lista) vale por cima do preço do catálogo
                                    # — sem isso, o cliente via o desconto no PDF mas
                                    # era cobrado o preço cheio na hora de adquirir.
                                    _override_venda = it.get('venda_override')
                                    _venda_un = float(_override_venda) if _override_venda is not None else float(_mat.get('venda') or 0)
                                    _estoque_at = float(_mat.get('estoque_atual') or 0)
                                    _insuficiente = _estoque_at < _qtd
                                    _linhas_preview.append({
                                        "item": it.get('item'), "qtd": _qtd,
                                        "custo_unitario": _custo_un, "venda_unitario": _venda_un,
                                        "estoque_insuficiente": f"⚠️ tem {_estoque_at:g}, falta comprar" if _insuficiente else "",
                                        "_material_id": _mat['id'],
                                    })
                                    _custo_total_op += _custo_un * _qtd
                                    _venda_total_op += _venda_un * _qtd

                                _df_preview_full = pd.DataFrame(_linhas_preview)
                                _cols_preview = [c for c in ['item', 'qtd', 'custo_unitario', 'venda_unitario', 'estoque_insuficiente'] if c in _df_preview_full.columns]
                                st.dataframe(_df_preview_full[_cols_preview], use_container_width=True, hide_index=True)
                                if _tem_sem_preco:
                                    st.caption("Itens sem preço no catálogo não entram na conta de custo/venda dessa operação.")

                                _lucro_preview = _venda_total_op - _custo_total_op
                                st.markdown(f"**Venda:** {utils.to_br_currency(_venda_total_op)} · **Custo:** {utils.to_br_currency(_custo_total_op)} · **Lucro:** {utils.to_br_currency(_lucro_preview)}")

                                col_conf, col_canc = st.columns(2)
                                if col_conf.button("✅ Confirmar aquisição", type="primary", key=f"btn_confirmar_adquirir_{lm['id']}_{prefix_key}"):
                                    try:
                                        _itens_venda_registro = [{k: v for k, v in linha.items() if k != "_material_id"} for linha in _linhas_preview]
                                        res_venda = supabase.table('vendas_materiais').insert({
                                            "servico_id": id_projeto,
                                            "lista_materiais_id": lm['id'],
                                            "cliente_nome": projeto_selecionado.get('nome_cliente'),
                                            "itens": _itens_venda_registro,
                                            "custo_total": _custo_total_op,
                                            "venda_total": _venda_total_op,
                                            "lucro_total": _lucro_preview,
                                        }).execute()
                                        venda_id = res_venda.data[0]['id']
                                        for linha in _linhas_preview:
                                            if "_material_id" not in linha:
                                                continue
                                            _qtd_baixa = float(linha['qtd'])
                                            _mat_baixa = _mapa_materiais_precos.get(linha['item'])
                                            supabase.table('estoque_movimentos').insert({
                                                "material_id": linha['_material_id'], "tipo": "saida_venda",
                                                "quantidade": _qtd_baixa, "custo_unitario_na_epoca": linha.get('custo_unitario'),
                                                "referencia_id": venda_id,
                                            }).execute()
                                            _novo_estoque = float(_mat_baixa.get('estoque_atual') or 0) - _qtd_baixa
                                            supabase.table('materiais_padrao').update({"estoque_atual": _novo_estoque}).eq('id', linha['_material_id']).execute()
                                            try:
                                                gestao_click.garantir_produto(supabase, {**_mat_baixa, "estoque_atual": _novo_estoque})
                                            except gestao_click.GestaoClickError:
                                                pass  # não trava a venda por causa do Gestão Click — sincroniza de novo na próxima oportunidade
                                        st.toast("Itens atualizados no ERP Ecoclim e no Gestão Click Ecoclim!", icon="✅")
                                        st.success(f"✅ Materiais adquiridos (lucro: {utils.to_br_currency(_lucro_preview)}) — itens atualizados no ERP Ecoclim e no Gestão Click Ecoclim!")
                                        st.session_state[_preview_key] = False
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao registrar aquisição: {e}")
                                if col_canc.button("Cancelar", key=f"btn_cancelar_adquirir_{lm['id']}_{prefix_key}"):
                                    st.session_state[_preview_key] = False
                                    st.rerun()

                        if st.session_state.get(_editando_key) == lm['id']:
                            df_edit_base = pd.DataFrame(_itens_lm)[_cols_lm] if _itens_lm else pd.DataFrame(columns=_cols_lm)
                            df_editado = st.data_editor(
                                df_edit_base, num_rows="dynamic", use_container_width=True,
                                key=f"editor_mat_{lm['id']}_{prefix_key}",
                            )
                            if st.button("💾 Salvar alterações", key=f"btn_save_edit_mat_{lm['id']}_{prefix_key}"):
                                _itens_novos = df_editado.dropna(subset=['item']).to_dict('records')
                                try:
                                    supabase.table('listas_materiais').update({
                                        "itens": _itens_novos,
                                        "atualizado_em": datetime.datetime.utcnow().isoformat(),
                                    }).eq('id', lm['id']).execute()
                                    st.success("Lista atualizada.")
                                    st.session_state[_editando_key] = None
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao salvar: {e}")

            st.markdown("---")
            with st.expander("➕ Adicionar lista de materiais", expanded=False):
                _novos_itens_key = f"novos_itens_mat_{prefix_key}"
                if _novos_itens_key not in st.session_state:
                    st.session_state[_novos_itens_key] = []

                try:
                    res_padrao = supabase.table('materiais_padrao').select('*').order('categoria').order('ordem').execute()
                    catalogo_mat = res_padrao.data or []
                except Exception:
                    catalogo_mat = []

                opcoes_catalogo = {f"{c['item']} ({c.get('categoria', '')})": c for c in catalogo_mat}

                try:
                    res_modelos = supabase.table('materiais_modelos').select('*').order('nome').execute()
                    modelos_mat = res_modelos.data or []
                except Exception:
                    modelos_mat = []
                if modelos_mat:
                    st.markdown("###### 🚀 Começar de uma lista padrão")
                    opcoes_modelo = {m['nome']: m for m in modelos_mat}
                    col_mod1, col_mod2 = st.columns([3, 1])
                    modelo_sel = col_mod1.selectbox("Lista padrão", ["-- nenhuma --"] + list(opcoes_modelo.keys()), key=f"sel_modelo_mat_{prefix_key}")
                    if col_mod2.button("📥 Usar", key=f"btn_usar_modelo_{prefix_key}", disabled=(modelo_sel == "-- nenhuma --")):
                        st.session_state[_novos_itens_key].extend(opcoes_modelo[modelo_sel].get('itens') or [])
                        st.success(f"Itens de \"{modelo_sel}\" adicionados — ajuste o que precisar abaixo.")
                        st.rerun()

                montar_itens_material(supabase, catalogo_mat, opcoes_catalogo, _novos_itens_key)

                if st.session_state[_novos_itens_key]:
                    df_novo = pd.DataFrame(st.session_state[_novos_itens_key])
                    # Custo é só de referência (nunca editável, nunca sobrescreve o
                    # catálogo). Venda o admin PODE editar aqui — pra dar desconto
                    # pontual pra um cliente — e o valor mexido é salvo JUNTO com a
                    # lista como `venda_override` por item; o preço cadastrado em
                    # materiais_padrao nunca é tocado. Pedido do Breno (2026-09-03).
                    _precos_por_item_mat = {c['item']: c for c in catalogo_mat}
                    df_novo['custo_unitario'] = df_novo['item'].map(
                        lambda n: float((_precos_por_item_mat.get(n) or {}).get('custo') or 0))
                    df_novo['venda_unitario'] = df_novo['item'].map(
                        lambda n: float((_precos_por_item_mat.get(n) or {}).get('venda') or 0))
                    df_novo_editado = st.data_editor(
                        df_novo, num_rows="dynamic", use_container_width=True,
                        column_order=[c for c in ['item', 'qtd', 'unidade', 'categoria', 'custo_unitario', 'venda_unitario'] if c in df_novo.columns],
                        column_config={
                            "item": st.column_config.TextColumn("Item", width="large"),
                            "qtd": st.column_config.NumberColumn("Qtd", width="small", min_value=0),
                            "unidade": st.column_config.TextColumn("Un.", width="small"),
                            "categoria": st.column_config.TextColumn("Categoria", width="small"),
                            "custo_unitario": st.column_config.NumberColumn("Custo Unit.", format="R$ %.2f", width="small", disabled=True),
                            "venda_unitario": st.column_config.NumberColumn(
                                "Venda Unit.", format="R$ %.2f", width="small",
                                help="Editável — mude aqui pra dar desconto pontual só nesta lista, sem afetar o preço cadastrado no catálogo.",
                            ),
                        },
                        key=f"editor_novo_mat_{prefix_key}_{len(st.session_state[_novos_itens_key])}",
                    )
                    if st.button("💾 Salvar nova lista de materiais", key=f"btn_save_novo_mat_{prefix_key}"):
                        _itens_final = (
                            df_novo_editado.drop(columns=['custo_unitario'], errors='ignore')
                            .rename(columns={'venda_unitario': 'venda_override'})
                            .dropna(subset=['item']).to_dict('records')
                        )
                        if not _itens_final:
                            st.warning("Adicione pelo menos um item.")
                        else:
                            try:
                                supabase.table('listas_materiais').insert({
                                    "servico_id": id_projeto,
                                    "instalador": "Admin",
                                    "cliente_nome": projeto_selecionado.get('nome_cliente'),
                                    "itens": _itens_final,
                                    "atualizado_em": datetime.datetime.utcnow().isoformat(),
                                }).execute()
                                st.success("Lista criada com sucesso!")
                                st.session_state[_novos_itens_key] = []
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao salvar: {e}")
                else:
                    st.caption("Nenhum item adicionado ainda — busque no catálogo ou digite um item manual acima.")

        st.markdown("<br>", unsafe_allow_html=True)
        
        if novo_status == "Excluir":
            st.error("⚠️ **ATENÇÃO:** Você selecionou a opção de Excluir. Isso apagará permanentemente este cliente e orçamento do sistema.")
            if st.button("🗑️ CONFIRMAR EXCLUSÃO", type="primary", use_container_width=True, key=f"del_{prefix_key}"):
                try:
                    supabase.table('servicos_andamento').delete().eq('id', id_projeto).execute()
                    st.success("✅ Orçamento excluído com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao excluir: {e}")
        else:
            if st.button("💾 SALVAR PROJETO", type="primary", use_container_width=True, key=f"save_{prefix_key}"):
                dados = {
                    "nome_cliente": novo_nome_cliente,
                    "telefone_cliente": novo_tel_cliente,
                    "endereco_cliente": novo_endereco_cliente,
                    "bairro_cliente": novo_bairro_cliente,
                    "cpf_cnpj_cliente": novo_cpf_cliente,
                    "status_projeto": novo_status,
                    "data_conclusao": nova_data.strftime('%Y-%m-%d'),
                    "instalador": novo_instalador,
                    "detalhamento_itens": df_itens_final.fillna("").to_dict('records'),
                    "custo_adicional_materiais": custo_ext, 
                    "custo_terceirizados": custo_mo,
                    "pago_instalador": novo_pago_instalador,
                    "data_pagamento_instalador": nova_data_pag_inst.strftime('%Y-%m-%d') if nova_data_pag_inst else None,
                    "data_inicio_garantia": nova_data_garantia.strftime('%Y-%m-%d') if nova_data_garantia else None,
                    "custo_comissao": valor_comissao,
                    "custo_impostos": valor_nf,
                    "custo_cartao": valor_cartao_taxa,
                    "valor_venda_total": venda_final,
                    "lucro_estimado": lucro_final,
                    "notas_internas": notas,
                    "nf_entrada": nova_nf_entrada,
                    "vencimento_boleto": novo_venc_boleto.strftime('%Y-%m-%d') if novo_venc_boleto else None,
                    "pago_avista_fornecedor": pago_avista,
                    "pagamentos_recebidos": lista_pagamentos_salvar,
                }
                try:
                    _status_antes = str(projeto_selecionado.get('status_projeto') or '')
                    try:
                        supabase.table('servicos_andamento').update(dados).eq('id', id_projeto).execute()
                    except Exception:
                        # Coluna "pagamentos_recebidos" ainda não existe nesse
                        # Supabase (sql_pagamentos_recebidos.sql não rodado) —
                        # grava o resto sem ela em vez de perder o salvamento
                        # inteiro; os valores continuam corretos (custo_cartao
                        # já veio somado dos pagamentos), só a lista detalhada
                        # de quem pagou o quê não persiste até a migração rodar.
                        supabase.table('servicos_andamento').update(
                            {k: v for k, v in dados.items() if k != "pagamentos_recebidos"}
                        ).eq('id', id_projeto).execute()

                    if novo_status != _status_antes:
                        movimentacoes.registrar(
                            supabase, "servico", id_projeto, "status",
                            de=_status_antes or None, para=novo_status,
                            detalhe=novo_nome_cliente,
                        )
                        # Entrar em "Em Andamento" é o momento em que a obra vira
                        # trabalho do instalador — é aí que ele precisa saber.
                        if novo_status == "Em Andamento" and novo_instalador:
                            push.avisar_instalador(
                                supabase, novo_instalador,
                                "🛠️ Nova instalação pra você",
                                f"{novo_nome_cliente} entrou em andamento.",
                                tag=f"servico-{id_projeto}",
                            )

                    if f"itens_state_{prefix_key}" in st.session_state:
                        del st.session_state[f"itens_state_{prefix_key}"]
                    if f"last_status_{prefix_key}" in st.session_state:
                        del st.session_state[f"last_status_{prefix_key}"]
                    if f"data_edit_{prefix_key}" in st.session_state:
                        del st.session_state[f"data_edit_{prefix_key}"]
                    if f"pagamentos_{prefix_key}" in st.session_state:
                        del st.session_state[f"pagamentos_{prefix_key}"]

                    st.success("✅ Atualizado com sucesso!")
                    st.rerun()
                except Exception as e: 
                    st.error(f"Erro ao salvar. Verifique se as colunas 'nf_entrada', 'vencimento_boleto', 'instalador', 'bairro_cliente' e 'cpf_cnpj_cliente' foram criadas no Supabase. Detalhe: {e}")
    except Exception as global_e:
        st.error(f"⚠️ **Erro Interno de Execução:** Ocorreu uma falha ao renderizar este painel.")
        st.info("Para que o suporte possa ajudar, por favor tire um print do erro abaixo:")
        st.code(traceback.format_exc(), language="python")
