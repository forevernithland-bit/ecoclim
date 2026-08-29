"""Motor dos lembretes pessoais — roda de minuto em minuto no servidor (cron).

Lê a tabela `lembretes` (a mesma que o Claude e o app do celular usam), pega o
que já venceu e ainda não foi avisado, e manda o push pro Breno (perfil Admin).
`avisado_em` garante um aviso por lembrete — se o cron rodar duas vezes, ninguém
recebe em dobro.

Lembrete recorrente (`repetir` = diario/semanal/uteis): ao disparar, o script
fecha a ocorrência atual e já cria a próxima. Se o Breno tiver marcado como
feito antes pelo Claude/app, a skill já criou a próxima e este script nem vê a
linha (o filtro é feito=false).

    python lembrete_pessoal.py            # envia
    python lembrete_pessoal.py --simular  # só mostra o que enviaria
"""
import sys
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import utils
import push

TZ_UTC = datetime.timezone.utc


def _iso(dt):
    return dt.astimezone(TZ_UTC).isoformat()


def _parse(iso):
    if not iso:
        return None
    try:
        dt = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=TZ_UTC) if dt.tzinfo is None else dt.astimezone(TZ_UTC)


def proxima_ocorrencia(dt, repetir):
    """Próxima data de um lembrete recorrente (mesma regra da skill Lembretes)."""
    if not dt:
        return None
    r = str(repetir or "").lower()
    if r.startswith("diar"):
        return dt + datetime.timedelta(days=1)
    if r.startswith("seman"):
        return dt + datetime.timedelta(weeks=1)
    if r in ("uteis", "úteis", "util"):
        d = dt + datetime.timedelta(days=1)
        while d.weekday() >= 5:            # pula sábado/domingo
            d += datetime.timedelta(days=1)
        return d
    return None


def main(simular=False):
    supabase = utils.init_connection()
    agora = datetime.datetime.now(TZ_UTC)

    try:
        pendentes = (
            supabase.table("lembretes").select("*")
            .eq("feito", False)
            .is_("avisado_em", "null")
            .lte("lembrar_em", _iso(agora))
            .order("lembrar_em")
            .execute().data or []
        )
    except Exception as e:
        print(f"Erro ao ler lembretes: {e}")
        return 1

    # lembrar_em nulo não vem no filtro lte, mas garante de novo:
    pendentes = [r for r in pendentes if r.get("lembrar_em")]

    if not pendentes:
        print(f"[{agora:%Y-%m-%d %H:%M} UTC] Nada pra avisar.")
        return 0

    print(f"[{agora:%Y-%m-%d %H:%M} UTC] {len(pendentes)} lembrete(s) vencido(s):")
    for lem in pendentes:
        texto = lem.get("texto") or "(sem texto)"
        prio = " ‼️" if (lem.get("prioridade") or 0) >= 1 else ""
        print(f"  #{lem['id']} — {texto}{prio}")
        if simular:
            continue

        enviadas, falhas = push.enviar(
            supabase,
            "⏰ Lembrete",
            f"{texto}{prio}",
            perfil="Admin",
            url="./index.html",
            tag=f"lembrete-{lem['id']}",
        )
        print(f"      push: {enviadas} aparelho(s), {falhas} falha(s)")

        patch = {"avisado_em": _iso(agora)}
        # Recorrente: fecha esta e agenda a próxima.
        if lem.get("repetir") and lem.get("lembrar_em"):
            prox = proxima_ocorrencia(_parse(lem["lembrar_em"]), lem["repetir"])
            if prox:
                patch["feito"] = True
                patch["feito_em"] = _iso(agora)
                try:
                    novo = supabase.table("lembretes").insert({
                        "texto": texto,
                        "lembrar_em": _iso(prox),
                        "repetir": lem["repetir"],
                        "prioridade": lem.get("prioridade") or 0,
                        "origem": "cron",
                    }).execute().data or [{}]
                    print(f"      ⟳ próxima (#{novo[0].get('id')}): {prox:%d/%m %H:%M} UTC")
                except Exception as e:
                    print(f"      (não deu pra reagendar: {e})")
                    patch.pop("feito", None)
                    patch.pop("feito_em", None)

        try:
            supabase.table("lembretes").update(patch).eq("id", lem["id"]).execute()
        except Exception as e:
            print(f"      (não deu pra marcar avisado_em: {e})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(simular="--simular" in sys.argv))
