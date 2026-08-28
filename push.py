"""Notificações push (Web Push) do app do instalador.

Funciona em Android e iPhone. No iPhone há uma condição da Apple que não
depende do nosso código: o push só chega se o app tiver sido **instalado na
tela inicial** — aberto pelo Safari comum, o iOS simplesmente não entrega.

Quem envia é sempre o servidor: o ERP (admin mexeu em algo) ou a própria API.
As assinaturas ficam em `push_subscriptions`; cada aparelho é uma linha, e
quando o navegador responde 404/410 a assinatura morreu (app desinstalado,
cache limpo) e é desativada pra não ficar tentando pra sempre.
"""
import json

VAPID_PUBLIC = "BAuussOkrNIF1ZA_5awDoaC1JG7USV_gaPSk4rPqXYHnvjeWk7Q4IxZtcuscw5kSpI_w98Uyg2OGQ08eHEp6idI"
# Contato exigido pelo protocolo: o serviço de push usa isso pra avisar de
# problema no envio.
VAPID_CLAIMS_EMAIL = "mailto:comercial@ecoclim.com.br"


def _chave_privada():
    """Lê a chave privada do secrets — nunca fica no código, porque com ela
    qualquer um conseguiria mandar notificação em nome do app."""
    try:
        import streamlit as st
        return st.secrets["VAPID_PRIVATE_KEY"]
    except Exception:
        pass
    from pathlib import Path
    for caminho in (Path(__file__).parent / ".streamlit" / "secrets.toml",
                    Path(r"G:\Meu Drive\CLODE\ERP_ECOCLIM\.streamlit\secrets.toml")):
        if caminho.exists():
            for linha in caminho.read_text(encoding="utf-8").splitlines():
                if linha.strip().startswith("VAPID_PRIVATE_KEY"):
                    return linha.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("VAPID_PRIVATE_KEY não configurada no secrets.")


def enviar(supabase, titulo, mensagem, *, usuario=None, instalador=None,
           perfil=None, url="./index.html", tag=None):
    """Dispara a notificação pros aparelhos que interessam.

    Filtros (combináveis): `usuario` (login exato), `instalador` (todos os
    aparelhos ligados àquele instalador) ou `perfil` ("Admin" pra avisar o
    Breno). Sem filtro nenhum não envia nada — mandar pra todo mundo por
    engano seria pior que não mandar.

    Retorna (enviadas, falhas). Nunca levanta exceção: notificação é um
    acessório, não pode derrubar o salvamento que a originou.
    """
    if not any((usuario, instalador, perfil)):
        return 0, 0

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return 0, 0

    try:
        q = supabase.table("push_subscriptions").select("*").eq("ativo", True)
        if usuario:
            q = q.eq("usuario", usuario)
        if instalador:
            q = q.eq("instalador_vinculado", instalador)
        if perfil:
            q = q.eq("perfil", perfil)
        assinaturas = q.execute().data or []
    except Exception:
        return 0, 0

    if not assinaturas:
        return 0, 0

    corpo = json.dumps({
        "title": titulo, "body": mensagem, "url": url,
        "tag": tag or "ecoclim", "badge": 1,
    })

    try:
        chave = _chave_privada()
    except Exception:
        return 0, 0

    enviadas, falhas, mortas = 0, 0, []
    for s in assinaturas:
        try:
            webpush(
                subscription_info={
                    "endpoint": s["endpoint"],
                    "keys": {"p256dh": s["p256dh"], "auth": s["auth"]},
                },
                data=corpo,
                vapid_private_key=chave,
                vapid_claims={"sub": VAPID_CLAIMS_EMAIL},
            )
            enviadas += 1
        except WebPushException as e:
            # 404/410 = assinatura não existe mais do lado do navegador.
            codigo = getattr(getattr(e, "response", None), "status_code", None)
            if codigo in (404, 410):
                mortas.append(s["id"])
            falhas += 1
        except Exception:
            falhas += 1

    if mortas:
        try:
            supabase.table("push_subscriptions").update({"ativo": False}).in_("id", mortas).execute()
        except Exception:
            pass

    return enviadas, falhas


def avisar_instalador(supabase, instalador, titulo, mensagem, **kw):
    """Atalho: avisa os aparelhos de um instalador (ex: tarefa nova na agenda)."""
    return enviar(supabase, titulo, mensagem, instalador=instalador, **kw)


def avisar_admin(supabase, titulo, mensagem, **kw):
    """Atalho: avisa o Breno (ex: instalador concluiu uma instalação)."""
    return enviar(supabase, titulo, mensagem, perfil="Admin", **kw)
