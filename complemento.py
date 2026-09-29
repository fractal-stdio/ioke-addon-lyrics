"""Complemento "Letras extras" para o IOkê: NetEase e Musixmatch como fontes de letras
(API 1, pelo SDK karaoke_complemento.py)."""
import logging
from concurrent.futures import ThreadPoolExecutor

import letras
from karaoke_complemento import Complemento, Erro

log = logging.getLogger("complemento")
comp = Complemento()
_musixmatch = {}  # consulta -> texto (a busca do Musixmatch ja traz a letra)


def _ligada(fonte):
    return comp.opcoes.get(fonte, True) is not False


def _netease(consulta):
    itens = letras._check_netease(letras.netease_search(consulta))  # noqa: SLF001 - some com as vazias
    return [{"fonte": "netease", "id": it["id"], "titulo": it["title"], "artista": it["artist"], "album": it["album"],
             "duracao": it["duration"], "sincronizada": bool(it.get("synced")), "palavras": bool(it.get("words"))}
            for it in itens]


def _mxm(consulta):
    out = []
    for it in letras.musixmatch_search(consulta):
        _musixmatch[consulta] = it["text"]
        titulo = f'Melhor resultado para "{consulta}"' if comp.idioma == "pt-BR" else f'Best match for "{consulta}"'
        out.append({"fonte": "musixmatch", "id": consulta, "titulo": titulo, "artista": "", "album": "",
                    "duracao": None, "sincronizada": it["synced"], "palavras": it["words"]})
    return out


@comp.letras_buscar
def buscar(dados):
    consulta = str(dados.get("texto") or f"{dados.get('artista') or ''} {dados.get('musica') or ''}").strip()
    if not consulta:
        return []
    tarefas = [f for f, ok in ((_netease, _ligada("netease")), (_mxm, _ligada("musixmatch"))) if ok]
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
        if fonte == "musixmatch":
            if lid in _musixmatch:
                return _musixmatch[lid]
            itens = letras.musixmatch_search(lid)
            return itens[0]["text"] if itens else ""
    except Exception as exc:  # noqa: BLE001
        raise Erro(("Não consegui baixar a letra: " if comp.idioma == "pt-BR" else "Couldn't get the lyrics: ")
                   + str(exc)[:200]) from None
    raise Erro(f"fonte desconhecida: {fonte}", 404)


if __name__ == "__main__":
    comp.rodar()
