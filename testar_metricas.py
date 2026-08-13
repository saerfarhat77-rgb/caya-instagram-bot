"""Testa marcos, CSV e comparacao com a media, sem chamar a API."""

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bot.acompanhamento import EmAcompanhamento, carregar, incluir, limpar_concluidos  # noqa: E402
from bot.fila import FUSO_BRASILIA  # noqa: E402
from bot.metricas import (  # noqa: E402
    MARCOS, Leitura, media_no_marco, montar_mensagem,
    proximo_marco_vencido, registrar,
)

agora = datetime(2026, 8, 13, 18, 0, tzinfo=FUSO_BRASILIA)
publicado = agora - timedelta(hours=5)

print("=== 1. Qual marco venceu ===")
print(f"Post publicado ha 5h. Marcos: {MARCOS}")
for lidos in ([], [1], [1, 3], [1, 3, 6]):
    m = proximo_marco_vencido(publicado, "feed", set(lidos), agora)
    print(f"  ja lidos {lidos} -> proximo vencido: {m}")

esperados = [1, 3, None, None]
obtidos = [proximo_marco_vencido(publicado, "feed", set(l), agora)
           for l in ([], [1], [1, 3], [1, 3, 6])]
print(f"  esperado {esperados} -> {'OK' if obtidos == esperados else 'ERRO: ' + str(obtidos)}")

print("\n=== 2. Story usa marcos proprios ===")
m_story = proximo_marco_vencido(publicado, "story", set(), agora)
print(f"  story publicado ha 5h -> marco {m_story} (esperado 1)")
print(f"  {'OK' if m_story == 1 else 'ERRO'}")

print("\n=== 3. CSV e comparacao com a media ===")
with tempfile.TemporaryDirectory() as tmp:
    csv_path = Path(tmp) / "metricas.csv"

    # Tres posts anteriores no marco de 3h, alcance medio 300.
    for i, alcance in enumerate([250, 300, 350], start=1):
        registrar(csv_path, Leitura(
            post_id=f"antigo{i}", chave=f"2026-08-0{i}-1200", tipo="feed",
            publicado_em=publicado - timedelta(days=i), marco_h=3,
            valores={"reach": alcance, "likes": alcance // 10,
                     "comments": 3, "saved": 5, "shares": 2,
                     "profile_visits": 8},
        ))

    media = media_no_marco(csv_path, "feed", 3, excluir_post="novo")
    print(f"  media de alcance nos 3 anteriores: {media.get('reach')} (esperado 300.0)")
    print(f"  {'OK' if media.get('reach') == 300.0 else 'ERRO'}")

    # Post novo com 420 de alcance = 40% acima da media.
    nova = Leitura(
        post_id="novo", chave="2026-08-13-1300", tipo="feed",
        publicado_em=publicado, marco_h=3,
        valores={"reach": 420, "likes": 55, "comments": 7, "saved": 12,
                 "shares": 4, "profile_visits": 15},
    )
    print("\n--- mensagem que chegaria no WhatsApp ---")
    print(montar_mensagem(nova, media))
    print("---")

    texto = montar_mensagem(nova, media)
    print(f"\n  diz '40% acima' -> {'OK' if '40% acima' in texto else 'ERRO'}")
    print(f"  tem engajamento -> {'OK' if 'Engajamento' in texto else 'ERRO'}")

    # Primeiro post do tipo: sem media para comparar.
    sem_media = montar_mensagem(nova, {})
    print(f"  avisa quando nao ha media -> {'OK' if 'sem media' in sem_media else 'ERRO'}")

print("\n=== 4. Registro de acompanhamento ===")
with tempfile.TemporaryDirectory() as tmp:
    reg = Path(tmp) / "acompanhamento.json"
    incluir(reg, "id123", "2026-08-13-1300", "feed", publicado)
    incluir(reg, "id123", "2026-08-13-1300", "feed", publicado)  # duplicata
    itens = carregar(reg)
    print(f"  incluir duas vezes o mesmo id -> {len(itens)} item (esperado 1)")
    print(f"  {'OK' if len(itens) == 1 else 'ERRO'}")

    itens[0].marcos_lidos = list(MARCOS)
    from bot.acompanhamento import salvar
    salvar(reg, itens)
    print(f"  concluido apos ler todos os marcos -> "
          f"{'OK' if carregar(reg)[0].concluido else 'ERRO'}")
    removidos = limpar_concluidos(reg)
    print(f"  limpeza remove concluidos -> {'OK' if removidos == 1 and not carregar(reg) else 'ERRO'}")
