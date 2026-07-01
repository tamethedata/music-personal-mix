#recup des donnees de lapi web de spotify 

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import pandas as pd
import os

load_dotenv()

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="user-read-recently-played user-top-read user-library-read playlist-read-collaborative user-read-playback-state playlist-read-private"
))


def get_recently_played():
    historique = sp.current_user_recently_played(limit=50)
    morceaux = []
    for item in historique["items"]:
        track = item["track"]
        morceaux.append({
            "titre": track["name"],
            "artistes": ", ".join([a["name"] for a in track["artists"]]),
            "artistes_id": ", ".join([a["id"] for a in track["artists"]]),
            "track_id": track["id"],
            "album": track["album"]["name"],
            "album_release_date": track["album"]["release_date"],
            "date_ecoute": item["played_at"],
            "heure": pd.to_datetime(item["played_at"]).hour,
            "jour_semaine": pd.to_datetime(item["played_at"]).day_name()
        })
    df_nouveau = pd.DataFrame(morceaux)
    if os.path.exists("historique.csv"):
        df_existant = pd.read_csv("historique.csv")
        df_final = pd.concat([df_existant, df_nouveau]).drop_duplicates(subset=["track_id", "date_ecoute"])
    else:
        df_final = df_nouveau

    df_final.to_csv("historique.csv", index=False)
    return df_final


def get_top_artists():
    artistes = []
    for periode in ["short_term", "medium_term", "long_term"]:
        offset = 0
        while True:
            top_artistes = sp.current_user_top_artists(limit=50, offset=offset, time_range=periode)
            if not top_artistes["items"]:
                break
            for artiste in top_artistes["items"]:
                artistes.append({
                    "nom": artiste["name"],
                    "artiste_id": artiste["id"],
                    "periode": periode
                })
            offset += 50

    df = pd.DataFrame(artistes)
    df.to_csv("top_artistes.csv", index=False)
    return df


def get_top_tracks():
    tous_top = []
    for periode in ["short_term", "medium_term", "long_term"]:
        offset = 0
        while True:
            top = sp.current_user_top_tracks(limit=50, offset=offset, time_range=periode)
            if not top["items"]:
                break
            for track in top["items"]:
                tous_top.append({
                    "titre": track["name"],
                    "artiste": track["artists"][0]["name"],
                    "track_id": track["id"],
                    "album_release_date": track["album"]["release_date"],
                    "periode": periode
                })
            offset += 50

    df = pd.DataFrame(tous_top)
    df.to_csv("top_morceaux.csv", index=False)
    return df


def get_liked_tracks():
    likes = []
    offset = 0
    while True:
        resultats = sp.current_user_saved_tracks(limit=50, offset=offset)
        if not resultats["items"]:
            break
        for item in resultats["items"]:
            track = item["track"]
            likes.append({
                "titre": track["name"],
                "artiste": track["artists"][0]["name"],
                "track_id": track["id"],
                "album_release_date": track["album"]["release_date"]
            })
        offset += 50
    df = pd.DataFrame(likes)
    df.to_csv("likes.csv", index=False)
    return df


def get_playlist_tracks():
    liste_morceaux = []

    playlists_toutes = []
    offset_playlist = 0
    while True:
        playlists = sp.current_user_playlists(limit=50, offset=offset_playlist)
        if not playlists["items"]:
            break
        playlists_toutes.extend(playlists["items"])
        offset_playlist += 50

    print(f"Nombre total de playlists : {len(playlists_toutes)}")

    for playlist in playlists_toutes:
        playlist_id = playlist["id"]
        try:
            offset_tracks = 0
            while True:
                items = sp.playlist_items(playlist_id, limit=50, offset=offset_tracks)
                if not items["items"]:
                    break
                for item in items["items"]:
                    track = item.get("item")
                    if track:
                        liste_morceaux.append({
                            "titre": track["name"],
                            "artiste": track["artists"][0]["name"],
                            "track_id": track["id"],
                            "playlist": playlist["name"]
                        })
                offset_tracks += 50
        except Exception as e:
            print(f"Erreur playlist {playlist['name']}: {e}")

    print(f"Total morceaux récupérés : {len(liste_morceaux)}")
    df = pd.DataFrame(liste_morceaux)
    df.to_csv("playlist_tracks.csv", index=False)
    return df


if __name__ == "__main__":
    print("=== Historique récent ===")
    get_recently_played()

    print("\n=== Top artistes ===")
    get_top_artists()

    print("\n=== Top morceaux ===")
    get_top_tracks()

    print("\n=== Morceaux likés ===")
    get_liked_tracks()

    print("\n=== Morceaux des playlists ===")
    get_playlist_tracks()

    print("\nCollecte terminée !")