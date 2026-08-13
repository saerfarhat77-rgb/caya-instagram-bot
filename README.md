# Robo de posts agendados — Instagram da Caya

Voce sobe a foto com a data no nome. Na hora marcada, o robo publica sozinho
e avisa no seu WhatsApp. Roda na nuvem: seu PC pode estar desligado.

## Como agendar um post

O **nome do arquivo diz quando posta**. O `.txt` de mesmo nome diz o que escreve.

```
fila/
  2026-08-15-1900.jpg        foto no feed, 15/08 as 19:00
  2026-08-15-1900.txt        legenda dessa foto

  2026-08-17-1200_1.jpg      carrossel: ate 10 imagens,
  2026-08-17-1200_2.jpg      mesmo horario, sufixo _1 _2 _3...
  2026-08-17-1200_3.jpg
  2026-08-17-1200.txt        uma legenda so para o carrossel

  2026-08-20-0800.mp4        reels (todo video sem sufixo vira reels)
  2026-08-20-0800.txt

  2026-08-21-1000-story.jpg  story (sufixo -story; aceita .jpg ou .mp4)
```

Formato da data: `AAAA-MM-DD-HHMM`, horario de Brasilia. `1900` = 19:00.
Story nao usa legenda. Se faltar o `.txt`, o post vai sem legenda.

O robo roda de hora em hora e publica tudo que ja passou do horario — entao um
post marcado para 19:00 sai entre 19:05 e 20:05. Se precisar do minuto exato,
me fala que troco a frequencia do agendador.

Depois de publicar, os arquivos vao para `publicados/AAAA-MM/`. Se um post
falhar, ele **fica na fila** e tenta de novo na hora seguinte.

## Comandos

```bash
python -m bot.postar --agenda     # ver a fila inteira e o que esta vencido
python -m bot.postar --simular    # ensaio: mostra o que faria, sem publicar
python -m bot.postar              # publica de verdade o que venceu
```

---

## Configuracao (uma vez so)

### 1. Instagram: pegar o ID da conta e o token

1. Acesse <https://developers.facebook.com/apps> e crie um app do tipo
   **Business**.
2. Adicione o produto **Instagram Graph API**.
3. Abra o **Graph API Explorer**, selecione o app e peca estas permissoes:
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
   `business_management`.
4. Rode `me/accounts` para achar a Pagina do Facebook da Caya e copie o `id`.
5. Rode `{id-da-pagina}?fields=instagram_business_account`. O `id` que voltar
   e o **IG_CONTA_ID**.
6. O token do Explorer dura 1 hora. Troque por um de longa duracao (60 dias):

```
https://graph.facebook.com/v21.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={APP_ID}
  &client_secret={APP_SECRET}
  &fb_exchange_token={TOKEN_CURTO}
```

O token de 60 dias e o **IG_TOKEN**. Anote a data de validade — quando vencer,
o robo avisa no WhatsApp e basta repetir este passo 6.

### 2. WhatsApp: escolha um dos dois

**Opcao A — CallMeBot (2 minutos, gratis):**
1. Salve o numero `+34 644 51 95 23` nos contatos.
2. Mande `I allow callmebot to send me messages` para ele.
3. Ele responde com sua apikey.
4. Secrets: `CALLMEBOT_PHONE` (seu numero com codigo do pais, ex `5511999998888`)
   e `CALLMEBOT_APIKEY`.

**Opcao B — WhatsApp Cloud API (oficial da Meta, mesmo app do Instagram):**
1. No app da Meta, adicione o produto **WhatsApp**.
2. Copie o **Phone number ID** e o token.
3. Secrets: `WHATSAPP_PHONE_ID`, `WHATSAPP_TOKEN` e `WHATSAPP_DESTINO`
   (seu numero com codigo do pais).

Se as duas estiverem configuradas, a oficial tem prioridade.

### 3. GitHub

No repositorio, em **Settings → Secrets and variables → Actions**:

| Secret | O que e |
|---|---|
| `IG_CONTA_ID` | ID da conta Instagram Business (passo 1.5) |
| `IG_TOKEN` | Token de 60 dias (passo 1.6) |
| `CALLMEBOT_PHONE` / `CALLMEBOT_APIKEY` | Se escolheu a opcao A |
| `WHATSAPP_PHONE_ID` / `WHATSAPP_TOKEN` / `WHATSAPP_DESTINO` | Se escolheu a opcao B |

Na aba **Variables** (nao Secrets), crie `BASE_URL` com a URL do Pages, ex:
`https://saerfarhat77-rgb.github.io/caya-instagram-bot`

Em **Settings → Pages**, ative servindo da branch `main`, pasta `/ (root)`.

> O repositorio precisa ser **publico**: a API do Instagram baixa a imagem da
> URL, e URL de repo privado nao abre para ela.

---

## Limites do Instagram (nao sao do robo)

- 50 publicacoes por dia por conta
- Carrossel: 10 imagens no maximo
- Reels: ate 15 min, formato 9:16
- Story: so publica depois que a Meta aprovar o app em modo Live
- Imagem: JPEG/PNG, proporcao entre 4:5 e 1.91:1

## Quando algo der errado

O WhatsApp avisa. Os casos mais comuns:

- **"token invalido ou expirado"** → refaca o passo 1.6 e atualize `IG_TOKEN`.
- **"fora do padrao"** → nome do arquivo errado; confira `AAAA-MM-DD-HHMM`.
- **Post nao saiu e nao chegou aviso** → aba **Actions** no GitHub mostra o log.

Post que falha nao e arquivado: continua na fila e tenta de novo sozinho.
