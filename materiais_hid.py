import streamlit as st
import pandas as pd
import datetime
import urllib.parse
import servicos_painel
import utils


def renderizar():
    st.markdown("### 🧰 Materiais Hidráulicos")
    st.caption("Monte listas de materiais hidráulicos avulsas ou cadastre listas padrão reutilizáveis (ex: Acoplado, Tradicional). Precificação entra numa próxima etapa.")

    supabase = st.session_state.supabase
    try:
        res_cat = supabase.table('materiais_padrao').select('*').order('categoria').order('ordem').execute()
        catalogo_mat = res_cat.data or []
    except Exception:
        catalogo_mat = []
    opcoes_catalogo = {f"{c['item']} ({c.get('categoria', '')})": c for c in catalogo_mat}

    aba_listas, aba_padrao = st.tabs(["📦 Listas de Materiais", "📋 Listas Padrão"])

    # =========================================================================
    # ABA: LISTAS DE MATERIAIS (AVULSAS — não vinculadas a uma instalação)
    # =========================================================================
    with aba_listas:
        st.caption("Listas avulsas — não vinculadas a uma instalação específica. Também aparecem aqui as listas avulsas que o instalador criou pelo app.")
        try:
            res_listas = supabase.table('listas_materiais').select('*').is_('servico_id', 'null').order('atualizado_em', desc=True).execute()
            listas_avulsas = res_listas.data or []
        except Exception:
            listas_avulsas = []

        try:
            res_projetos_andamento = supabase.table('servicos_andamento').select('id, nome_cliente').eq('status_projeto', 'Em Andamento').order('nome_cliente').execute()
            projetos_andamento = res_projetos_andamento.data or []
        except Exception:
            projetos_andamento = []
        opcoes_projeto = {f"{p['nome_cliente']} (ID {p['id']})": p for p in projetos_andamento}

        if listas_avulsas:
            st.markdown("##### Listas cadastradas")
            _editando_lista_key = "editando_lista_hid"
            for lm in listas_avulsas:
                with st.container(border=True):
                    _itens_lm = lm.get('itens') or []
                    st.markdown(f"**{lm.get('cliente_nome') or 'Sem nome'}** — {len(_itens_lm)} item(ns) · {lm.get('instalador', '')}")
                    if _itens_lm:
                        _df = pd.DataFrame(_itens_lm)
                        _cols = [c for c in ['item', 'qtd', 'unidade'] if c in _df.columns]
                        # Custo/Venda de referência (mesma regra: `venda_override`
                        # por item, se tiver desconto pontual salvo, tem prioridade
                        # sobre o preço do catálogo). Pedido do Breno (2026-09-03).
                        _precos_lista_avulsa = {c['item']: c for c in catalogo_mat}
                        _df['custo_unitario'] = _df['item'].map(
                            lambda n: float((_precos_lista_avulsa.get(n) or {}).get('custo') or 0))
                        if 'venda_override' in _df.columns:
                            _df['venda_unitario'] = _df.apply(
                                lambda r: float(r['venda_override']) if pd.notna(r.get('venda_override')) else float((_precos_lista_avulsa.get(r['item']) or {}).get('venda') or 0),
                                axis=1)
                        else:
                            _df['venda_unitario'] = _df['item'].map(
                                lambda n: float((_precos_lista_avulsa.get(n) or {}).get('venda') or 0))
                        _cols_com_preco = _cols + ['custo_unitario', 'venda_unitario']
                        st.dataframe(
                            _df[_cols_com_preco], use_container_width=True, hide_index=True,
                            column_config={
                                "custo_unitario": st.column_config.NumberColumn("Custo Unit.", format="R$ %.2f"),
                                "venda_unitario": st.column_config.NumberColumn("Venda Unit.", format="R$ %.2f"),
                            },
                        )
                        # st.metric, não st.markdown — "R$" repetido na mesma string
                        # de markdown embaralha (ver aprendizado 2026-09-03).
                        _qtd_avulsa = pd.to_numeric(_df.get('qtd'), errors='coerce').fillna(0)
                        _total_venda_avulsa = float((_qtd_avulsa * _df['venda_unitario']).sum())
                        _total_custo_avulsa = float((_qtd_avulsa * _df['custo_unitario']).sum())
                        _col_c_av, _col_v_av, _col_l_av = st.columns(3)
                        _col_c_av.metric("Custo", utils.to_br_currency(_total_custo_avulsa))
                        _col_v_av.metric("Venda", utils.to_br_currency(_total_venda_avulsa))
                        _col_l_av.metric("Lucro", utils.to_br_currency(_total_venda_avulsa - _total_custo_avulsa))

                        with st.expander("📋 Ver texto formatado (copiar, print ou WhatsApp)"):
                            _texto_lm = utils.gerar_texto_lista_materiais(lm.get('cliente_nome'), _itens_lm)
                            st.code(_texto_lm, language=None)
                            _url_wa = "https://wa.me/?text=" + urllib.parse.quote(_texto_lm)
                            st.markdown(f"[📤 Abrir no WhatsApp]({_url_wa})")

                        # PDF pro cliente, com preço de venda (formato horizontal
                        # aprovado em revisão de marketing — 2026-09-03). Gerado na
                        # hora do clique, não fica salvo: se a lista mudar, o PDF do
                        # próximo clique já sai atualizado.
                        if st.button("📄 Gerar PDF pro cliente", key=f"btn_pdf_lista_hid_{lm['id']}", use_container_width=True):
                            try:
                                _pdf_buf, _total_pdf, _sem_preco = utils.gerar_pdf_lista_materiais(
                                    supabase, lm.get('cliente_nome') or "Cliente", "", _itens_lm,
                                )
                                st.session_state[f"pdf_lista_hid_{lm['id']}"] = _pdf_buf.getvalue()
                                if _sem_preco:
                                    st.warning(f"⚠️ {len(_sem_preco)} item(ns) sem preço de venda cadastrado, entraram como R$ 0,00: {', '.join(_sem_preco)}")
                                st.success(f"PDF gerado — total {utils.to_br_currency(_total_pdf)}")
                            except Exception as e:
                                st.error(f"Erro ao gerar PDF: {e}")
                        if st.session_state.get(f"pdf_lista_hid_{lm['id']}"):
                            st.download_button(
                                "⬇️ Baixar PDF", data=st.session_state[f"pdf_lista_hid_{lm['id']}"],
                                file_name=f"materiais_{(lm.get('cliente_nome') or 'cliente').replace(' ', '_')}.pdf",
                                mime="application/pdf", key=f"dl_pdf_lista_hid_{lm['id']}", use_container_width=True,
                            )

                    col_ed, col_ex = st.columns(2)
                    if col_ed.button("✏️ Editar", key=f"btn_edit_lista_hid_{lm['id']}", use_container_width=True):
                        st.session_state[_editando_lista_key] = lm['id'] if st.session_state.get(_editando_lista_key) != lm['id'] else None
                        st.rerun()
                    if col_ex.button("🗑️ Excluir", key=f"btn_del_lista_hid_{lm['id']}", use_container_width=True):
                        try:
                            supabase.table('listas_materiais').delete().eq('id', lm['id']).execute()
                            st.success("Lista excluída.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")

                    if opcoes_projeto:
                        col_sel_proj, col_btn_proj = st.columns([3, 1])
                        proj_sel = col_sel_proj.selectbox(
                            "Enviar pra cliente em andamento", ["-- escolher --"] + list(opcoes_projeto.keys()),
                            key=f"sel_proj_lista_hid_{lm['id']}", label_visibility="collapsed",
                        )
                        if col_btn_proj.button("📤 Enviar", key=f"btn_enviar_proj_{lm['id']}", use_container_width=True, disabled=(proj_sel == "-- escolher --")):
                            _proj = opcoes_projeto[proj_sel]
                            try:
                                supabase.table('listas_materiais').update({
                                    "servico_id": _proj['id'],
                                    "cliente_nome": _proj['nome_cliente'],
                                }).eq('id', lm['id']).execute()
                                st.success(f"Lista enviada pra \"{_proj['nome_cliente']}\" — agora ela aparece dentro desse cliente, não mais aqui.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao enviar: {e}")
                    else:
                        st.caption("Nenhum cliente 'Em Andamento' encontrado pra enviar essa lista.")

                    if st.session_state.get(_editando_lista_key) == lm['id']:
                        _cols_edit = ['item', 'qtd', 'unidade']
                        df_edit = pd.DataFrame(_itens_lm)[_cols_edit] if _itens_lm else pd.DataFrame(columns=_cols_edit)
                        df_edit_novo = st.data_editor(
                            df_edit, num_rows="dynamic", use_container_width=True,
                            key=f"editor_lista_hid_{lm['id']}",
                        )
                        if st.button("💾 Salvar alterações", key=f"btn_save_lista_hid_{lm['id']}"):
                            _itens_novos = df_edit_novo.dropna(subset=['item']).to_dict('records')
                            try:
                                supabase.table('listas_materiais').update({
                                    "itens": _itens_novos,
                                    "atualizado_em": datetime.datetime.utcnow().isoformat(),
                                }).eq('id', lm['id']).execute()
                                st.success("Lista atualizada.")
                                st.session_state[_editando_lista_key] = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao salvar: {e}")

        st.markdown("---")
        st.markdown("##### ➕ Criar nova lista de materiais")
        nome_nova_lista = st.text_input("Nome/Referência (ex: nome do cliente ou do orçamento)", key="nome_nova_lista_hid")

        try:
            res_modelos_h = supabase.table('materiais_modelos').select('*').order('nome').execute()
            modelos_h = res_modelos_h.data or []
        except Exception:
            modelos_h = []

        _itens_nova_lista_key = "itens_nova_lista_hid"
        if _itens_nova_lista_key not in st.session_state:
            st.session_state[_itens_nova_lista_key] = []

        if modelos_h:
            opcoes_modelo_h = {m['nome']: m for m in modelos_h}
            col_m1, col_m2 = st.columns([3, 1])
            modelo_sel_h = col_m1.selectbox("Começar de uma lista padrão", ["-- nenhuma --"] + list(opcoes_modelo_h.keys()), key="sel_modelo_hid")
            if col_m2.button("📥 Usar", key="btn_usar_modelo_hid", disabled=(modelo_sel_h == "-- nenhuma --")):
                st.session_state[_itens_nova_lista_key].extend(opcoes_modelo_h[modelo_sel_h].get('itens') or [])
                st.success(f"Itens de \"{modelo_sel_h}\" adicionados — ajuste o que precisar abaixo.")
                st.rerun()

        servicos_painel.montar_itens_material(supabase, catalogo_mat, opcoes_catalogo, _itens_nova_lista_key)

        if st.session_state[_itens_nova_lista_key]:
            df_nova = pd.DataFrame(st.session_state[_itens_nova_lista_key])
            # A chave inclui a quantidade de itens de propósito: sempre que
            # um item entra por fora (colar WhatsApp, catálogo, modelo), a
            # lista muda de tamanho e a chave muda junto — isso força o
            # editor a recarregar do zero com os itens novos. Sem isso, o
            # Streamlit mantém o estado antigo da tabela (mesma chave fixa
            # entre reruns) e os itens adicionados depois da primeira vez
            # não apareciam pra salvar de verdade.
            # Custo é só de referência (nunca editável, nunca sobrescreve o
            # catálogo). Venda o admin PODE editar aqui — pra dar desconto pontual
            # pra um cliente — e o valor mexido é salvo JUNTO com a lista como
            # `venda_override` por item; o preço cadastrado em materiais_padrao
            # nunca é tocado. Pedido do Breno (2026-09-03).
            _precos_por_item_hid = {c['item']: c for c in catalogo_mat}
            df_nova['custo_unitario'] = df_nova['item'].map(
                lambda n: float((_precos_por_item_hid.get(n) or {}).get('custo') or 0))
            df_nova['venda_unitario'] = df_nova['item'].map(
                lambda n: float((_precos_por_item_hid.get(n) or {}).get('venda') or 0))
            df_nova_edit = st.data_editor(
                df_nova, num_rows="dynamic", use_container_width=True,
                column_order=[c for c in ['item', 'qtd', 'unidade', 'categoria', 'custo_unitario', 'venda_unitario'] if c in df_nova.columns],
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
                key=f"editor_nova_lista_hid_{len(st.session_state[_itens_nova_lista_key])}",
            )
            # Soma ao vivo — lê o dataframe JÁ editado, então acompanha qualquer
            # alteração de qtd ou de Venda Unit. (desconto pontual) a cada
            # interação, sem precisar salvar antes. Pedido do Breno (2026-09-03).
            _qtd_soma_h = pd.to_numeric(df_nova_edit.get('qtd'), errors='coerce').fillna(0)
            _venda_soma_h = pd.to_numeric(df_nova_edit.get('venda_unitario'), errors='coerce').fillna(0)
            _custo_soma_h = pd.to_numeric(df_nova_edit.get('custo_unitario'), errors='coerce').fillna(0)
            _total_venda_soma_h = float((_qtd_soma_h * _venda_soma_h).sum())
            _total_custo_soma_h = float((_qtd_soma_h * _custo_soma_h).sum())
            # st.metric (não st.markdown): o Streamlit trata "$" como abertura de
            # fórmula matemática (LaTeX) em QUALQUER string de markdown, mesmo com
            # unsafe_allow_html=True (isso só libera tag HTML, não desliga a
            # detecção de fórmula) — com três valores em "R$" saía embaralhado.
            # st.metric não roda essa interpretação sobre o valor.
            _col_custo_h, _col_venda_h, _col_lucro_h = st.columns(3)
            _col_custo_h.metric("Custo", utils.to_br_currency(_total_custo_soma_h))
            _col_venda_h.metric("Venda", utils.to_br_currency(_total_venda_soma_h))
            _col_lucro_h.metric("Lucro", utils.to_br_currency(_total_venda_soma_h - _total_custo_soma_h))

            # PDF pro cliente ANTES de salvar — usa o que já está na tela (com
            # qualquer desconto pontual editado na Venda Unit.), formato
            # horizontal combinado (revisão de marketing 2026-09-03). Pedido
            # do Breno (2026-09-05).
            if st.button("📄 Gerar PDF pro cliente", key="btn_pdf_nova_lista_hid", use_container_width=True):
                _itens_pdf_hid = (
                    df_nova_edit.drop(columns=['custo_unitario'], errors='ignore')
                    .rename(columns={'venda_unitario': 'venda_override'})
                    .dropna(subset=['item']).to_dict('records')
                )
                if not _itens_pdf_hid:
                    st.warning("Adicione pelo menos um item.")
                else:
                    try:
                        _pdf_buf_hid, _total_pdf_hid, _sem_preco_hid = utils.gerar_pdf_lista_materiais(
                            supabase, nome_nova_lista.strip() or "Cliente", "", _itens_pdf_hid,
                        )
                        st.session_state["pdf_nova_lista_hid"] = _pdf_buf_hid.getvalue()
                        if _sem_preco_hid:
                            st.warning(f"⚠️ {len(_sem_preco_hid)} item(ns) sem preço de venda: {', '.join(_sem_preco_hid)}")
                        st.success(f"PDF gerado — total {utils.to_br_currency(_total_pdf_hid)}")
                    except Exception as e:
                        st.error(f"Erro ao gerar PDF: {e}")
            if st.session_state.get("pdf_nova_lista_hid"):
                st.download_button(
                    "⬇️ Baixar PDF", data=st.session_state["pdf_nova_lista_hid"],
                    file_name=f"materiais_{(nome_nova_lista.strip() or 'cliente').replace(' ', '_')}.pdf",
                    mime="application/pdf", key="dl_pdf_nova_lista_hid", use_container_width=True,
                )

            if st.button("💾 Salvar lista de materiais", type="primary", key="btn_save_nova_lista_hid"):
                _itens_final = (
                    df_nova_edit.drop(columns=['custo_unitario'], errors='ignore')
                    .rename(columns={'venda_unitario': 'venda_override'})
                    .dropna(subset=['item']).to_dict('records')
                )
                if not _itens_final:
                    st.warning("Adicione pelo menos um item.")
                else:
                    try:
                        supabase.table('listas_materiais').insert({
                            "servico_id": None,
                            "instalador": "Admin",
                            "cliente_nome": nome_nova_lista.strip() or None,
                            "itens": _itens_final,
                            "atualizado_em": datetime.datetime.utcnow().isoformat(),
                        }).execute()
                        st.success("Lista de materiais criada!")
                        st.session_state[_itens_nova_lista_key] = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
        else:
            st.caption("Nenhum item adicionado ainda — comece de uma lista padrão, cole do WhatsApp, busque no catálogo, ou digite manual acima.")

    # =========================================================================
    # ABA: LISTAS PADRÃO (MODELOS)
    # =========================================================================
    with aba_padrao:
        st.caption("Modelos prontos (ex: Acoplado, Tradicional, Modular) que o instalador ou o admin podem usar como ponto de partida ao criar uma lista de materiais — só ajusta o que precisar depois.")

        try:
            res_modelos_cfg = supabase.table('materiais_modelos').select('*').order('nome').execute()
            modelos_existentes = res_modelos_cfg.data or []
        except Exception:
            modelos_existentes = []

        if modelos_existentes:
            st.markdown("##### Listas já cadastradas")
            _editando_modelo_key = "editando_modelo_mat"
            for m in modelos_existentes:
                _itens_m = m.get('itens') or []
                # Fechadas por padrão: são 4+ listas de 20 a 24 itens cada, e
                # abertas de uma vez enchem a tela toda antes de chegar no que
                # a pessoa veio fazer. Abre só a que ela quiser ver — mas a que
                # está sendo editada continua aberta, senão o clique em "Editar"
                # dispara o rerun e o editor some junto com o expander fechando.
                with st.expander(f"**{m['nome']}** — {len(_itens_m)} item(ns)",
                                 expanded=(st.session_state.get(_editando_modelo_key) == m['id'])):
                    if _itens_m:
                        _df_m = pd.DataFrame(_itens_m)
                        _cols_m = [c for c in ['item', 'qtd', 'unidade'] if c in _df_m.columns]
                        st.dataframe(_df_m[_cols_m] if _cols_m else _df_m, use_container_width=True, hide_index=True)

                    col_ed_m, col_ex_m = st.columns(2)
                    if col_ed_m.button("✏️ Editar", key=f"btn_edit_modelo_{m['id']}", use_container_width=True):
                        st.session_state[_editando_modelo_key] = m['id'] if st.session_state.get(_editando_modelo_key) != m['id'] else None
                        st.rerun()
                    if col_ex_m.button("🗑️ Excluir", key=f"btn_del_modelo_{m['id']}", use_container_width=True):
                        try:
                            supabase.table('materiais_modelos').delete().eq('id', m['id']).execute()
                            st.success("Lista padrão excluída.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir: {e}")

                    if st.session_state.get(_editando_modelo_key) == m['id']:
                        _cols_edit_m = ['item', 'qtd', 'unidade']
                        df_edit_modelo = pd.DataFrame(_itens_m)[_cols_edit_m] if _itens_m else pd.DataFrame(columns=_cols_edit_m)
                        df_edit_modelo_novo = st.data_editor(
                            df_edit_modelo, num_rows="dynamic", use_container_width=True,
                            key=f"editor_modelo_{m['id']}",
                        )
                        if st.button("💾 Salvar alterações", key=f"btn_save_modelo_{m['id']}"):
                            _itens_novos_m = df_edit_modelo_novo.dropna(subset=['item']).to_dict('records')
                            try:
                                supabase.table('materiais_modelos').update({"itens": _itens_novos_m}).eq('id', m['id']).execute()
                                st.success("Lista padrão atualizada.")
                                st.session_state[_editando_modelo_key] = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao salvar: {e}")

        st.markdown("---")
        st.markdown("##### ➕ Criar nova lista padrão")
        nome_novo_modelo = st.text_input("Nome da lista (ex: Acoplado, Tradicional, Modular)", key="nome_novo_modelo_mat")
        _itens_novo_modelo_key = "itens_novo_modelo_mat"
        if _itens_novo_modelo_key not in st.session_state:
            st.session_state[_itens_novo_modelo_key] = []

        servicos_painel.montar_itens_material(supabase, catalogo_mat, opcoes_catalogo, _itens_novo_modelo_key)

        if st.session_state[_itens_novo_modelo_key]:
            df_novo_modelo = pd.DataFrame(st.session_state[_itens_novo_modelo_key])
            df_novo_modelo_edit = st.data_editor(
                df_novo_modelo, num_rows="dynamic", use_container_width=True,
                key=f"editor_novo_modelo_mat_{len(st.session_state[_itens_novo_modelo_key])}",
            )
            if st.button("💾 Salvar lista padrão", type="primary", key="btn_save_novo_modelo_mat"):
                _itens_final_modelo = df_novo_modelo_edit.dropna(subset=['item']).to_dict('records')
                if not nome_novo_modelo.strip():
                    st.warning("Dê um nome pra essa lista padrão.")
                elif not _itens_final_modelo:
                    st.warning("Adicione pelo menos um item.")
                else:
                    try:
                        supabase.table('materiais_modelos').insert({
                            "nome": nome_novo_modelo.strip(),
                            "itens": _itens_final_modelo,
                        }).execute()
                        st.success(f"Lista padrão \"{nome_novo_modelo.strip()}\" criada!")
                        st.session_state[_itens_novo_modelo_key] = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
        else:
            st.caption("Nenhum item adicionado ainda — cole a lista do WhatsApp, busque no catálogo, ou digite manual acima.")
