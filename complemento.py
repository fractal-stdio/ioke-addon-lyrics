"""Complemento "Letras extras" para o IOkê: o NetEase como fonte de letras (muitas palavra a palavra)
(API 1, pelo SDK karaoke_complemento.py).

O Musixmatch saiu na 1.1.0: ele passou a recusar o acesso sem conta (o token vem zerado) e nao devolvia mais nada."""
import logging
from concurrent.futures import ThreadPoolExecutor

import letras
from karaoke_complemento import Complemento, Erro

log = logging.getLogger("complemento")
comp = Complemento()


def _ligada(fonte):
    return comp.opcoes.get(fonte, True) is not False


def _netease(consulta):
    itens = letras._check_netease(letras.netease_search(consulta))  # noqa: SLF001 - some com as vazias
    return [{"fonte": "netease", "id": it["id"], "titulo": it["title"], "artista": it["artist"], "album": it["album"],
             "duracao": it["duration"], "sincronizada": bool(it.get("synced")), "palavras": bool(it.get("words"))}
            for it in itens]


@comp.letras_buscar
def buscar(dados):
    consulta = str(dados.get("texto") or f"{dados.get('artista') or ''} {dados.get('musica') or ''}").strip()
    if not consulta:
        return []
    tarefas = [f for f, ok in ((_netease, _ligada("netease")),) if ok]
    resultados = []
    with ThreadPoolExecutor(max_workers=max(1, len(tarefas))) as pool:
        for fut in [pool.submit(f, consulta) for f in tarefas]:
            try:
                resultados.extend(fut.result(timeout=18))
            except Exception as exc:  # noqa: BLE001 - uma fonte fora do ar nao derruba a outra
                log.info("busca falhou: %s", exc)
    return resultados


@comp.letras_obter
def obter(fonte, lid):
    try:
        if fonte == "netease":
            return letras.netease_lyrics(lid)
    except Exception as exc:  # noqa: BLE001
        raise Erro(("Não consegui baixar a letra: " if comp.idioma == "pt-BR" else "Couldn't get the lyrics: ")
                   + str(exc)[:200]) from None
    raise Erro(f"fonte desconhecida: {fonte}", 404)


if __name__ == "__main__":
    comp.rodar()
