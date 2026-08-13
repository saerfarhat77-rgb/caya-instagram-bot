"""Robo de posts agendados da Caya no Instagram.

Roda de hora em hora no GitHub Actions: le a pasta fila/, publica o que ja
venceu o horario, move o que foi publicado para publicados/ e avisa no
WhatsApp o que aconteceu.

Uso:
    python -m bot.postar              # publica o que venceu
    python -m bot.postar --simular    # mostra o que faria, sem publicar
    python -m bot.postar --agenda     # lista a fila inteira e sai
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

from bot import whatsapp
from bot.fila import FUSO_BRASILIA, Post, ler_fila, pendentes
from bot.instagram import ErroInstagram, Instagram

RAIZ = Path(__file__).resolve().parent.parent
FILA = RAIZ / "fila"
PUBLICADOS = RAIZ / "publicados"


def url_publica(arquivo: Path) -> str:
    """URL do GitHub Pages para um arquivo da fila.

    A API do Instagram baixa a midia dessa URL, entao ela precisa estar no ar
    antes da publicacao - por isso o Pages serve a pasta fila/ direto.
    """
    base = os.environ.get("BASE_URL", "").rstrip("/")
    if not base:
        raise RuntimeError(
            "BASE_URL nao definida. Deve apontar para o GitHub Pages do repo, "
            "ex: https://saerfarhat77-rgb.github.io/caya-instagram-bot"
        )
    relativo = arquivo.relative_to(RAIZ).as_posix()
    return f"{base}/{urllib.parse.quote(relativo)}"


def publicar(ig: Instagram, post: Post) -> str:
    urls = [url_publica(m) for m in post.midias]

    if post.tipo == "feed":
        return ig.foto(urls[0], post.legenda)
    if post.tipo == "carrossel":
        return ig.carrossel(urls, post.legenda)
    if post.tipo == "reels":
        return ig.reels(urls[0], post.legenda)
    if post.tipo == "story":
        e_video = post.midias[0].suffix.lower() in {".mp4", ".mov"}
        return ig.story(urls[0], e_video)
    raise ErroInstagram(f"tipo de post desconhecido: {post.tipo}")


def arquivar(post: Post) -> None:
    """Move os arquivos do post para publicados/AAAA-MM/."""
    destino = PUBLICADOS / post.quando.strftime("%Y-%m")
    destino.mkdir(parents=True, exist_ok=True)
    for arquivo in post.arquivos:
        shutil.move(str(arquivo), str(destino / arquivo.name))


def descrever(post: Post) -> str:
    nomes = ", ".join(m.name for m in post.midias)
    return f"{post.quando:%d/%m %H:%M} [{post.tipo}] {nomes}"


def mostrar_agenda() -> int:
    posts, problemas = ler_fila(FILA)
    agora = datetime.now(FUSO_BRASILIA)

    if not posts and not problemas:
        print("Fila vazia.")
        return 0

    print(f"Agora: {agora:%d/%m/%Y %H:%M} (Brasilia)\n")
    for p in posts:
        marca = "VENCIDO" if p.venceu(agora) else "agendado"
        print(f"  [{marca}] {descrever(p)}")
        if p.legenda:
            primeira = p.legenda.splitlines()[0]
            print(f"            \"{primeira[:60]}{'...' if len(primeira) > 60 else ''}\"")
        else:
            print("            (sem legenda)")

    if problemas:
        print("\nProblemas na fila:")
        for p in problemas:
            print(f"  - {p}")
    return 1 if problemas else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Posts agendados da Caya no Instagram")
    ap.add_argument("--simular", action="store_true", help="nao publica de verdade")
    ap.add_argument("--agenda", action="store_true", help="lista a fila e sai")
    args = ap.parse_args()

    if args.agenda:
        return mostrar_agenda()

    vencidos, problemas = pendentes(FILA)

    if problemas:
        whatsapp.avisar(
            "Robo Caya - problemas na fila:\n"
            + "\n".join(f"- {p}" for p in problemas)
        )
        for p in problemas:
            print(f"[fila] {p}", file=sys.stderr)

    if not vencidos:
        print("Nada para publicar agora.")
        return 0

    if args.simular:
        print(f"Simulando {len(vencidos)} post(s):")
        for post in vencidos:
            print(f"  {descrever(post)}")
            for m in post.midias:
                print(f"    -> {url_publica(m)}")
        return 0

    conta_id = os.environ.get("IG_CONTA_ID")
    token = os.environ.get("IG_TOKEN")
    if not (conta_id and token):
        erro = "IG_CONTA_ID ou IG_TOKEN ausentes nos secrets do repositorio"
        whatsapp.avisar(f"Robo Caya - {erro}")
        print(erro, file=sys.stderr)
        return 1

    ig = Instagram(conta_id=conta_id, token=token)
    ok: list[str] = []
    falhas: list[str] = []

    for post in vencidos:
        try:
            post_id = publicar(ig, post)
            arquivar(post)
            ok.append(descrever(post))
            print(f"[ok] {descrever(post)} -> {post_id}")
        except (ErroInstagram, OSError) as e:
            # Falha nao arquiva: o post continua na fila e tenta de novo na
            # proxima hora. Erro de token se resolve sozinho depois da troca.
            falhas.append(f"{descrever(post)}\n   {e}")
            print(f"[falha] {descrever(post)}: {e}", file=sys.stderr)

    partes = []
    if ok:
        partes.append("Publicado no Instagram da Caya:\n" + "\n".join(f"- {o}" for o in ok))
    if falhas:
        partes.append("FALHOU (segue na fila, tenta de novo):\n" + "\n".join(f"- {f}" for f in falhas))
    if partes:
        whatsapp.avisar("\n\n".join(partes))

    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
