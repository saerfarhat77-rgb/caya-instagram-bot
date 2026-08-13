"""Cliente da Instagram Graph API (publicacao de conteudo).

Toda publicacao tem dois passos: cria um container de midia e depois publica
o container. Video (reels e story em video) precisa de um terceiro passo no
meio: esperar a Meta terminar de processar o arquivo.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
import json
from dataclasses import dataclass

API = "https://graph.facebook.com/v21.0"

# A Meta processa video de forma assincrona; sem esperar, publicar da erro.
ESPERA_VIDEO_S = 10
TENTATIVAS_VIDEO = 30  # ate ~5 min


class ErroInstagram(RuntimeError):
    """Falha vinda da API do Instagram, com a mensagem original da Meta."""


def _requisicao(metodo: str, caminho: str, params: dict) -> dict:
    url = f"{API}/{caminho}"
    dados = urllib.parse.urlencode(params).encode()

    if metodo == "GET":
        url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, method="GET")
    else:
        req = urllib.request.Request(url, data=dados, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        corpo = e.read().decode(errors="replace")
        try:
            erro = json.loads(corpo)["error"]
            msg = erro.get("error_user_msg") or erro.get("message") or corpo
            # code 190 = token invalido/expirado; vale destacar, e o erro mais comum.
            if erro.get("code") == 190:
                msg = f"token invalido ou expirado - {msg}"
        except (ValueError, KeyError):
            msg = corpo
        raise ErroInstagram(f"{metodo} {caminho}: {msg}") from e
    except urllib.error.URLError as e:
        raise ErroInstagram(f"{metodo} {caminho}: falha de rede - {e.reason}") from e


@dataclass
class Instagram:
    conta_id: str
    token: str

    def _post(self, caminho: str, **params) -> dict:
        return _requisicao("POST", caminho, {**params, "access_token": self.token})

    def _get(self, caminho: str, **params) -> dict:
        return _requisicao("GET", caminho, {**params, "access_token": self.token})

    # --- containers ---------------------------------------------------

    def _container(self, **params) -> str:
        resposta = self._post(f"{self.conta_id}/media", **params)
        if "id" not in resposta:
            raise ErroInstagram(f"resposta sem id do container: {resposta}")
        return resposta["id"]

    def _esperar_video(self, container: str) -> None:
        """Aguarda a Meta terminar de processar o video do container."""
        for _ in range(TENTATIVAS_VIDEO):
            estado = self._get(container, fields="status_code,status")
            codigo = estado.get("status_code")
            if codigo == "FINISHED":
                return
            if codigo == "ERROR":
                raise ErroInstagram(
                    f"a Meta rejeitou o video: {estado.get('status', 'sem detalhe')}"
                )
            time.sleep(ESPERA_VIDEO_S)
        raise ErroInstagram(
            f"video ainda processando depois de "
            f"{TENTATIVAS_VIDEO * ESPERA_VIDEO_S // 60} min"
        )

    def _publicar(self, container: str) -> str:
        resposta = self._post(f"{self.conta_id}/media_publish", creation_id=container)
        if "id" not in resposta:
            raise ErroInstagram(f"resposta sem id da publicacao: {resposta}")
        return resposta["id"]

    # --- formatos -----------------------------------------------------

    def foto(self, url: str, legenda: str) -> str:
        return self._publicar(self._container(image_url=url, caption=legenda))

    def carrossel(self, urls: list[str], legenda: str) -> str:
        filhos = [
            self._container(image_url=u, is_carousel_item="true") for u in urls
        ]
        pai = self._container(
            media_type="CAROUSEL",
            children=",".join(filhos),
            caption=legenda,
        )
        return self._publicar(pai)

    def reels(self, url: str, legenda: str) -> str:
        container = self._container(
            media_type="REELS", video_url=url, caption=legenda
        )
        self._esperar_video(container)
        return self._publicar(container)

    def story(self, url: str, e_video: bool) -> str:
        params = (
            {"media_type": "STORIES", "video_url": url}
            if e_video
            else {"media_type": "STORIES", "image_url": url}
        )
        container = self._container(**params)
        if e_video:
            self._esperar_video(container)
        return self._publicar(container)

    # --- diagnostico --------------------------------------------------

    def limite_diario(self) -> tuple[int, int]:
        """(publicados nas ultimas 24h, cota). O Instagram permite 50/dia."""
        r = self._get(f"{self.conta_id}/content_publishing_limit", fields="quota_usage")
        dados = r.get("data") or [{}]
        return int(dados[0].get("quota_usage", 0)), 50
