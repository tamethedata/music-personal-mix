import pylast
import pandas as pd
import os
from dotenv import load_dotenv
import time

load_dotenv()

lf = pylast.LastFMNetwork(api_key=os.getenv("LASTFM_API_KEY"))
API_KEY = os.getenv("LASTFM_API_KEY")


def get_similar_artists_lastfm():
    df = pd.read_csv("top_artistes.csv")
    resultats = []
    for artist in df["nom"].unique():
        try:
            artistt = lf.get_artist(artist)
            similaires = artistt.get_similar(limit=10)
            for s in similaires:
                resultats.append({
                    "artiste_source": artist,
                    "artiste_similaire": s.item.name,
                    "score": s.match
                })
        except Exception as e:
            print(f"Erreur pour {artist}: {e}")

    df_final = pd.DataFrame(resultats)
    df_final.to_csv("similar_artists_lastfm.csv", index=False)
    return df_final

def get_top_artists_tags():
    df = pd.read_csv("top_artistes.csv")
    res = []
    for artist in df["nom"].unique():
        succes = False
        for tentative in range(5):
            try:
                artistt = lf.get_artist(artist)
                tags = artistt.get_top_tags(limit=5)
                for tag in tags:
                    res.append({
                        "artiste_source": artist,
                        "tag": tag.item.name,
                        "poids_tag": tag.weight
                    })
                succes = True
                break  # Sort de la boucle des tentatives si ça fonctionne
            except Exception as e:
                # On augmente le temps d'attente à chaque échec (3s, puis 6s, puis 9s...)
                attente = (tentative + 1) * 3
                print(f"Tentative {tentative+1} échouée pour {artist}: {e}. Attente de {attente}s...")
                time.sleep(attente)
        
        if not succes:
            print(f"ÉCHEC DÉFINITIF pour {artist}")
      
        time.sleep(1)
    
    df_final = pd.DataFrame(res)
    df_final.to_csv("top_artists_tags_lastfm.csv", index=False)
    return df_final

def get_artist_top_tracks_lastfm():
    df = pd.read_csv("similar_artists_lastfm.csv")
    resultats = []
    for artist in df["artiste_similaire"].unique():
        try:
            artistt = lf.get_artist(artist)
            top_tracks = artistt.get_top_tracks(limit=10)
            for track in top_tracks:
                resultats.append({
                    "artiste": artist,
                    "titre": track.item.title,
                    "weight": track.weight
                })
        except Exception as e:
            print(f"Erreur pour {artist}: {e}")

    df_final = pd.DataFrame(resultats)
    df_final.to_csv("artist_top_tracks_lastfm.csv", index=False)
    return df_final


if __name__ == "__main__":
    print("=== Artistes similaires ===")
    df_similar = get_similar_artists_lastfm()
    print(df_similar)

    print("\n=== Tags des top artistes ===")
    df_tags = get_top_artists_tags()
    print(df_tags)

    print("\n=== Top tracks des artistes similaires ===")
    df_top_tracks = get_artist_top_tracks_lastfm()
    print(df_top_tracks)