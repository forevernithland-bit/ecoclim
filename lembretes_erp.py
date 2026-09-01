"""Lembretes no ERP desktop — mesmo banco (tabela `lembretes`) que o app do
celular e a skill do Claude. Aqui é só mais um cliente lendo/escrevendo.

Abre por um ícone ao lado da logo (só perfil Admin), num diálogo — de
propósito NÃO vira item no menu de navegação, pra não poluir.
"""
import datetime
import streamlit as st

TZ_BR = datetime.timezone(datetime.timedelta(hours=-3))  # Brasília (sem horário de verão)

CATEGORIAS = [("ecoclim", "Ecoclim"), ("consorbens", "Consorbens"),
              ("maggi", "Maggi"), ("pessoal", "Pessoal")]
CAT_PADRAO = "pessoal"
_SLUGS = [s for s, _ in CATEGORIAS]
_ROTULO = dict(CATEGORIAS)
_LABEL_PARA_SLUG = {lbl: s for s, lbl in CATEGORIAS}


def rotulo(slug):
    return _ROTULO.get(slug, "Pessoal")


def slug_do_label(label):
    return _LABEL_PARA_SLUG.get(label)


# ---------------------------------------------------------------------------
def _sb():
    if "supabase" in st.session_state:
        return st.session_state.supabase
    import utils
    return utils.init_connection()


def _agora_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt):
    return dt.astimezone(datetime.timezone.utc).isoformat()


def _parse(iso):
    if not iso:
        return None
    try:
        dt = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=datetime.timezone.utc) if dt.tzinfo is None else dt


def montar_lembrar_em(d, t):
    """date + time (horário de Brasília) -> ISO em UTC. Sem data -> None."""
    if not d:
        return None
    t = t or datetime.time(9, 0)
    return _iso(datetime.datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=TZ_BR))


def quando_br(iso):
    dt = _parse(iso)
    if not dt:
        return ""
    dl = dt.astimezone(TZ_BR)
    hoje = datetime.datetime.now(TZ_BR).date()
    d = dl.date()
    if d == hoje:
        dia = "hoje"
    elif d == hoje + datetime.timedelta(days=1):
        dia = "amanhã"
    elif d == hoje - datetime.timedelta(days=1):
        dia = "ontem"
    else:
        dia = dl.strftime("%d/%m")
    return f"{dia} {dl.strftime('%H:%M')}"


def esta_atrasado(lem):
    dt = _parse(lem.get("lembrar_em"))
    return bool(dt and not lem.get("feito") and dt < _agora_utc())


# ---------------------------------------------------------------------------
def listar(categoria=None, incluir_feitos=False):
    q = _sb().table("lembretes").select("*")
    if not incluir_feitos:
        q = q.eq("feito", False)
    if categoria:
        q = q.eq("categoria", categoria)
    return q.order("feito").order("lembrar_em").execute().data or []


def contar_atrasados():
    try:
        abertos = (_sb().table("lembretes").select("lembrar_em")
                   .eq("feito", False).execute().data or [])
    except Exception:
        return 0
    agora = _agora_utc()
    return sum(1 for r in abertos if (_parse(r.get("lembrar_em")) or agora) < agora
               and r.get("lembrar_em"))


def criar(texto, categoria=CAT_PADRAO, lembrar_em=None, repetir=None, prioridade=0):
    linha = {
        "texto": (texto or "").strip(),
        "categoria": categoria if categoria in _SLUGS else CAT_PADRAO,
        "origem": "erp",
    }
    if lembrar_em:
        linha["lembrar_em"] = lembrar_em
    if repetir:
        linha["repetir"] = repetir
    if prioridade:
        linha["prioridade"] = int(prioridade)
    _sb().table("lembretes").insert(linha).execute()


def _proxima(dt, repetir):
    r = (repetir or "").lower()
    if r.startswith("diar"):
        return dt + datetime.timedelta(days=1)
    if r.startswith("seman"):
        return dt + datetime.timedelta(weeks=1)
    if r in ("uteis", "úteis", "util"):
        d = dt + datetime.timedelta(days=1)
        while d.weekday() >= 5:
            d += datetime.timedelta(days=1)
        return d
    return None


def marcar_feito(lem, feito):
    agora = _iso(_agora_utc())
    patch = ({"feito": True, "feito_em": agora, "atualizado_em": agora}
             if feito else
             {"feito": False, "feito_em": None, "avisado_em": None, "atualizado_em": agora})
    _sb().table("lembretes").update(patch).eq("id", lem["id"]).execute()
    if feito and lem.get("repetir") and lem.get("lembrar_em"):
        prox = _proxima(_parse(lem["lembrar_em"]), lem["repetir"])
        if prox:
            _sb().table("lembretes").insert({
                "texto": lem["texto"], "lembrar_em": _iso(prox),
                "repetir": lem["repetir"], "prioridade": lem.get("prioridade") or 0,
                "categoria": lem.get("categoria") or CAT_PADRAO, "origem": "erp",
            }).execute()


def mudar_categoria(lem_id, categoria):
    if categoria not in _SLUGS:
        return
    _sb().table("lembretes").update(
        {"categoria": categoria, "atualizado_em": _iso(_agora_utc())}
    ).eq("id", lem_id).execute()


def adiar(lem_id, lembrar_em_iso):
    _sb().table("lembretes").update(
        {"lembrar_em": lembrar_em_iso, "avisado_em": None, "feito": False,
         "atualizado_em": _iso(_agora_utc())}
    ).eq("id", lem_id).execute()


def excluir(lem_id):
    _sb().table("lembretes").delete().eq("id", lem_id).execute()
