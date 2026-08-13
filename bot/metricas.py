"""Acompanhamento de desempenho dos posts publicados.

Depois que um post vai ao ar, ele entra em acompanhamento.py e o robo le as
metricas nos marcos definidos em MARCOS. Cada leitura vira uma linha no
metricas.csv e uma mensagem no WhatsApp comparando com a media dos posts
anteriores - numero solto nao diz se foi bem ou mal.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from bot.fila import FUSO_BRASILIA
from bot.instagram import ErroInstagram, Instagram

# Marcos de acompanhamento, em horas depois da publicacao.
# Para receber menos mensagens, apague itens desta lista.
MARCOS = [1, 3, 6, 12, 24, 48, 72, 168, 336]  # ate 14 dias

# Story so tem metrica durante as 24h de vida; depois a API nao devolve mais.
MARCOS_STORY = [1, 6, 20]

# Metricas por tipo de post. A API rejeita a chamada inteira se pedirmos uma
# metrica que nao existe para aquele formato.
METRICAS = {
    "feed": ["reach", "likes", "comments", "saved", "shares", "profile_visits"],
    "carrossel": ["reach", "likes", "comments", "saved", "shares", "profile_visits"],
    "reels": ["reach", "likes", "comments", "saved", "shares", "views"],
    "story": ["reach", "replies"],
}

# Como cada metrica aparece na mensagem do WhatsApp.
ROTULOS = {
    "reach": "alcance",
    "views": "views",
    "likes": "curtidas",
    "comments": "comentarios",
    "saved": "salvamentos",
    "shares": "compartilhamentos",
    "profile_visits": "visitas ao perfil",
    "replies": "respostas",
}

COLUNAS = [
    "post_id", "chave", "tipo", "publicado_em", "marco_h", "lido_em",
    "reach", "views", "likes", "comments", "saved", "shares",
    "profile_visits", "replies",
]


@dataclass
class Leitura:
    post_id: str
    chave: str
    tipo: str
    publicado_em: datetime
    marco_h: int
    valores: dict[str, int]

    def como_linha(self) -> dict[str, str]:
        linha = {
            "post_id": self.post_id,
            "chave": self.chave,
            "tipo": self.tipo,
            "publicado_em": self.publicado_em.isoformat(),
            "marco_h": str(self.marco_h),
            "lido_em": datetime.now(FUSO_BRASILIA).isoformat(),
        }
        for coluna in COLUNAS[6:]:
            linha[coluna] = str(self.valores.get(coluna, ""))
        return linha


def marcos_do_tipo(tipo: str) -> list[int]:
    return MARCOS_STORY if tipo == "story" else MARCOS


def ler_metricas(ig: Instagram, post_id: str, tipo: str) -> dict[str, int]:
    """Busca as metricas de um post na API."""
    campos = METRICAS.get(tipo, METRICAS["feed"])
    resposta = ig._get(f"{post_id}/insights", metric=",".join(campos))

    valores: dict[str, int] = {}
    for item in resposta.get("data", []):
        nome = item.get("name")
        pontos = item.get("values") or [{}]
        valor = pontos[0].get("value")
        if nome and isinstance(valor, int):
            valores[nome] = valor
    return valores


def registrar(csv_path: Path, leitura: Leitura) -> None:
    """Acrescenta a leitura ao CSV, criando o cabecalho se for a primeira."""
    novo = not csv_path.exists()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        if novo:
            escritor.writeheader()
        escritor.writerow(leitura.como_linha())


def historico(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def media_no_marco(
    csv_path: Path, tipo: str, marco_h: int, excluir_post: str
) -> dict[str, float]:
    """Media de cada metrica nos posts anteriores do mesmo tipo e marco.

    E o que da sentido ao numero: 312 de alcance so significa algo comparado
    ao que a conta costuma fazer.
    """
    soma: dict[str, float] = {}
    n = 0
    for linha in historico(csv_path):
        if linha.get("tipo") != tipo or linha.get("marco_h") != str(marco_h):
            continue
        if linha.get("post_id") == excluir_post:
            continue
        n += 1
        for coluna in COLUNAS[6:]:
            bruto = linha.get(coluna, "")
            if bruto not in ("", None):
                try:
                    soma[coluna] = soma.get(coluna, 0.0) + float(bruto)
                except ValueError:
                    continue
    if n == 0:
        return {}
    return {k: v / n for k, v in soma.items()}


def _rotulo_marco(horas: int) -> str:
    if horas < 24:
        return f"{horas}h"
    dias = horas // 24
    return f"{dias} dia" if dias == 1 else f"{dias} dias"


def _comparar(valor: int, media: float) -> str:
    """Traduz a diferenca para a media em algo legivel."""
    if media <= 0:
        return ""
    variacao = (valor - media) / media * 100
    if abs(variacao) < 10:
        return "  (na media)"
    seta = "acima" if variacao > 0 else "abaixo"
    return f"  ({abs(variacao):.0f}% {seta} da media)"


def montar_mensagem(leitura: Leitura, media: dict[str, float]) -> str:
    """Monta o texto do WhatsApp para um marco."""
    campos = METRICAS.get(leitura.tipo, METRICAS["feed"])
    linhas = [
        f"Post de {leitura.publicado_em:%d/%m %H:%M} ({leitura.tipo})",
        f"Balanco de {_rotulo_marco(leitura.marco_h)}:",
        "",
    ]

    for campo in campos:
        if campo not in leitura.valores:
            continue
        valor = leitura.valores[campo]
        rotulo = ROTULOS.get(campo, campo)
        linhas.append(f"- {rotulo}: {valor:,}".replace(",", ".")
                      + _comparar(valor, media.get(campo, 0.0)))

    alcance = leitura.valores.get("reach", 0)
    interacoes = sum(
        leitura.valores.get(c, 0) for c in ("likes", "comments", "saved", "shares")
    )
    if alcance > 0:
        taxa = interacoes / alcance * 100
        linhas += ["", f"Engajamento: {taxa:.1f}% de quem viu interagiu"]

    if not media:
        linhas += ["", "(primeiro post neste marco - ainda sem media para comparar)"]

    return "\n".join(linhas)


def proximo_marco_vencido(
    publicado_em: datetime, tipo: str, ja_lidos: set[int], agora: datetime | None = None
) -> int | None:
    """Primeiro marco que ja venceu e ainda nao foi lido."""
    agora = agora or datetime.now(FUSO_BRASILIA)
    for horas in marcos_do_tipo(tipo):
        if horas in ja_lidos:
            continue
        if agora >= publicado_em + timedelta(hours=horas):
            return horas
    return None


def acompanhar(
    ig: Instagram, csv_path: Path, post_id: str, chave: str, tipo: str,
    publicado_em: datetime, marco_h: int,
) -> tuple[str, bool]:
    """Le, grava e monta a mensagem de um marco. Devolve (texto, deu_certo)."""
    try:
        valores = ler_metricas(ig, post_id, tipo)
    except ErroInstagram as e:
        return f"Nao consegui ler as metricas do post de {publicado_em:%d/%m %H:%M}: {e}", False

    leitura = Leitura(post_id, chave, tipo, publicado_em, marco_h, valores)
    media = media_no_marco(csv_path, tipo, marco_h, excluir_post=post_id)
    registrar(csv_path, leitura)
    return montar_mensagem(leitura, media), True
