"""Alerta no WhatsApp.

Dois caminhos, escolhidos pelas variaveis de ambiente presentes:

1. WhatsApp Cloud API (oficial da Meta) - usa o mesmo app do Instagram.
   Precisa de WHATSAPP_PHONE_ID, WHATSAPP_TOKEN e WHATSAPP_DESTINO.

2. CallMeBot (terceiro, setup em 2 min) - precisa de CALLMEBOT_PHONE e
   CALLMEBOT_APIKEY.

Se nada estiver configurado, o alerta e so registrado no log: falta de
notificacao nunca deve derrubar uma publicacao que deu certo.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.facebook.com/v21.0"


def _cloud_api(texto: str) -> bool:
    phone_id = os.environ.get("WHATSAPP_PHONE_ID")
    token = os.environ.get("WHATSAPP_TOKEN")
    destino = os.environ.get("WHATSAPP_DESTINO")
    if not (phone_id and token and destino):
        return False

    corpo = json.dumps(
        {
            "messaging_product": "whatsapp",
            "to": destino,
            "type": "text",
            "text": {"body": texto},
        }
    ).encode()

    req = urllib.request.Request(
        f"{API}/{phone_id}/messages",
        data=corpo,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()
    return True


def _callmebot(texto: str) -> bool:
    phone = os.environ.get("CALLMEBOT_PHONE")
    apikey = os.environ.get("CALLMEBOT_APIKEY")
    if not (phone and apikey):
        return False

    url = "https://api.callmebot.com/whatsapp.php?" + urllib.parse.urlencode(
        {"phone": phone, "text": texto, "apikey": apikey}
    )
    with urllib.request.urlopen(url, timeout=30) as r:
        r.read()
    return True


def avisar(texto: str) -> None:
    """Manda o alerta. Nunca levanta excecao - so avisa que nao conseguiu."""
    for tentativa in (_cloud_api, _callmebot):
        try:
            if tentativa(texto):
                return
        except (urllib.error.URLError, OSError) as e:
            print(f"[whatsapp] {tentativa.__name__} falhou: {e}")
    print(f"[whatsapp] sem canal configurado. Mensagem:\n{texto}")
