"""Confere se as credenciais e o Pages estao funcionando, sem publicar nada.

Rode depois de configurar os secrets:

    python -m bot.conferir
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from bot.fila import ler_fila
from bot.instagram import ErroInstagram, Instagram
from bot.postar import FILA, url_publica

OK, FALHA, AVISO = "[ok]  ", "[FALHA]", "[aviso]"


def conferir_pages() -> bool:
    """A API do Instagram so consegue baixar de uma URL publica que responde 200."""
    base = os.environ.get("BASE_URL")
    if not base:
        print(f"{FALHA} BASE_URL nao definida")
        return False

    posts, _ = ler_fila(FILA)
    if not posts:
        print(f"{AVISO} fila vazia, nao da para testar o Pages com um arquivo real")
        print(f"        BASE_URL = {base}")
        return True

    url = url_publica(posts[0].midias[0])
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"{OK} Pages serve a fila ({r.status}) - {url}")
            return True
    except urllib.error.HTTPError as e:
        print(f"{FALHA} Pages respondeu {e.code} em {url}")
        print("        Confira Settings -> Pages (branch main, pasta /) e se o repo e publico")
        return False
    except urllib.error.URLError as e:
        print(f"{FALHA} nao consegui acessar o Pages: {e.reason}")
        return False


def conferir_instagram() -> bool:
    conta_id = os.environ.get("IG_CONTA_ID")
    token = os.environ.get("IG_TOKEN")
    if not (conta_id and token):
        print(f"{FALHA} IG_CONTA_ID e/ou IG_TOKEN ausentes")
        return False

    ig = Instagram(conta_id=conta_id, token=token)
    try:
        perfil = ig._get(conta_id, fields="username,name,followers_count")
        print(f"{OK} conectado em @{perfil.get('username', '?')} "
              f"({perfil.get('followers_count', '?')} seguidores)")
        usados, cota = ig.limite_diario()
        print(f"{OK} publicacoes nas ultimas 24h: {usados} de {cota}")
        return True
    except ErroInstagram as e:
        print(f"{FALHA} {e}")
        return False


def conferir_whatsapp() -> bool:
    oficial = all(os.environ.get(v) for v in
                  ("WHATSAPP_PHONE_ID", "WHATSAPP_TOKEN", "WHATSAPP_DESTINO"))
    bot = all(os.environ.get(v) for v in ("CALLMEBOT_PHONE", "CALLMEBOT_APIKEY"))

    if oficial:
        print(f"{OK} WhatsApp pela Cloud API oficial")
    elif bot:
        print(f"{OK} WhatsApp pelo CallMeBot")
    else:
        print(f"{AVISO} WhatsApp nao configurado - os avisos so vao para o log do Actions")
    return True


def main() -> int:
    print("Conferindo o robo da Caya\n")
    resultados = [
        conferir_instagram(),
        conferir_pages(),
        conferir_whatsapp(),
    ]

    posts, problemas = ler_fila(FILA)
    print(f"\n{OK} {len(posts)} post(s) na fila")
    for p in problemas:
        print(f"{AVISO} {p}")

    if all(resultados):
        print("\nTudo certo. O robo publica sozinho de hora em hora.")
        return 0
    print("\nCorrija os itens marcados como FALHA antes de contar com o agendamento.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
