"""Teste da leitura da fila com arquivos de mentira, sem tocar na API."""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bot.fila import FUSO_BRASILIA, ler_fila  # noqa: E402

ARQUIVOS = [
    "2026-08-15-1900.jpg",          # feed
    "2026-08-15-1900.txt",
    "2026-08-17-1200_1.jpg",        # carrossel de 3
    "2026-08-17-1200_2.jpg",
    "2026-08-17-1200_3.png",
    "2026-08-17-1200.txt",
    "2026-08-20-0800.mp4",          # reels
    "2026-08-20-0800.txt",
    "2026-08-21-1000-story.jpg",    # story
    "2026-09-01-1200.jpeg",         # futuro, sem legenda
    "foto-do-anel.jpg",             # nome invalido
    "2026-13-45-9999.jpg",          # data impossivel
    "2026-08-30-1500.txt",          # legenda orfa
    "2026-08-15-1900.gif",          # extensao nao suportada
]

with tempfile.TemporaryDirectory() as tmp:
    pasta = Path(tmp)
    for nome in ARQUIVOS:
        arquivo = pasta / nome
        arquivo.write_text("Anel meia alianca em ouro branco.\n#caya #joias"
                           if nome.endswith(".txt") else "x", encoding="utf-8")

    posts, problemas = ler_fila(pasta)
    agora = datetime(2026, 8, 18, 10, 0, tzinfo=FUSO_BRASILIA)

    print(f"Referencia de tempo: 18/08/2026 10:00\n")
    print(f"{len(posts)} posts lidos:")
    for p in posts:
        estado = "VENCIDO" if p.venceu(agora) else "futuro "
        print(f"  [{estado}] {p.quando:%d/%m %H:%M} {p.tipo:9} "
              f"{len(p.midias)} midia(s)  legenda={'sim' if p.legenda else 'NAO'}")

    print(f"\n{len(problemas)} problemas detectados:")
    for p in problemas:
        print(f"  - {p}")

    esperado_tipos = ["feed", "carrossel", "reels", "story", "feed"]
    obtidos = [p.tipo for p in posts]
    vencidos = [p for p in posts if p.venceu(agora)]

    print("\n--- conferencia ---")
    print(f"tipos esperados {esperado_tipos} -> {'OK' if obtidos == esperado_tipos else 'ERRO: ' + str(obtidos)}")
    print(f"2 vencidos em 18/08 -> {'OK' if len(vencidos) == 2 else 'ERRO: ' + str(len(vencidos))}")
    print(f"carrossel com 3 midias -> {'OK' if len(posts[1].midias) == 3 else 'ERRO'}")
    print(f"4 problemas esperados -> {'OK' if len(problemas) == 4 else 'ERRO: ' + str(len(problemas))}")
