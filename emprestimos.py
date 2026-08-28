"""Empréstimos pessoais a receber — o espelho dos Boletos.

Boleto é conta que sai; aqui é dinheiro que o Breno emprestou pra amigo e
precisa lembrar de cobrar. Cada linha da tabela `emprestimos` é uma parcela;
as parcelas do mesmo empréstimo compartilham o `grupo_id`.
"""
import datetime
import urllib.parse

import pandas as pd
import streamlit as st

import utils

STATUS_PENDENTE = "Pendente"
STATUS_RECEBIDO = "Recebido"


def _somar_meses(data, meses):
    """Mesma data em outro mês, sem estourar em mês curto: quem empresta dia 31
    e parcela em 3x espera vencer 28/02, não 03/03."""
    ano = data.year + (data.month - 1 + meses) // 12
    mes = (data.month - 1 + meses) % 12 + 1
    ultimo_dia = [31, 29 if (ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0)) else 28,
                  31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1]
    return datetime.date(ano, mes, min(data.day, ultimo_dia))


def _carregar(supabase):
    try:
        res = supabase.table("emprestimos").select("*").order("vencimento").execute()
        return pd.DataFrame(res.data or [])
    except Exception as e:
        if "does not exist" in str(e) or "schema cache" in str(e):
            st.warning("A tabela de empréstimos ainda não existe no banco. "
                       "Rode `sql_emprestimos.sql` no Supabase pra ativar esta aba.")
        else:
            st.error(f"Erro ao carregar empréstimos: {e}")
        return pd.DataFrame()


def _form_novo(supabase):
    with st.expander("➕ Registrar novo empréstimo", expanded=False):
        with st.form("form_novo_emprestimo"):
            c1, c2, c3 = st.columns([2, 1.5, 1.2])
            pessoa = c1.text_input("Para quem emprestei", placeholder="Nome do amigo")
            telefone = c2.text_input("WhatsApp (opcional)", placeholder="(31) 99999-9999",
                                     help="Preenchendo aqui, aparece um botão pra cobrar direto no WhatsApp.")
            valor_total = c3.number_input("Valor emprestado (R$)", min_value=0.0, format="%.2f")

            c4, c5, c6 = st.columns([1.2, 1, 1.2])
            data_emp = c4.date_input("Data do empréstimo", value=datetime.date.today(), format="DD/MM/YYYY")
            parcelas = c5.number_input("Parcelas", min_value=1, max_value=60, value=1, step=1)
            # Padrão: primeira cobrança um mês depois. É o combinado mais comum
            # num empréstimo entre amigos, e fica editável pra quando não for.
            venc_sugerido = _somar_meses(data_emp, 1)
            primeiro_venc = c6.date_input("1º vencimento", value=venc_sugerido, format="DD/MM/YYYY")

            observacao = st.text_input("Observação (opcional)", placeholder="Ex: pra consertar o carro, combinamos sem juros")

            if parcelas > 1 and valor_total > 0:
                st.caption(f"Vai gerar {parcelas} parcelas de "
                           f"{utils.to_br_currency(round(valor_total / parcelas, 2))} — "
                           f"a primeira em {primeiro_venc.strftime('%d/%m/%Y')}, depois mensalmente.")

            if st.form_submit_button("💾 Registrar empréstimo", use_container_width=True, type="primary"):
                if not pessoa.strip():
                    st.error("Informe pra quem você emprestou.")
                elif valor_total <= 0:
                    st.error("Informe o valor emprestado.")
                else:
                    _gravar(supabase, pessoa.strip(), telefone.strip(), valor_total,
                            data_emp, int(parcelas), primeiro_venc, observacao.strip())


def _gravar(supabase, pessoa, telefone, valor_total, data_emp, parcelas, primeiro_venc, observacao):
    """Cria uma linha por parcela. O centavo que sobra na divisão vai na última
    parcela — assim a soma das parcelas fecha exatamente com o valor emprestado,
    em vez de faltar ou sobrar uns centavos na cobrança."""
    valor_parcela = round(valor_total / parcelas, 2)
    ajuste_ultima = round(valor_total - (valor_parcela * parcelas), 2)

    linhas = []
    for n in range(1, parcelas + 1):
        valor = valor_parcela + (ajuste_ultima if n == parcelas else 0)
        linhas.append({
            "pessoa": pessoa,
            "telefone": telefone or None,
            "data_emprestimo": data_emp.strftime("%Y-%m-%d"),
            "valor_total": valor_total,
            "total_parcelas": parcelas,
            "parcela_num": n,
            "valor_parcela": round(valor, 2),
            "vencimento": _somar_meses(primeiro_venc, n - 1).strftime("%Y-%m-%d"),
            "status": STATUS_PENDENTE,
            "observacao": observacao or None,
        })

    try:
        # Um insert só: as parcelas nascem com o mesmo grupo_id (default do banco)
        # apenas se forem do mesmo comando — por isso o grupo é resolvido depois.
        res = supabase.table("emprestimos").insert(linhas).execute()
        ids = [r["id"] for r in (res.data or [])]
        if ids:
            grupo = (res.data or [{}])[0].get("grupo_id")
            if grupo:
                supabase.table("emprestimos").update({"grupo_id": grupo}).in_("id", ids).execute()
        st.success(f"Empréstimo registrado! {parcelas}x pra {pessoa}.")
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Não deu pra salvar: {e}")


def _resumo(df):
    pend = df[df["status"] == STATUS_PENDENTE]
    receb = df[df["status"] == STATUS_RECEBIDO]
    hoje = datetime.date.today()
    venc = pd.to_datetime(pend["vencimento"], errors="coerce").dt.date
    atrasadas = pend[venc < hoje] if not pend.empty else pend

    c1, c2, c3 = st.columns(3)
    c1.metric("A receber", utils.to_br_currency(pend["valor_parcela"].sum() if not pend.empty else 0),
              f"{len(pend)} parcela(s)")
    c2.metric("Já recebido", utils.to_br_currency(receb["valor_parcela"].sum() if not receb.empty else 0),
              f"{len(receb)} parcela(s)")
    c3.metric("Vencidas", utils.to_br_currency(atrasadas["valor_parcela"].sum() if not atrasadas.empty else 0),
              f"{len(atrasadas)} parcela(s)", delta_color="inverse")


def _mensagem_cobranca(linha):
    venc = pd.to_datetime(linha["vencimento"], errors="coerce")
    venc_txt = venc.strftime("%d/%m/%Y") if pd.notna(venc) else ""
    parcela_txt = (f" (parcela {int(linha['parcela_num'])}/{int(linha['total_parcelas'])})"
                   if int(linha.get("total_parcelas", 1)) > 1 else "")
    return (f"Oi {linha['pessoa']}, tudo bem? "
            f"Passando pra lembrar do valor de {utils.to_br_currency(linha['valor_parcela'])}"
            f"{parcela_txt}, com vencimento em {venc_txt}. Abraço!")


def _tabela(supabase, df, mostrar_recebidos):
    alvo = df[df["status"] == (STATUS_RECEBIDO if mostrar_recebidos else STATUS_PENDENTE)].copy()
    if alvo.empty:
        st.info("Nada por aqui." if mostrar_recebidos else "Nenhuma parcela em aberto — ninguém te devendo. 🎉")
        return

    hoje = datetime.date.today()
    alvo["_venc"] = pd.to_datetime(alvo["vencimento"], errors="coerce")
    alvo = alvo.sort_values("_venc")

    for _, r in alvo.iterrows():
        venc = r["_venc"].date() if pd.notna(r["_venc"]) else None
        atrasada = venc and venc < hoje and not mostrar_recebidos
        dias = (hoje - venc).days if venc else 0

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2.2, 1.4, 1.4, 1.6])

            parcela_txt = (f" · parcela {int(r['parcela_num'])}/{int(r['total_parcelas'])}"
                           if int(r.get("total_parcelas", 1)) > 1 else "")
            c1.markdown(f"**{r['pessoa']}**{parcela_txt}")
            if r.get("observacao"):
                c1.caption(r["observacao"])

            c2.markdown(f"**{utils.to_br_currency(r['valor_parcela'])}**")
            emprestado = pd.to_datetime(r["data_emprestimo"], errors="coerce")
            if pd.notna(emprestado):
                c2.caption(f"emprestado {emprestado.strftime('%d/%m/%Y')}")

            if venc:
                if atrasada:
                    c3.markdown(f"<span style='color:#c00;font-weight:700;'>{venc.strftime('%d/%m/%Y')}</span>",
                                unsafe_allow_html=True)
                    c3.caption(f"⚠️ {dias} dia(s) em atraso")
                else:
                    c3.markdown(venc.strftime("%d/%m/%Y"))
                    if not mostrar_recebidos:
                        c3.caption(f"vence em {abs(dias)} dia(s)" if dias < 0 else "vence hoje")

            if mostrar_recebidos:
                receb = pd.to_datetime(r.get("data_recebimento"), errors="coerce")
                c4.success(f"✅ {receb.strftime('%d/%m/%Y')}" if pd.notna(receb) else "✅ Recebido")
                if c4.button("↩️ Desfazer", key=f"desf_{r['id']}", use_container_width=True):
                    supabase.table("emprestimos").update(
                        {"status": STATUS_PENDENTE, "data_recebimento": None}).eq("id", r["id"]).execute()
                    st.rerun()
            else:
                if c4.button("✅ Recebi", key=f"rec_{r['id']}", use_container_width=True, type="primary"):
                    supabase.table("emprestimos").update({
                        "status": STATUS_RECEBIDO,
                        "data_recebimento": hoje.strftime("%Y-%m-%d"),
                    }).eq("id", r["id"]).execute()
                    st.rerun()
                if r.get("telefone"):
                    fone = "".join(ch for ch in str(r["telefone"]) if ch.isdigit())
                    if fone and not fone.startswith("55"):
                        fone = "55" + fone
                    link = f"https://wa.me/{fone}?text={urllib.parse.quote(_mensagem_cobranca(r))}"
                    c4.markdown(f"<a href='{link}' target='_blank' style='font-size:0.85rem;'>💬 Cobrar no WhatsApp</a>",
                                unsafe_allow_html=True)

            with c4.popover("🗑️", use_container_width=False):
                st.caption("Apagar esta parcela?")
                if st.button("Confirmar exclusão", key=f"del_{r['id']}"):
                    supabase.table("emprestimos").delete().eq("id", r["id"]).execute()
                    st.rerun()


def renderizar():
    supabase = st.session_state.supabase
    st.markdown("### 💸 Empréstimos a Receber")
    st.caption("Dinheiro que você emprestou e precisa cobrar — o contrário dos boletos, que são o que você paga.")

    _form_novo(supabase)

    df = _carregar(supabase)
    if df.empty:
        st.info("Nenhum empréstimo registrado ainda. Use o botão acima pra cadastrar o primeiro.")
        return

    st.markdown("---")
    _resumo(df)
    st.markdown("<br>", unsafe_allow_html=True)

    aba_aberto, aba_recebido = st.tabs(["⏳ Em aberto", "✅ Recebidos"])
    with aba_aberto:
        _tabela(supabase, df, mostrar_recebidos=False)
    with aba_recebido:
        _tabela(supabase, df, mostrar_recebidos=True)
