"""Le as metricas dos posts em acompanhamento e avisa no WhatsApp.

Roda de hora em hora, junto com o publicador. Para cada post ativo, verifica
se algum marco venceu e ainda nao foi lido; se sim, busca as metricas, grava
no CSV e manda a mensagem.

Uso:
    python -m bot.acompanhar             # le os marcos vencidos
    python -m bot.acompanhar --resumo    # mostra o estado, sem ler a API
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from bot import acompanhamento, whatsapp
from bot.fila import FUSO_BRASILIA
from bot.instagram import Instagram
from bot.metricas import (
    _rotulo_marco,
    acompanhar as ler_marco,
    marcos_do_tipo,
    proximo_marco_vencido,
)

RAIZ = Path(__file__).resolve().parent.parent
REGISTRO = RAIZ / "dados" / "acompanhamento.json"
CSV = RAIZ / "dados" / "metricas.csv"


def resumo() -> int:
    itens = acompanhamento.carregar(REGISTRO)
    if not itens:
        print("Nenhum post em acompanhamento.")
        return 0

    agora = datetime.now(FUSO_BRASILIA)
    print(f"Agora: {agora:%d/%m/%Y %H:%M} (Brasilia)\n")
    for i in itens:
        marcos = marcos_do_tipo(i.tipo)
        faltam = [m for m in marcos if m not in i.marcos_lidos]
        idade = (agora - i.quando).total_seconds() / 3600
        print(f"  {i.quando:%d/%m %H:%M} [{i.tipo}] publicado ha {idade:.0f}h")
        print(f"    lidos: {sorted(i.marcos_lidos)} de {marcos}")
        if faltam:
            print(f"    proximo: {_rotulo_marco(faltam[0])} apos a publicacao")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Acompanhamento de desempenho dos posts")
    ap.add_argument("--resumo", action="store_true", help="mostra o estado e sai")
    args = ap.parse_args()

    if args.resumo:
        return resumo()

    itens = acompanhamento.carregar(REGISTRO)
    if not itens:
        print("Nenhum post em acompanhamento.")
        return 0

    conta_id = os.environ.get("IG_CONTA_ID")
    token = os.environ.get("IG_TOKEN")
    if not (conta_id and token):
        print("IG_CONTA_ID ou IG_TOKEN ausentes", file=sys.stderr)
        return 1

    ig = Instagram(conta_id=conta_id, token=token)
    houve_erro = False

    for item in itens:
        marco = proximo_marco_vencido(
            item.quando, item.tipo, set(item.marcos_lidos)
        )
        if marco is None:
            continue

        texto, ok = ler_marco(
            ig, CSV, item.post_id, item.chave, item.tipo, item.quando, marco
        )
        whatsapp.avisar(texto)
        print(f"[{item.chave}] marco {marco}h: {'ok' if ok else 'falhou'}")

        if ok:
            # So marca como lido se deu certo; senao tenta de novo na proxima hora.
            item.marcos_lidos.append(marco)
        else:
            houve_erro = True

    acompanhamento.salvar(REGISTRO, itens)
    removidos = acompanhamento.limpar_concluidos(REGISTRO)
    if removidos:
        print(f"{removidos} post(s) concluiram o acompanhamento")

    return 1 if houve_erro else 0


if __name__ == "__main__":
    sys.exit(main())
