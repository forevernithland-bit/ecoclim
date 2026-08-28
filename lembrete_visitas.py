"""Lembrete da véspera — roda 1x por dia no servidor (cron).

Manda push pro instalador sobre as visitas de amanhã que ele ainda não
confirmou. O card de confirmação no app já mostra isso quando ele abre; este
script é o empurrão pra quem não abriria o app por conta própria.

`lembrete_enviado_em` garante um aviso por visita por dia: se o cron rodar
duas vezes (ou for disparado na mão), ninguém recebe a mesma coisa em dobro.

    python lembrete_visitas.py            # envia
    python lembrete_visitas.py --simular  # só mostra o que enviaria
"""
import sys
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import utils
import push


def main(simular=False):
    supabase = utils.init_connection()
    hoje = datetime.date.today()
    amanha = hoje + datetime.timedelta(days=1)

    try:
        visitas = supabase.table("agenda_visitas").select("*").eq("status", "Agendada").execute().data or []
    except Exception as e:
        print(f"Erro ao ler agenda: {e}")
        return 1

    alvo = []
    for v in visitas:
        if v.get("confirmacao"):                       # já respondeu OK/Remarcar
            continue
        if str(v.get("lembrete_enviado_em") or "") == hoje.isoformat():
            continue                                   # já avisado hoje
        try:
            data_visita = datetime.datetime.fromisoformat(str(v["data_hora"]).replace("Z", "+00:00")).date()
        except Exception:
            continue
        if data_visita == amanha:
            alvo.append(v)

    if not alvo:
        print(f"[{hoje}] Nenhuma visita amanhã pendente de confirmação.")
        return 0

    print(f"[{hoje}] {len(alvo)} visita(s) amanhã aguardando confirmação:")
    for v in alvo:
        quando = str(v.get("data_hora", ""))[11:16]
        print(f"  - {v.get('instalador')}: {v.get('cliente_nome')} às {quando}")
        if simular:
            continue
        enviadas, _ = push.avisar_instalador(
            supabase, v.get("instalador"),
            "⏰ Visita amanhã — confirme",
            f"{v.get('cliente_nome')} às {quando}. Abra o app e responda OK ou Remarcar.",
            tag=f"lembrete-{v['id']}",
        )
        try:
            supabase.table("agenda_visitas").update(
                {"lembrete_enviado_em": hoje.isoformat()}).eq("id", v["id"]).execute()
        except Exception:
            pass
        print(f"      push enviado para {enviadas} aparelho(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(simular="--simular" in sys.argv))
