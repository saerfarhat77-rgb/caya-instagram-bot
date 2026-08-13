"""Registro dos posts em acompanhamento.

Guarda o que ja foi publicado e quais marcos ja foram lidos, em um JSON
versionado no repo. Um post sai do acompanhamento quando todos os marcos do
seu tipo foram lidos.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from bot.fila import FUSO_BRASILIA
from bot.metricas import marcos_do_tipo


@dataclass
class EmAcompanhamento:
    post_id: str
    chave: str
    tipo: str
    publicado_em: str  # ISO 8601
    marcos_lidos: list[int] = field(default_factory=list)

    @property
    def quando(self) -> datetime:
        d = datetime.fromisoformat(self.publicado_em)
        return d if d.tzinfo else d.replace(tzinfo=FUSO_BRASILIA)

    @property
    def concluido(self) -> bool:
        return set(marcos_do_tipo(self.tipo)) <= set(self.marcos_lidos)


def carregar(caminho: Path) -> list[EmAcompanhamento]:
    if not caminho.exists():
        return []
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        # Arquivo corrompido nao pode travar a publicacao do dia.
        return []
    return [EmAcompanhamento(**d) for d in dados]


def salvar(caminho: Path, itens: list[EmAcompanhamento]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps([asdict(i) for i in itens], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def incluir(
    caminho: Path, post_id: str, chave: str, tipo: str, publicado_em: datetime
) -> None:
    itens = carregar(caminho)
    if any(i.post_id == post_id for i in itens):
        return
    itens.append(
        EmAcompanhamento(
            post_id=post_id,
            chave=chave,
            tipo=tipo,
            publicado_em=publicado_em.isoformat(),
        )
    )
    salvar(caminho, itens)


def limpar_concluidos(caminho: Path) -> int:
    itens = carregar(caminho)
    ativos = [i for i in itens if not i.concluido]
    removidos = len(itens) - len(ativos)
    if removidos:
        salvar(caminho, ativos)
    return removidos
