"""Histórico de movimentações — usado pelo ERP e espelhado no app (movimentacoes.js).

Registrar o que aconteceu é barato e responde sozinho as perguntas que
aparecem depois ("quem cancelou essa visita?", "quando isso virou Em
Andamento?"). Nada aqui pode derrubar a operação: se o registro falhar, a
ação que o usuário fez continua valendo.
"""
import streamlit as st

ROTULOS = {
    "criou": "criou",
    "status": "mudou o status",
    "comentario": "comentou",
    "midia": "anexou mídia",
    "editou": "editou",
    "concluiu": "concluiu",
}


def registrar(supabase, tipo, referencia_id, acao, *, usuario=None, de=None, para=None, detalhe=None):
    try:
        supabase.table("movimentacoes").insert({
            "tipo": tipo, "referencia_id": int(referencia_id),
            "usuario": usuario or st.session_state.get("usuario_logado", "Sistema"),
            "acao": acao, "de": de, "para": para, "detalhe": detalhe,
        }).execute()
    except Exception:
        pass  # histórico é registro, não pode travar o que o usuário fez


def listar(supabase, tipo, referencia_id, limite=40):
    try:
        return supabase.table("movimentacoes").select("*").eq("tipo", tipo).eq(
            "referencia_id", int(referencia_id)).order("criado_em", desc=True).limit(limite).execute().data or []
    except Exception:
        return []


def frase(mov):
    """Uma linha legível a partir do registro."""
    quem = mov.get("usuario") or "Alguém"
    acao = ROTULOS.get(mov.get("acao"), mov.get("acao") or "mexeu")
    if mov.get("acao") == "status" and mov.get("para"):
        de = f" (era {mov['de']})" if mov.get("de") else ""
        return f"{quem} {acao} para **{mov['para']}**{de}"
    if mov.get("detalhe"):
        return f"{quem} {acao}: {mov['detalhe']}"
    return f"{quem} {acao}"


def render(supabase, tipo, referencia_id, titulo="🕓 Histórico de movimentações"):
    """Bloco de histórico pronto pra colar em qualquer tela do ERP."""
    import pandas as pd
    movs = listar(supabase, tipo, referencia_id)
    with st.expander(f"{titulo} ({len(movs)})", expanded=False):
        if not movs:
            st.caption("Nada registrado ainda.")
            return
        for m in movs:
            quando = pd.to_datetime(m.get("criado_em"), errors="coerce")
            carimbo = quando.strftime("%d/%m/%Y %H:%M") if pd.notna(quando) else ""
            st.markdown(f"- {frase(m)}  <span style='color:#888;font-size:0.85em;'>· {carimbo}</span>",
                        unsafe_allow_html=True)
