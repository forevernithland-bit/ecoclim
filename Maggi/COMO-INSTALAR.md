# Base de médias de lance — Simulador Maggi

Estes arquivos fazem a "base de dados" das médias de lance ficar no seu GitHub
(repositório **forevernithland-bit/ecoclim**) e se atualizar sozinha toda semana.
O simulador (arquivo HTML) lê essa base e mostra a média de cada grupo.

## O que tem aqui

- **scraper.py** — robô que acessa o site da Maggi, lê as assembleias e calcula a
  média do lance livre dos últimos 3 meses de cada grupo (excluindo os lances fixos).
- **medias.json** — a base de dados (gerada pelo robô). É esse arquivo que o simulador lê.
- **.github/workflows/atualizar-medias.yml** — agendamento: roda o robô toda segunda-feira.

## Passo a passo (só uma vez)

1. Entre no seu repositório no GitHub: **forevernithland-bit/ecoclim**.
2. Clique em **Add file → Upload files** e suba estes 3 arquivos, **mantendo as pastas**:
   - `scraper.py`
   - `medias.json`
   - `.github/workflows/atualizar-medias.yml`  (precisa ficar dentro de `.github/workflows/`)
   
   > Dica: ao subir, no campo do nome do arquivo do workflow você pode digitar
   > `.github/workflows/atualizar-medias.yml` que o GitHub cria as pastas sozinho.
3. Confirme o envio (**Commit changes**).
4. Vá em **Settings → Actions → General**, role até **Workflow permissions**, marque
   **"Read and write permissions"** e salve. (Isso deixa o robô atualizar o arquivo.)
5. Vá na aba **Actions**, escolha **"Atualizar médias de lance"** e clique em
   **Run workflow** para rodar agora (depois ele roda sozinho toda semana).

Pronto. A base fica em:
```
https://raw.githubusercontent.com/forevernithland-bit/ecoclim/main/medias.json
```
O simulador (`simuladornovoMaggi.html`) já está configurado para ler essa URL.

## Como funciona no dia a dia

- O simulador continua sendo **1 arquivo HTML** que você envia para os parceiros.
- Quando alguém abre o simulador e escolhe um grupo, ele busca a média nessa base do
  GitHub (rápido). Se o GitHub estiver fora, mostra o último valor salvo no próprio arquivo.
- Toda segunda o robô recalcula e atualiza o `medias.json` — sem você fazer nada.

## Ajustes

- **Mudar o dia/horário:** edite a linha `cron` no `atualizar-medias.yml`.
  (formato: `minuto hora * * dia-da-semana`, em UTC. `0 9 * * 1` = segunda 09:00 UTC.)
- **Adicionar/remover grupos ou mudar o lance fixo:** edite o dicionário `GRUPOS`
  no topo do `scraper.py`.
