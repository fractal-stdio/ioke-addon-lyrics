"""NetEase e Musixmatch: letras sincronizadas (e palavra a palavra, quando tem).

- NetEase (music.163.com): boa cobertura de musicas internacionais e, em muitas, o tempo de cada
  PALAVRA (formato "yrc", convertido para LRC enhanced).
- Musixmatch (pelo syncedlyrics): 1 resultado, palavra a palavra quando tem.

Letras palavra a palavra ficam no formato LRC enhanced:
    [00:07.61]<00:07.61>Toss <00:08.24>your <00:08.75>dirty <00:09.20>shoes<00:09.95>
"""
import re
from concurrent.futures import ThreadPoolExecutor

import requests

UA = {"User-Agent": "IOkeAddonLyrics/1.0"}
TIMEOUT = 12
SYNCED_RE = re.compile(r"\[\d{1,3}:\d{2}(?:[.:]\d{1,3})?\]")
WORD_RE = re.compile(r"<\d{1,3}:\d{2}(?:[.:]\d{1,3})?>")


def is_synced(text):
    return bool(text) and len(SYNCED_RE.findall(text)) >= 3


def has_words(text):
    """A letra tem o tempo de cada palavra (LRC enhanced)?"""
    return bool(text) and len(WORD_RE.findall(text)) >= 10


def _stamp(ms):
    ms = max(0, int(ms))
    return f"{ms // 60000:02d}:{(ms % 60000) / 1000:05.2f}"


def ts(sec):
    """Segundos -> "mm:ss.xx" (formato das marcas do LRC)."""
    return _stamp(round(max(0.0, float(sec)) * 1000))


WORD_GAP = 0.06  # s: silencio minimo entre duas palavras que vale marcar


def timed_line(line_start, words):
    """Uma linha de LRC enhanced com o INICIO e o FIM de cada palavra.

    words: [(inicio, fim, texto)] em segundos; o texto pode trazer o espaco final.
    O fim so e escrito quando ha silencio antes da proxima palavra (e no fim da
    linha): uma marca seguida de espaco em branco quer dizer "a palavra anterior
    acabou aqui". Sem marca de fim, a palavra vai ate o inicio da proxima.

        [00:07.61]<00:07.61>Toss<00:08.10> <00:08.24>your <00:08.75>dirty<00:13.25>
    """
    out = [f"[{ts(line_start)}]"]
    for i, (start, end, text) in enumerate(words):
        core = text.rstrip()
        tail = text[len(core):]
        out.append(f"<{ts(start)}>{core}")
        if i + 1 == len(words):
            out.append(f"<{ts(end)}>")  # fim da ultima palavra = fim da linha
        elif words[i + 1][0] - end > WORD_GAP:
            out.append(f"<{ts(end)}>{tail}")  # palavra acabou, silencio ate a proxima
        else:
            out.append(tail)
    return "".join(out)


_YRC_LINE = re.compile(r"^\[(\d+),(\d+)\](.*)$")
_YRC_WORD = re.compile(r"\((\d+),(\d+),-?\d+\)")


def yrc_to_lrc(yrc):
    """Letra palavra a palavra do NetEase ("yrc") -> LRC enhanced, com o inicio E
    o fim de cada palavra (o yrc traz a duracao de cada uma)."""
    out = []
    for raw in (yrc or "").splitlines():
        m = _YRC_LINE.match(raw.strip())
        if not m:
            continue  # linhas de credito vem em JSON
        parts = _YRC_WORD.split(m.group(3))  # ['', ini, dur, texto, ini, dur, texto, ...]
        words = []
        for i in range(1, len(parts) - 2, 3):
            start, dur, text = int(parts[i]) / 1000, int(parts[i + 1]) / 1000, parts[i + 2]
            if not text:
                continue
            if not text.strip() and words:  # so espaco: vai para a palavra anterior
                s0, e0, t0 = words[-1]
                words[-1] = (s0, e0, t0 + text)
                continue
            words.append((start, start + max(dur, 0.01), text))
        if not words or _NETEASE_CREDIT_TEXT.search("".join(w[2] for w in words)):
            continue
        out.append(timed_line(int(m.group(1)) / 1000, words))
    return "\n".join(out)


_NETEASE_HEADERS = {**UA, "Referer": "https://music.163.com/"}


def netease_search(query):
    r = requests.post(
        "https://music.163.com/api/cloudsearch/pc",
        data={"s": query, "type": 1, "offset": 0, "limit": 12},
        headers=_NETEASE_HEADERS,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    result = r.json().get("result")
    songs = result.get("songs") if isinstance(result, dict) else None
    out = []
    for s in songs or []:
        out.append({
            "source": "netease",
            "id": str(s.get("id")),
            "artist": ", ".join(a.get("name") or "" for a in s.get("ar") or s.get("artists") or []),
            "title": s.get("name") or "",
            "album": (s.get("al") or s.get("album") or {}).get("name") or "",
            "duration": (s.get("dt") or s.get("duration") or 0) / 1000 or None,
            "synced": None,  # so sabemos depois de baixar
            "text": None,
        })
    return out


def netease_lyrics(song_id, words=True):
    """Letra do NetEase. Prefere a versao palavra a palavra (yrc) quando existe."""
    r = requests.get(
        "https://music.163.com/api/song/lyric/v1",
        params={"id": int(song_id), "lv": -1, "kv": -1, "tv": -1, "yv": -1},
        headers=_NETEASE_HEADERS,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    if words:
        enhanced = yrc_to_lrc((data.get("yrc") or {}).get("lyric") or "")
        if is_synced(enhanced) and has_words(enhanced):
            return enhanced
    text = (data.get("lrc") or {}).get("lyric") or ""
    # tira as linhas de credito em chines ("作词 : Fulano", "作曲 : ...")
    kept = [ln for ln in text.splitlines() if not _NETEASE_CREDIT_RE.search(ln) and not ln.lstrip().startswith("{")]
    return "\n".join(kept).strip() or None


_CREDIT_WORDS = r"(?:作词|作曲|编曲|制作人|制作|混音|母带|和声|吉他|贝斯|鼓|录音|监制|出品|词|曲)\s*[:：]"
_NETEASE_CREDIT_RE = re.compile(r"^\s*(?:\[[^\]]*\])+\s*" + _CREDIT_WORDS)
_NETEASE_CREDIT_TEXT = re.compile(r"^\s*" + _CREDIT_WORDS)


def musixmatch_search(query):
    try:
        import syncedlyrics
    except ImportError:
        return []
    # palavra a palavra quando o Musixmatch tem ("richsync"); senao, por linha
    try:
        text = syncedlyrics.search(query, providers=["Musixmatch"], enhanced=True)
    except Exception:  # noqa: BLE001
        text = None
    if not has_words(text):
        text = syncedlyrics.search(query, providers=["Musixmatch"]) or text
    if not text:
        return []
    return [{
        "source": "musixmatch",
        "id": query,
        "artist": "",
        "title": f"Melhor resultado para \"{query}\"",
        "album": "",
        "duration": None,
        "synced": is_synced(text),
        "words": has_words(text),
        "text": text,
    }]


def _check_netease(results, limit=10):
    """O NetEase lista muitas versoes sem letra (so os creditos de compositor,
    comum em musica brasileira). Baixa as primeiras em paralelo: some com as
    vazias e marca a situacao real (palavra a palavra / sincronizada / sem tempo)."""
    netease = [it for it in results if it["source"] == "netease"][:limit]
    if not netease:
        return results

    def load(it):
        try:
            return it, netease_lyrics(it["id"])
        except Exception:  # noqa: BLE001 - na duvida, mantem (o "Ver" tenta de novo)
            return it, False

    empty = set()
    with ThreadPoolExecutor(max_workers=len(netease)) as pool:
        for it, text in pool.map(load, netease):
            if text is False:
                continue
            if not text:
                empty.add(it["id"])
                continue
            it.update(text=text, synced=is_synced(text), words=has_words(text))
    extra = [it for it in results if it["source"] == "netease"][limit:]  # nao conferidas: ficam de fora
    return [it for it in results if it["source"] != "netease" or (it["id"] not in empty and it not in extra)]
