"""Leitura da pasta fila/: traduz nomes de arquivo em posts agendados.

Convencao de nomes (o nome do arquivo define QUANDO posta):

    2026-08-15-1900.jpg          -> foto unica, 15/08/2026 as 19:00
    2026-08-15-1900.txt          -> legenda desse post
    2026-08-17-1200_1.jpg        -> carrossel, primeira imagem
    2026-08-17-1200_2.jpg        -> carrossel, segunda imagem
    2026-08-20-0800.mp4          -> reels
    2026-08-21-1000-story.jpg    -> story
    2026-08-21-1000-story.mp4    -> story em video

O sufixo -story marca story. Sem sufixo, video vira reels e imagem vira feed.
Varias imagens com o mesmo horario e sufixo _N viram um carrossel unico.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Instagram opera no fuso da conta; a Caya posta em horario de Brasilia.
FUSO_BRASILIA = timezone(timedelta(hours=-3))

IMAGENS = {".jpg", ".jpeg", ".png"}
VIDEOS = {".mp4", ".mov"}

# Limites da API do Instagram. Conferidos na leitura da fila para o erro
# aparecer no --agenda, e nao so na hora de publicar.
MAX_IMAGEM_MB = 8
MAX_VIDEO_MB = 300

# 2026-08-17-1200_2-story.jpg -> data, hora, indice do carrossel, sufixo story
PADRAO = re.compile(
    r"^(?P<data>\d{4}-\d{2}-\d{2})-(?P<hora>\d{4})"
    r"(?:_(?P<indice>\d+))?"
    r"(?P<story>-story)?$",
    re.IGNORECASE,
)


class NomeInvalido(ValueError):
    """Arquivo na fila que nao segue a convencao de nomes."""


@dataclass
class Post:
    """Um post agendado, montado a partir de um ou mais arquivos da fila."""

    quando: datetime
    tipo: str  # feed | carrossel | reels | story
    midias: list[Path] = field(default_factory=list)
    legenda: str = ""
    arquivo_legenda: Path | None = None

    @property
    def chave(self) -> str:
        """Identificador estavel do post (o prefixo comum dos arquivos)."""
        base = self.quando.strftime("%Y-%m-%d-%H%M")
        return f"{base}-story" if self.tipo == "story" else base

    @property
    def arquivos(self) -> list[Path]:
        """Todos os arquivos que compoem o post, legenda inclusa."""
        todos = list(self.midias)
        if self.arquivo_legenda is not None:
            todos.append(self.arquivo_legenda)
        return todos

    def venceu(self, agora: datetime | None = None) -> bool:
        """O horario agendado ja passou?"""
        agora = agora or datetime.now(FUSO_BRASILIA)
        return self.quando <= agora


def _interpretar(stem: str) -> tuple[datetime, int, bool]:
    """Extrai (horario, indice do carrossel, e_story) do nome do arquivo."""
    m = PADRAO.match(stem)
    if not m:
        raise NomeInvalido(
            f"'{stem}' fora do padrao. Use AAAA-MM-DD-HHMM, "
            "opcionalmente _1 _2 para carrossel e -story para story."
        )

    data, hora = m.group("data"), m.group("hora")
    try:
        quando = datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H%M")
    except ValueError as e:
        raise NomeInvalido(f"'{stem}' tem data ou hora invalida: {e}") from e

    indice = int(m.group("indice")) if m.group("indice") else 0
    return quando.replace(tzinfo=FUSO_BRASILIA), indice, bool(m.group("story"))


def _tipo_do_post(midias: list[Path], e_story: bool) -> str:
    if e_story:
        return "story"
    if any(m.suffix.lower() in VIDEOS for m in midias):
        return "reels"
    return "carrossel" if len(midias) > 1 else "feed"


def ler_fila(pasta: Path) -> tuple[list[Post], list[str]]:
    """Le a pasta da fila e devolve (posts ordenados, problemas encontrados).

    Problemas nao interrompem a leitura: um arquivo mal nomeado nao pode
    impedir que os posts corretos sejam publicados no horario.
    """
    problemas: list[str] = []
    # chave do post -> {indice: caminho}
    grupos: dict[tuple[datetime, bool], dict[int, Path]] = {}
    legendas: dict[tuple[datetime, bool], Path] = {}

    if not pasta.is_dir():
        return [], [f"pasta da fila nao encontrada: {pasta}"]

    for arquivo in sorted(pasta.iterdir()):
        if not arquivo.is_file() or arquivo.name.startswith("."):
            continue

        ext = arquivo.suffix.lower()
        if ext not in IMAGENS | VIDEOS | {".txt"}:
            problemas.append(f"{arquivo.name}: extensao '{ext}' nao suportada")
            continue

        try:
            quando, indice, e_story = _interpretar(arquivo.stem)
        except NomeInvalido as e:
            problemas.append(str(e))
            continue

        chave = (quando, e_story)
        if ext == ".txt":
            legendas[chave] = arquivo
            continue

        limite = MAX_VIDEO_MB if ext in VIDEOS else MAX_IMAGEM_MB
        tamanho_mb = arquivo.stat().st_size / (1024 * 1024)
        if tamanho_mb > limite:
            problemas.append(
                f"{arquivo.name}: {tamanho_mb:.1f} MB, acima do limite de "
                f"{limite} MB do Instagram"
            )
            continue

        vagas = grupos.setdefault(chave, {})
        if indice in vagas:
            problemas.append(
                f"{arquivo.name}: conflito com {vagas[indice].name} "
                "(mesmo horario e mesmo indice)"
            )
            continue
        vagas[indice] = arquivo

    posts: list[Post] = []
    for (quando, e_story), vagas in grupos.items():
        midias = [caminho for _, caminho in sorted(vagas.items())]

        if len(midias) > 10:
            problemas.append(
                f"{quando:%Y-%m-%d %H:%M}: {len(midias)} imagens, "
                "o Instagram aceita no maximo 10 num carrossel"
            )
            continue

        tipo = _tipo_do_post(midias, e_story)

        if tipo == "reels" and len(midias) > 1:
            problemas.append(
                f"{quando:%Y-%m-%d %H:%M}: video nao pode ser agrupado em carrossel"
            )
            continue
        if tipo == "story" and len(midias) > 1:
            problemas.append(
                f"{quando:%Y-%m-%d %H:%M}: story aceita so uma midia por vez"
            )
            continue

        arquivo_legenda = legendas.get((quando, e_story))
        legenda = ""
        if arquivo_legenda is not None:
            # utf-8-sig remove o BOM que o Bloco de Notas do Windows insere;
            # sem isso a legenda comeca com um caractere invisivel.
            legenda = arquivo_legenda.read_text(encoding="utf-8-sig").strip()

        posts.append(
            Post(
                quando=quando,
                tipo=tipo,
                midias=midias,
                legenda=legenda,
                arquivo_legenda=arquivo_legenda,
            )
        )

    # Legenda solta (sem midia) e quase sempre erro de digitacao no nome.
    for chave, caminho in legendas.items():
        if chave not in grupos:
            problemas.append(f"{caminho.name}: legenda sem imagem/video correspondente")

    posts.sort(key=lambda p: p.quando)
    return posts, problemas


def pendentes(pasta: Path, agora: datetime | None = None) -> tuple[list[Post], list[str]]:
    """Posts cujo horario ja chegou e que ainda estao na fila."""
    posts, problemas = ler_fila(pasta)
    return [p for p in posts if p.venceu(agora)], problemas
