#!/usr/bin/env python3
"""Baixa imagens de fundo (paisagem) de séries, animes e filmes para o protetor de tela do dumbtv home.

Séries e animes: API pública do TVmaze (sem chave).
Filmes: TMDB, só se a variável TMDB_API_KEY estiver definida (chave gratuita em themoviedb.org).

Uso:
    python3 -I scripts/screensaver-images.py [pasta_destino] [--por-titulo N]
    ./scripts/screensaver.sh screensaver-images      # manda para a TV e liga o protetor

A pasta padrão é screensaver-images/ na raiz do repositório (fora do git).
Cada arquivo sai como "Categoria - Título - N.jpg"; o protetor de tela usa isso como legenda.
Uso pessoal: as imagens são material promocional dos estúdios.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "dumbtv-screensaver/1.0"}

# (categoria, busca, ano de estreia, só anime japonês?)
SERIES = [
    # Marvel
    ("Marvel", "Daredevil", 2015, False),
    ("Marvel", "Daredevil: Born Again", 2025, False),
    ("Marvel", "Loki", 2021, False),
    ("Marvel", "WandaVision", 2021, False),
    ("Marvel", "Agatha All Along", 2024, False),
    ("Marvel", "Moon Knight", 2022, False),
    ("Marvel", "Hawkeye", 2021, False),
    ("Marvel", "What If...?", 2021, False),
    ("Marvel", "X-Men '97", 2024, False),
    ("Marvel", "The Punisher", 2017, False),
    ("Marvel", "Jessica Jones", 2015, False),
    ("Marvel", "Agents of S.H.I.E.L.D.", 2013, False),
    ("Marvel", "The Falcon and the Winter Soldier", 2021, False),
    ("Marvel", "Your Friendly Neighborhood Spider-Man", 2025, False),
    # DC
    ("DC", "Peacemaker", 2022, False),
    ("DC", "The Penguin", 2024, False),
    ("DC", "Creature Commandos", 2024, False),
    ("DC", "Harley Quinn", 2019, False),
    ("DC", "The Flash", 2014, False),
    ("DC", "Arrow", 2012, False),
    ("DC", "Gotham", 2014, False),
    ("DC", "Titans", 2018, False),
    ("DC", "Doom Patrol", 2019, False),
    ("DC", "Superman & Lois", 2021, False),
    ("DC", "Smallville", 2001, False),
    ("DC", "Batman: The Animated Series", 1992, False),
    ("DC", "Young Justice", 2010, False),
    ("DC", "Batman: Caped Crusader", 2024, False),
    # Animes
    ("Anime", "Attack on Titan", 2013, True),
    ("Anime", "Demon Slayer: Kimetsu no Yaiba", 2019, True),
    ("Anime", "Jujutsu Kaisen", 2020, True),
    ("Anime", "One Piece", 1999, True),
    ("Anime", "Naruto Shippuden", 2007, True),
    ("Anime", "Dragon Ball Super", 2015, True),
    ("Anime", "Dragon Ball Z", 1989, True),
    ("Anime", "My Hero Academia", 2016, True),
    ("Anime", "Chainsaw Man", 2022, True),
    ("Anime", "Spy x Family", 2022, True),
    ("Anime", "Frieren: Beyond Journey's End", 2023, True),
    ("Anime", "Solo Leveling", 2024, True),
    ("Anime", "Dandadan", 2024, True),
    ("Anime", "Death Note", 2006, True),
    ("Anime", "Fullmetal Alchemist: Brotherhood", 2009, True),
    ("Anime", "Cowboy Bebop", 1998, True),
    ("Anime", "Hunter x Hunter", 2011, True),
    ("Anime", "One Punch Man", 2015, True),
    ("Anime", "Bleach", 2004, True),
    ("Anime", "Neon Genesis Evangelion", 1995, True),
    ("Anime", "Cyberpunk: Edgerunners", 2022, True),
    ("Anime", "Mob Psycho 100", 2016, True),
]

# (categoria, busca, ano)
FILMES = [
    ("Marvel", "Avengers: Endgame", 2019),
    ("Marvel", "Avengers: Infinity War", 2018),
    ("Marvel", "Iron Man", 2008),
    ("Marvel", "Black Panther", 2018),
    ("Marvel", "Guardians of the Galaxy", 2014),
    ("Marvel", "Spider-Man: No Way Home", 2021),
    ("Marvel", "Spider-Man: Into the Spider-Verse", 2018),
    ("Marvel", "Spider-Man: Across the Spider-Verse", 2023),
    ("Marvel", "Thor: Ragnarok", 2017),
    ("Marvel", "Doctor Strange", 2016),
    ("Marvel", "Deadpool & Wolverine", 2024),
    ("Marvel", "Logan", 2017),
    ("DC", "The Dark Knight", 2008),
    ("DC", "The Batman", 2022),
    ("DC", "Joker", 2019),
    ("DC", "Wonder Woman", 2017),
    ("DC", "Man of Steel", 2013),
    ("DC", "Superman", 2025),
    ("DC", "Aquaman", 2018),
    ("DC", "Zack Snyder's Justice League", 2021),
    ("DC", "The Suicide Squad", 2021),
    ("DC", "Batman Begins", 2005),
    ("Anime", "Spirited Away", 2001),
    ("Anime", "Your Name.", 2016),
    ("Anime", "Princess Mononoke", 1997),
    ("Anime", "Akira", 1988),
    ("Anime", "Suzume", 2022),
    ("Anime", "Demon Slayer: Kimetsu no Yaiba - The Movie: Mugen Train", 2020),
    ("Anime", "The Boy and the Heron", 2023),
    ("Anime", "Howl's Moving Castle", 2004),
    ("Anime", "Jujutsu Kaisen 0", 2021),
]


def get_json(url, tentativas=4):
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:  # TVmaze: 20 pedidos a cada 10 s
                time.sleep(3 + i * 2)
                continue
            if e.code == 404:
                return None
            raise
    return None


def baixar(url, destino):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        dados = r.read()
    if len(dados) < 20_000 or not (dados[:3] == b"\xff\xd8\xff" or dados[:8] == b"\x89PNG\r\n\x1a\n"):
        raise ValueError("não parece uma imagem")
    tmp = destino + ".part"
    with open(tmp, "wb") as f:
        f.write(dados)
    os.replace(tmp, destino)
    return len(dados)


def nome_arquivo(cat, titulo, n, ext):
    limpo = re.sub(r'[<>:"/\\|?*]', "", titulo).replace(" - ", " – ").strip()
    return f"{cat} - {limpo} - {n}{ext}"


def ano(s):
    return int(s[:4]) if s and s[:4].isdigit() else None


def serie_tvmaze(busca, ano_esperado, anime):
    res = get_json("https://api.tvmaze.com/search/shows?q=" + urllib.parse.quote(busca)) or []
    candidatos = [r["show"] for r in res]
    if anime:
        candidatos = [s for s in candidatos if (s.get("language") or "") == "Japanese"]
    for s in candidatos:
        a = ano(s.get("premiered"))
        if a and abs(a - ano_esperado) <= 1:
            return s
    return candidatos[0] if candidatos else None


def fundos_tvmaze(show_id, limite):
    imgs = get_json(f"https://api.tvmaze.com/shows/{show_id}/images") or []
    fundos = [i for i in imgs if i.get("type") == "background" and i.get("resolutions", {}).get("original")]
    fundos.sort(key=lambda i: (not i.get("main"), -(i["resolutions"]["original"].get("width") or 0)))
    return [i["resolutions"]["original"]["url"] for i in fundos[:limite]]


def fundos_tmdb(chave, busca, ano_esperado, limite):
    q = urllib.parse.urlencode({"api_key": chave, "query": busca, "year": ano_esperado})
    res = (get_json("https://api.themoviedb.org/3/search/movie?" + q) or {}).get("results") or []
    if not res:
        return None, []
    filme = res[0]
    # include_image_language=null: só imagens sem texto/logo, melhores para fundo.
    q = urllib.parse.urlencode({"api_key": chave, "include_image_language": "null"})
    imgs = (get_json(f"https://api.themoviedb.org/3/movie/{filme['id']}/images?" + q) or {}).get("backdrops") or []
    imgs.sort(key=lambda i: (-(i.get("vote_average") or 0), -(i.get("width") or 0)))
    urls = [f"https://image.tmdb.org/t/p/w1920{i['file_path']}" for i in imgs[:limite]]
    return filme.get("title"), urls


def main():
    args = [a for a in sys.argv[1:]]
    limite = 2
    if "--por-titulo" in args:
        i = args.index("--por-titulo")
        limite = int(args[i + 1])
        del args[i:i + 2]
    pasta = args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screensaver-images")
    os.makedirs(pasta, exist_ok=True)

    total = 0
    faltou = []
    for cat, busca, a, anime in SERIES:
        s = serie_tvmaze(busca, a, anime)
        time.sleep(0.6)
        if not s:
            faltou.append(busca)
            continue
        urls = fundos_tvmaze(s["id"], limite)
        time.sleep(0.6)
        if not urls:
            faltou.append(busca)
            continue
        for n, url in enumerate(urls, 1):
            destino = os.path.join(pasta, nome_arquivo(cat, s["name"], n, ".jpg"))
            if os.path.exists(destino):
                continue
            try:
                kb = baixar(url, destino) // 1024
                total += 1
                print(f"ok  {cat:6} {s['name']} #{n} ({kb} KB)")
            except Exception as e:  # noqa: BLE001
                print(f"erro {busca}: {e}")

    chave = os.environ.get("TMDB_API_KEY", "").strip()
    if chave:
        for cat, busca, a in FILMES:
            titulo, urls = fundos_tmdb(chave, busca, a, limite)
            time.sleep(0.3)
            if not urls:
                faltou.append(busca)
                continue
            for n, url in enumerate(urls, 1):
                destino = os.path.join(pasta, nome_arquivo(cat, titulo, n, ".jpg"))
                if os.path.exists(destino):
                    continue
                try:
                    kb = baixar(url, destino) // 1024
                    total += 1
                    print(f"ok  {cat:6} {titulo} #{n} ({kb} KB)")
                except Exception as e:  # noqa: BLE001
                    print(f"erro {busca}: {e}")
    else:
        print("filmes: pulados (defina TMDB_API_KEY para baixar fundos de filmes)")

    print(f"\n{total} imagens novas em {os.path.abspath(pasta)}")
    if faltou:
        print("sem imagem:", ", ".join(faltou))


if __name__ == "__main__":
    main()
