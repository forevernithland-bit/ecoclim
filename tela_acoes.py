"""Aba "Ações" do Controle Financeiro: carteira, sinais por regras e radar de
oportunidades. A lógica fica em acoes_dados.py (sem Streamlit); aqui só tela.
"""
import datetime

import altair as alt
import pandas as pd
import streamlit as st

import acoes_base
import acoes_dados as ad

AVISO = (
    "ℹ️ **Ferramenta de triagem quantitativa** com dados públicos e regras fixas que você pode ajustar. Não considera seu perfil, objetivos, "
    "patrimônio nem tributação, e **não é recomendação de investimento** nem substitui assessor/analista credenciado pela CVM. "
    "Cotações via Yahoo Finance (~15 min de atraso); lucros via CVM. Os dados podem ter atraso, erros ou lacunas — confira antes de decidir. "
    "O sistema **nunca compra nem vende nada**; a decisão e a responsabilidade são suas."
)


def _brl(v):
    return "—" if v is None or pd.isna(v) else f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v, casas=1):
    return "—" if v is None or pd.isna(v) else f"{v * 100:.{casas}f}%".replace(".", ",")


@st.cache_data(ttl=900, show_spinner=False)
def _cotacoes(tickers: tuple):
    return ad.buscar_varios(tickers)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _varredura(tickers: tuple):
    return ad.buscar_varios(tickers, trabalhadores=10)


def _base(sb, recarregar=False):
    if recarregar or "_acoes_base" not in st.session_state:
        st.session_state["_acoes_base"] = acoes_base.carregar(sb)
    return st.session_state["_acoes_base"]


def _frase(av, ticker, m):
    pts = av.get("score")
    if pts is None:
        return f"**{ticker}** — sem dados suficientes para pontuar o valor pelas regras."
    ref = f" (preço R$ {m['preco']:.2f} vs preço de referência de renda R$ {m['teto_bazin']:.2f})" if m.get("teto_bazin") else ""
    return f"**{ticker}** soma **{pts:+.0f} ponto(s)** nos {av['criterios']} critérios calculados{ref}. É o resultado numérico das regras, não uma indicação de compra, venda ou manutenção."


# ---------------------------------------------------------------------------
def renderizar(sb):
    st.caption(AVISO)
    try:
        cfg = ad.ler_config(sb)
        carteira = ad.ler_carteira(sb)
        base = _base(sb)
    except Exception as e:  # noqa: BLE001
        st.error(f"Não consegui ler os dados do banco ({str(e)[:100]}). Nada foi alterado — recarregue a página.")
        return

    c1, c2 = st.columns([5, 1])
    with c2:
        if st.button("🔄 Atualizar cotações", use_container_width=True):
            _cotacoes.clear()
            st.rerun()

    t_cart, t_opo, t_cad, t_crit = st.tabs(["💼 Minha carteira", "🎯 Radar de baratas", "➕ Cadastrar / Importar", "⚙️ Critérios e dados"])

    with t_cart:
        _aba_carteira(carteira, base, cfg)
    with t_opo:
        _aba_oportunidades(carteira, base, cfg)
    with t_cad:
        _aba_cadastro(sb, carteira, base)
    with t_crit:
        _aba_criterios(sb, cfg, base)


# ---------------------------------------------------------------------------
def _aba_carteira(carteira, base, cfg):
    if not carteira:
        st.info("Carteira vazia. Use a aba **➕ Cadastrar / Importar** para colocar suas ações.")
        return
    if not base:
        st.warning("Base fundamentalista (lucros de 7 anos) ainda não carregada — vá em **⚙️ Critérios e dados** e atualize. Sem ela, os sinais usam só preço e dividendos.")

    tickers = tuple(sorted({p["ticker"] for p in carteira}))
    with st.spinner("Buscando cotações…"):
        hist = _cotacoes(tickers)

    linhas, mets = [], {}
    for p in carteira:
        t = p["ticker"]
        if t not in mets:
            m = ad.calcular_metricas(hist.get(t), base, cfg)
            mets[t] = (m, ad.avaliar(m, cfg))
        m, av = mets[t]
        preco = m.get("preco") if not m.get("erro") else None
        qtd, pm = float(p["qtd"]), float(p.get("pm") or 0)
        valor = preco * qtd if preco else None
        custo = pm * qtd if pm > 0 else None
        grupo = p.get("grupo") or m.get("grupo") or "Outros"
        linhas.append({
            "Ticker": t, "Tipo": m.get("tipo") or ad.tipo_do_ticker(t, base), "Grupo": grupo, "Corretora": p.get("corretora", ""),
            "Qtd": qtd, "Alugada": float(p.get("alugada") or 0), "Preço médio": pm if pm > 0 else None, "Cotação": preco,
            "Valor": valor, "Custo": custo,
            "Resultado R$": (valor - custo) if valor is not None and custo is not None else None,
            "Resultado %": (valor / custo - 1) if valor is not None and custo else None,
            "Dia": m.get("var_dia"), "DY 12m": m.get("dy_12m"), "Sinal": av["rotulo"],
            "vs PM": (preco / pm - 1) if preco and pm > 0 else None, "Pontos": av.get("score"),
        })
    df = pd.DataFrame(linhas)
    total = df["Valor"].sum()
    df["Peso"] = df["Valor"] / total if total else None
    pesos_grupo = (df.groupby("Grupo")["Valor"].sum() / total).to_dict() if total else {}

    com_custo = df.dropna(subset=["Custo", "Valor"])
    a, b, c, d = st.columns(4)
    a.metric("Valor da carteira", _brl(total))
    b.metric("Custo (onde há preço médio)", _brl(com_custo["Custo"].sum()))
    res = com_custo["Valor"].sum() - com_custo["Custo"].sum()
    b2 = res / com_custo["Custo"].sum() if com_custo["Custo"].sum() else None
    c.metric("Resultado", _brl(res), _pct(b2))
    ndiv = df["Dia"].notna().sum()
    dia = (df["Valor"] * df["Dia"].fillna(0) / (1 + df["Dia"].fillna(0))).sum()
    d.metric("Variação do dia", _brl(dia), _pct(dia / total) if total else None)

    erros = [t for t, (m, _) in mets.items() if m.get("erro")]
    if erros:
        st.warning("Sem cotação para: " + ", ".join(erros) + " (ticker errado ou sem negociação).")
    sem_pm = df[df["Preço médio"].isna()]["Ticker"].tolist()
    if sem_pm:
        st.caption("Sem preço médio informado (fora do resultado): " + ", ".join(sorted(set(sem_pm))))

    # alertas de concentração
    alertas = []
    pesos_papel = df.groupby("Ticker")["Peso"].sum().sort_values(ascending=False)  # soma Inter + XP do mesmo papel
    for tk_, pc in pesos_papel.items():
        if pc and pc * 100 > cfg["limite_papel"]:
            alertas.append(f"⚠️ **{tk_}** pesa {_pct(pc)} da carteira, somando todas as corretoras (limite {cfg['limite_papel']:.0f}%).")
    for g, pc in sorted(pesos_grupo.items(), key=lambda x: -x[1]):
        if pc * 100 > cfg["limite_grupo"]:
            alertas.append(f"⚠️ Grupo **{g}** soma {_pct(pc)} da carteira (limite {cfg['limite_grupo']:.0f}%).")
    for a_ in alertas:
        st.markdown(a_)

    # distribuição por grupo
    st.markdown("##### Distribuição por grupo")
    dg = df.groupby("Grupo", as_index=False)["Valor"].sum().sort_values("Valor", ascending=False)
    dg["Peso"] = dg["Valor"] / total if total else 0
    g1, g2 = st.columns([2, 3])
    with g1:
        st.altair_chart(alt.Chart(dg).mark_arc(innerRadius=50).encode(
            theta="Valor:Q", color=alt.Color("Grupo:N", legend=None),
            tooltip=["Grupo", alt.Tooltip("Valor:Q", format=",.2f"), alt.Tooltip("Peso:Q", format=".1%")]).properties(height=240), use_container_width=True)
    with g2:
        st.dataframe(dg.assign(Valor=dg["Valor"].map(_brl), Peso=dg["Peso"].map(_pct)), hide_index=True, use_container_width=True)

    st.markdown("##### Posições")
    ver = df.sort_values("Valor", ascending=False)[["Ticker", "Tipo", "Grupo", "Corretora", "Qtd", "Preço médio", "Cotação", "Valor", "Peso", "Resultado R$", "Resultado %", "vs PM", "Dia", "DY 12m", "Sinal"]]
    st.dataframe(ver, hide_index=True, use_container_width=True, column_config={
        "Qtd": st.column_config.NumberColumn(format="%d"),
        "Preço médio": st.column_config.NumberColumn(format="R$ %.2f"),
        "Cotação": st.column_config.NumberColumn(format="R$ %.2f"),
        "Valor": st.column_config.NumberColumn(format="R$ %.2f"),
        "Resultado R$": st.column_config.NumberColumn(format="R$ %.2f"),
        "Peso": st.column_config.NumberColumn(format="percent"),
        "Resultado %": st.column_config.NumberColumn(format="percent"),
        "vs PM": st.column_config.NumberColumn(format="percent", help="Cotação atual em relação ao seu preço médio"),
        "Dia": st.column_config.NumberColumn(format="percent"),
        "DY 12m": st.column_config.NumberColumn(format="percent"),
    })

    st.markdown("##### Baratas pelos critérios × seu preço médio")
    cruz = df.dropna(subset=["Pontos"]).copy()
    cruz = cruz[cruz["Pontos"] >= 1].sort_values(["Pontos", "vs PM"], ascending=[False, True])
    if cruz.empty:
        st.info("Nenhum papel da carteira pontua ≥ 1 nos critérios de valor hoje.")
    else:
        mostra = cruz[["Ticker", "Grupo", "Sinal", "Pontos", "Preço médio", "Cotação", "vs PM", "Peso"]].copy()
        mostra["Situação vs PM"] = mostra["vs PM"].map(lambda v: "—" if pd.isna(v) else ("abaixo do seu PM" if v < 0 else "acima do seu PM"))
        st.dataframe(mostra, hide_index=True, use_container_width=True, column_config={
            "Preço médio": st.column_config.NumberColumn(format="R$ %.2f"), "Cotação": st.column_config.NumberColumn(format="R$ %.2f"),
            "vs PM": st.column_config.NumberColumn(format="percent"), "Peso": st.column_config.NumberColumn(format="percent"),
            "Pontos": st.column_config.NumberColumn(format="%+d")})
        st.caption("Comprar abaixo do seu preço médio reduz o PM; acima, aumenta. É aritmética, não indicação — o simulador abaixo mostra o efeito.")

    with st.expander("🧮 Simulador de aporte (efeito no preço médio)"):
        s1, s2 = st.columns(2)
        tk_sim = s1.selectbox("Papel", sorted(df["Ticker"].unique()), key="sim_tk")
        v_sim = s2.number_input("Valor a aportar (R$)", 0.0, 1e7, 1000.0, 100.0, key="sim_v")
        lin = df[df["Ticker"] == tk_sim]
        qtd_t, custo_t = lin["Qtd"].sum(), lin["Custo"].sum()
        pm_t = (custo_t / qtd_t) if qtd_t and pd.notna(custo_t) and custo_t > 0 else 0
        sim = ad.simular_aporte(qtd_t, pm_t, mets[tk_sim][0].get("preco"), v_sim)
        if not sim:
            st.write("Informe um valor que compre ao menos 1 ação ao preço atual.")
        else:
            st.write(f"{_brl(v_sim)} compram **{sim['acoes']} ação(ões)** ao preço atual (gasto {_brl(sim['gasto'])}); a posição iria de {qtd_t:.0f} para {sim['nova_qtd']:.0f}.")
            if sim["novo_pm"]:
                st.write(f"Preço médio: {_brl(pm_t)} → **{_brl(sim['novo_pm'])}** ({_pct(sim['novo_pm'] / pm_t - 1)}).")
            else:
                st.write("Sem preço médio cadastrado nesse papel — não dá para calcular o novo PM.")

    st.markdown("##### Pontuação de cada papel")
    for t in df.sort_values("Valor", ascending=False)["Ticker"].drop_duplicates():
        m, av = mets[t]
        r = df[df["Ticker"] == t].iloc[0]
        txt, avisos = ad.leitura_da_posicao(av, (df[df["Ticker"] == t]["Peso"].sum() or 0) * 100, pesos_grupo.get(r["Grupo"], 0) * 100, cfg)
        with st.expander(f"{av['rotulo']}  ·  {t}  ·  {m.get('nome') or ''}"):
            st.markdown(_frase(av, t, m))
            if pd.notna(r["vs PM"]):
                st.markdown(f"Cotação {_pct(abs(r['vs PM']))} {'abaixo' if r['vs PM'] < 0 else 'acima'} do seu preço médio ({_brl(r['Preço médio'])}).")
            for a_ in avisos:
                st.markdown(a_)
            for mo in av["motivos"]:
                st.markdown(f"- {mo}")
            if m.get("erro"):
                continue
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Cotação", _brl(m["preco"]))
            k2.metric("Faixa 52 sem.", f"{_brl(m['baixa_52s'])} – {_brl(m['alta_52s'])}")
            k3.metric("Teto Bazin", _brl(m.get("teto_bazin")))
            k4.metric("Anos seguidos de lucro", "—" if m.get("streak_lucro") is None else m["streak_lucro"])
            if m.get("lucros"):
                st.caption("Lucro líquido (R$ milhões) por exercício: " + " · ".join(f"{a}: {v:,.0f}".replace(",", ".") if v is not None else f"{a}: s/d" for a, v in m["lucros"].items()))
            if m["tipo"] == "Unit" or m["tipo"] == "Ação":
                if not m.get("pl_atual"):
                    st.caption("P/L não calculado (dados insuficientes).")


# ---------------------------------------------------------------------------
def _aba_oportunidades(carteira, base, cfg):
    if not base:
        st.warning("Precisa da base fundamentalista. Vá em **⚙️ Critérios e dados** e clique em atualizar.")
        return
    anos = base["anos"]
    elegiveis = {}
    for tk, cnpj in base["tickers"].items():
        emp = base["empresas"][cnpj]
        if ad.anos_lucro_seguidos(emp, anos) < len(anos):
            continue
        if cfg["so_setores_perenes"] and emp.get("g") not in cfg["grupos_perenes"]:
            continue
        elegiveis[tk] = cnpj
    st.markdown(
        f"Filtro duro: **lucro em {len(anos)} exercícios seguidos ({anos[0]}–{anos[-1]})**"
        f"{' + setores perenes' if cfg['so_setores_perenes'] else ''} + liquidez ≥ {_brl(cfg['liquidez_min'])}/dia + dividendos em ≥ {cfg['div_anos_min']} dos últimos 7 anos. "
        f"**{len(elegiveis)} papéis** passam no filtro de lucro/setor."
    )
    if st.button("🔎 Varrer o mercado agora", type="primary"):
        with st.spinner(f"Buscando {len(elegiveis)} cotações e históricos (cerca de 1 minuto)…"):
            st.session_state["_acoes_scan"] = {"quando": datetime.datetime.now(), "hist": _varredura(tuple(sorted(elegiveis)))}
    scan = st.session_state.get("_acoes_scan")
    if not scan:
        st.info("Clique em **Varrer o mercado agora** para montar o ranking.")
        return

    na_carteira = {p["ticker"] for p in carteira}
    linhas, detalhe, vistos = [], {}, {}
    for tk, h in scan["hist"].items():
        if tk not in elegiveis:
            continue
        m = ad.calcular_metricas(h, base, cfg)
        if m.get("erro"):
            continue
        if (m.get("liquidez_dia") or 0) < cfg["liquidez_min"] or m.get("anos_com_dividendo", 0) < cfg["div_anos_min"]:
            continue
        av = ad.avaliar(m, cfg)
        cnpj = elegiveis[tk]
        # uma linha por empresa: o papel mais líquido
        if cnpj in vistos and vistos[cnpj][0] >= (m.get("liquidez_dia") or 0):
            continue
        vistos[cnpj] = (m.get("liquidez_dia") or 0, tk)
        detalhe[cnpj] = (m, av)
    for cnpj, (_, tk) in vistos.items():
        m, av = detalhe[cnpj]
        if av["score"] is None:
            continue
        linhas.append({"Ticker": tk, "Empresa": base["empresas"][cnpj]["n"], "Grupo": m["grupo"], "Sinal": av["rotulo"], "Score": av["score"],
                       "Cotação": m["preco"], "Teto Bazin": m.get("teto_bazin"), "DY 12m": m.get("dy_12m"),
                       "P/L": m.get("pl_atual"), "P/L mediano": m.get("pl_mediano"), "Percentil 5a": m.get("percentil_5a"),
                       "Na carteira": "✔" if tk in na_carteira else ""})
    falhas = sorted(t for t, h in scan["hist"].items() if t in elegiveis and h.get("erro"))
    st.caption(f"Varredura feita às {scan['quando']:%H:%M}." + (f" Sem cotação ({len(falhas)}): {', '.join(falhas[:20])}." if falhas else ""))
    if not linhas:
        st.info("Nenhum papel passou nos filtros.")
        return
    df = pd.DataFrame(linhas).sort_values(["Score", "DY 12m"], ascending=False)
    atr = df[df["Score"] >= 3]
    if len(atr):
        st.success(f"🔔 {len(atr)} papel(éis) perene(s) atingem a pontuação de 'barata' hoje: " + ", ".join(atr["Ticker"].head(12)))
    else:
        st.info("Nenhum papel perene atinge a pontuação de 'barata' hoje pelas regras.")
    st.dataframe(df, hide_index=True, use_container_width=True, column_config={
        "Cotação": st.column_config.NumberColumn(format="R$ %.2f"), "Teto Bazin": st.column_config.NumberColumn(format="R$ %.2f"),
        "DY 12m": st.column_config.NumberColumn(format="percent"), "P/L": st.column_config.NumberColumn(format="%.1f"),
        "P/L mediano": st.column_config.NumberColumn(format="%.1f"), "Percentil 5a": st.column_config.NumberColumn(format="percent"),
        "Score": st.column_config.NumberColumn(format="%.0f")})
    st.markdown("##### Por que cada sinal")
    for _, r in df.head(25).iterrows():
        cnpj = elegiveis[r["Ticker"]]
        m, av = detalhe[cnpj]
        with st.expander(f"{av['rotulo']} · {r['Ticker']} · {r['Empresa']} ({r['Grupo']})"):
            for mo in av["motivos"]:
                st.markdown(f"- {mo}")


# ---------------------------------------------------------------------------
def _aba_cadastro(sb, carteira, base):
    st.markdown("#### Carteira cadastrada")
    st.caption("Edite quantidade, preço médio, corretora, grupo (vazio = automático) e quantidade alugada. Clique em **Salvar** para gravar.")
    df0 = pd.DataFrame(carteira or [], columns=["ticker", "qtd", "pm", "corretora", "grupo", "alugada"])
    df0 = df0.rename(columns={"ticker": "Ticker", "qtd": "Qtd", "pm": "Preço médio", "corretora": "Corretora", "grupo": "Grupo", "alugada": "Alugada"})
    ed = st.data_editor(df0, num_rows="dynamic", use_container_width=True, hide_index=True, key=f"acoes_editor_{st.session_state.get('_acoes_ed_n', 0)}", column_config={
        "Qtd": st.column_config.NumberColumn(format="%d", min_value=0), "Preço médio": st.column_config.NumberColumn(format="R$ %.2f", min_value=0),
        "Alugada": st.column_config.NumberColumn(format="%d", min_value=0)})
    if st.button("💾 Salvar carteira", type="primary"):
        nova = []
        for _, r in ed.iterrows():
            t = str(r["Ticker"]).strip().upper() if pd.notna(r["Ticker"]) else ""
            if not t or t == "NAN" or pd.isna(r["Qtd"]):
                continue
            nova.append({"ticker": t, "qtd": float(r["Qtd"]), "pm": float(r["Preço médio"]) if pd.notna(r["Preço médio"]) else 0.0,
                         "corretora": str(r["Corretora"]) if pd.notna(r["Corretora"]) else "", "grupo": str(r["Grupo"]) if pd.notna(r["Grupo"]) else "",
                         "alugada": float(r["Alugada"]) if pd.notna(r["Alugada"]) else 0.0})
        ad.gravar_carteira(sb, nova)
        st.session_state["_acoes_ed_n"] = st.session_state.get("_acoes_ed_n", 0) + 1
        st.session_state["_acoes_msg"] = f"Carteira salva ({len(nova)} posições)."
        st.rerun()
    if st.session_state.get("_acoes_msg"):
        st.success(st.session_state.pop("_acoes_msg"))

    st.divider()
    st.markdown("#### 🔌 Sincronização automática (grátis — Pluggy)")
    conf = {}
    try:
        conf = dict(st.secrets.get("pluggy", {}))
    except Exception:  # noqa: BLE001
        pass
    if not conf.get("client_id"):
        st.info(
            "Ainda não ligada. Passo a passo (10 min, grátis): **1)** crie conta em meu.pluggy.ai e conecte **Inter** e **XP** lá (login/MFA você faz na tela deles); "
            "**2)** em dashboard.pluggy.ai crie uma aplicação e copie *Client ID* e *Client Secret*; **3)** coloque em `[pluggy]` no secrets do sistema "
            "(`client_id`, `client_secret`). Depois é só clicar em sincronizar aqui. Enquanto isso, use a importação da B3 abaixo."
        )
    elif st.button("🔄 Sincronizar Inter + XP agora"):
        import acoes_pluggy
        try:
            novas, avs = acoes_pluggy.buscar_posicoes(conf["client_id"], conf["client_secret"], list(conf.get("item_ids", [])) or None)
            for a_ in avs:
                st.warning(a_)
            if novas:
                corrs = {n["corretora"] for n in novas}
                atual = carteira
                for c_ in corrs:
                    atual = ad.mesclar_carteira(atual, [n for n in novas if n["corretora"] == c_], c_)
                ad.gravar_carteira(sb, atual)
                st.session_state["_acoes_msg"] = f"Sincronizado: {len(novas)} posições ({', '.join(sorted(corrs))})."
                st.rerun()
            else:
                st.warning("A Pluggy não devolveu ações/ETFs.")
        except Exception as e:  # noqa: BLE001
            st.error(f"Falha na sincronização: {e}")

    st.divider()
    st.markdown("#### Importar posição (Inter, XP ou B3)")
    st.markdown(
        "**Como automatizar:** no site **Área do Investidor da B3** (investidor.b3.com.br → *Extratos → Posição*) dá para baixar a posição de "
        "**todas as corretoras de uma vez** (Inter + XP) em Excel. Suba o arquivo aqui — o sistema lê tickers e quantidades. "
        "A B3 não informa preço médio, então o que você já cadastrou é preservado. (Não existe API oficial gratuita dos bancos para pessoa física; a conexão automática é a Pluggy, abaixo.)"
    )
    corr = st.text_input("Corretora desta importação", value="XP")
    arq = st.file_uploader("Planilha (.xlsx / .csv)", type=["xlsx", "xls", "csv"])
    texto = st.text_area("…ou cole linhas: TICKER QUANTIDADE PREÇO_MÉDIO (uma por linha)", height=120, placeholder="PETR4 245 28,90\nITUB4 40 38,44")
    novas, avisos = [], []
    if arq is not None:
        try:
            if arq.name.lower().endswith(".csv"):
                dfi = pd.read_csv(arq, sep=None, engine="python", dtype=str)
                novas, av = ad.interpretar_planilha(dfi, corr)
                avisos.append(av)
            else:
                for nome, dfi in pd.read_excel(arq, sheet_name=None, dtype=str).items():
                    ns, av = ad.interpretar_planilha(dfi, corr)
                    novas += ns
                    avisos.append(av)
        except Exception as e:  # noqa: BLE001
            st.error(f"Não consegui ler o arquivo: {e}")
    if texto.strip():
        ns, ignoradas = ad.interpretar_texto(texto, corr)
        novas += ns
        if ignoradas:
            avisos.append("Linhas ignoradas: " + " | ".join(ignoradas))
    for a_ in filter(None, avisos):
        st.caption(a_)
    if novas:
        st.dataframe(pd.DataFrame(novas)[["ticker", "qtd", "pm", "corretora"]], hide_index=True, use_container_width=True)
        subst = st.checkbox(f"Essa lista é a posição COMPLETA da corretora {corr} (remove o que não estiver nela)", value=False)
        if st.button("✅ Aplicar importação"):
            ad.gravar_carteira(sb, ad.mesclar_carteira(carteira, novas, corr if subst else None))
            st.session_state["_acoes_msg"] = f"Importação aplicada ({len(novas)} posições)."
            st.rerun()


# ---------------------------------------------------------------------------
def _aba_criterios(sb, cfg, base):
    st.markdown("#### Critérios (você ajusta)")
    c1, c2, c3, c4 = st.columns(4)
    y = c1.number_input("Yield alvo % (teto Bazin)", 2.0, 15.0, float(cfg["yield_alvo"]), 0.5)
    lp = c2.number_input("Limite por papel %", 3.0, 100.0, float(cfg["limite_papel"]), 1.0)
    lg = c3.number_input("Limite por grupo %", 5.0, 100.0, float(cfg["limite_grupo"]), 1.0)
    lq = c4.number_input("Liquidez mínima R$/dia", 0.0, 1e9, float(cfg["liquidez_min"]), 500_000.0)
    dm = st.number_input("Anos mínimos com dividendos (radar)", 0, 7, int(cfg["div_anos_min"]))
    sp = st.checkbox("Radar só em setores perenes", value=bool(cfg["so_setores_perenes"]))
    todos = sorted({e.get("g") for e in (base or {}).get("empresas", {}).values()} | set(cfg["grupos_perenes"]))
    gp = st.multiselect("Setores considerados perenes", todos, default=[g for g in cfg["grupos_perenes"] if g in todos])
    if st.button("💾 Salvar critérios"):
        ad.gravar_config(sb, {"yield_alvo": y, "limite_papel": lp, "limite_grupo": lg, "liquidez_min": lq, "div_anos_min": dm, "so_setores_perenes": sp, "grupos_perenes": gp})
        st.session_state.pop("_acoes_scan", None)
        st.rerun()

    st.divider()
    st.markdown("#### Como o sinal é calculado")
    st.markdown(
        "- **Teto Bazin**: mediana dos proventos anuais (5 janelas de 12 meses) ÷ yield alvo. Preço abaixo do teto = +2; até 15% acima = neutro; muito acima = −1.\n"
        "- **Dividend yield 12m** ≥ alvo: +1.\n"
        "- **P/L** atual vs **mediana do próprio histórico** (lucro da controladora ÷ ações emitidas): ≥15% abaixo = +1; ≥25% acima = −1.\n"
        "- **Percentil de preço 5 anos**: ≤25º = +1; ≥85º = −1.\n"
        "- 🟢 barata (≥3) · 🟡 intermediário (0–2) · 🔴 cara (<0). Precisa de ao menos 2 critérios calculáveis; sem lucro no último exercício a nota é limitada a 1.\n"
        "- ETFs, BDRs e fundos não têm lucro na CVM → ficam sem análise de valor. P/L usa total de ações × preço da classe (aproximação)."
    )
    st.markdown("#### Base fundamentalista (CVM)")
    if base:
        qual = sum(1 for t, c in base["tickers"].items() if ad.anos_lucro_seguidos(base["empresas"][c], base["anos"]) >= len(base["anos"]))
        st.write(f"Gerada em {base['gerado_em']} · exercícios {base['anos'][0]}–{base['anos'][-1]} · {len(base['empresas'])} companhias · {len(base['tickers'])} tickers · **{qual} com lucro em todos os anos**.")
    else:
        st.warning("Base ainda não existe.")
    st.caption("Atualize 1x por ano (março/abril, quando saem os balanços). Baixa ~90 MB da CVM e leva 1–2 minutos.")
    if st.button("⬇️ Atualizar base da CVM agora"):
        with st.status("Baixando balanços da CVM…", expanded=True) as stt:
            nova = acoes_base.construir_base(progresso=lambda m: stt.write(m))
            acoes_base.salvar(sb, nova)
            stt.update(label="Base atualizada", state="complete")
        _base(sb, recarregar=True)
        st.rerun()
