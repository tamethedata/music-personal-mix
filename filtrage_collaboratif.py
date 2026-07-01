import pandas as pd
import numpy as np
from sklearn.cluster import KMeans

# ============================================================
# ÉTAPE 1 — Profil d'affinité par morceau
# ============================================================
def build_track_affinity():
    df_historique = pd.read_csv("historique.csv")
    df_top = pd.read_csv("top_morceaux.csv")
    df_likes = pd.read_csv("likes.csv")
    df_playlist = pd.read_csv("playlist_tracks.csv")

    signal_historique = df_historique.groupby("track_id").size().reset_index(name="nb_ecoutes")
    signal_top = df_top.groupby("track_id").size().reset_index(name="nb_periodes")
    signal_likes = df_likes[["track_id"]].drop_duplicates()
    signal_likes["est_like"] = 1
    signal_playlist = df_playlist.groupby("track_id")["playlist"].nunique().reset_index(name="nb_playlists")

    df_final = signal_historique.merge(signal_top, on="track_id", how="outer")
    df_final = df_final.merge(signal_likes, on="track_id", how="outer")
    df_final = df_final.merge(signal_playlist, on="track_id", how="outer")
    df_final = df_final.fillna(0)
    df_final.to_csv("tracks_affinity.csv", index=False)
    return df_final


# ============================================================
# ÉTAPE 2 — Profil d'affinité par artiste
# ============================================================
def build_artist_affinity():
    df_top_artistes = pd.read_csv("top_artistes.csv")
    poids_periode = {"short_term": 1, "medium_term": 2, "long_term": 3}
    df_top_artistes["poids"] = df_top_artistes["periode"].map(poids_periode)
    affinite_artistes = df_top_artistes.groupby("nom")["poids"].sum().reset_index(name="affinite")
    return affinite_artistes


# ============================================================
# ÉTAPE 3 — Score recommandation par artiste
# ============================================================
def build_artist_recommendations(affinite_artistes):
    df_similar = pd.read_csv("similar_artists_lastfm.csv")
    df_reco = df_similar.merge(
        affinite_artistes,
        left_on="artiste_source",
        right_on="nom",
        how="inner"
    )
    df_reco["score_reco"] = df_reco["affinite"] * df_reco["score"]
    df_reco = df_reco.sort_values("score_reco", ascending=False)
    df_reco.to_csv("recommandation_artistes.csv", index=False)
    return df_reco


# ============================================================
# ÉTAPE 4 — KMeans clustering → 6 Daily Mix
# ============================================================
def build_daily_mix_clusters():
    df_tags = pd.read_csv("top_artists_tags_lastfm.csv")
    df_top_artistes = pd.read_csv("top_artistes.csv")

    artistes = df_top_artistes["nom"].unique()
    df_tags = df_tags[df_tags["artiste_source"].isin(artistes)]

    matrice = df_tags.pivot_table(
        index="artiste_source",
        columns="tag",
        values="poids_tag",
        fill_value=0
    )

    print(f"Matrice : {matrice.shape[0]} artistes × {matrice.shape[1]} tags")

    kmeans = KMeans(n_clusters=6, random_state=42, n_init=10)
    matrice["cluster"] = kmeans.fit_predict(matrice.values)

    tag_columns = [c for c in matrice.columns if c != "cluster"]
    centers = kmeans.cluster_centers_

    print("\n--- Résultat des 6 Daily Mix ---")
    for cluster_id in range(6):
        artistes_cluster = matrice[matrice["cluster"] == cluster_id].index.tolist()
        tag_dominant = tag_columns[np.argmax(centers[cluster_id])]
        print(f"\nDaily Mix {cluster_id+1} [{tag_dominant}] :")
        print(f"  {artistes_cluster}")

    matrice[["cluster"]].to_csv("daily_mix_clusters.csv")
    return matrice, kmeans, tag_columns


# ============================================================
# ÉTAPE 5 — Assigner les recommandations aux clusters
# ============================================================
def assign_recommendations_to_clusters():
    df_reco = pd.read_csv("recommandation_artistes.csv")
    df_clusters = pd.read_csv("daily_mix_clusters.csv")

    df_reco_clustered = df_reco.merge(
        df_clusters,
        left_on="artiste_source",
        right_on="artiste_source",
        how="inner"
    )

    df_reco_clustered.to_csv("recommandation_par_cluster.csv", index=False)

    for cluster_id in sorted(df_reco_clustered["cluster"].unique()):
        sous_df = df_reco_clustered[df_reco_clustered["cluster"] == cluster_id]
        top5 = sous_df.sort_values("score_reco", ascending=False).head(5)
        print(f"\n--- Daily Mix {cluster_id} ---")
        print(top5[["artiste_source", "artiste_similaire", "score_reco"]])

    return df_reco_clustered


# ============================================================
# ÉTAPE 6 — Daily Mix complet (tops + similaires)
# ============================================================
def build_complete_daily_mix():
    df_clusters = pd.read_csv("daily_mix_clusters.csv")
    df_reco = pd.read_csv("recommandation_artistes.csv")

    df_similaires_clustered = df_reco.merge(
        df_clusters[["artiste_source", "cluster"]],
        on="artiste_source",
        how="inner"
    )

    nouveaux_artistes = df_similaires_clustered[["artiste_similaire", "cluster"]].rename(
        columns={"artiste_similaire": "artiste_source"}
    ).drop_duplicates()

    daily_mix_complet = pd.concat([
        df_clusters[["artiste_source", "cluster"]],
        nouveaux_artistes
    ]).drop_duplicates(subset="artiste_source")

    daily_mix_complet.to_csv("daily_mix_complet.csv", index=False)
    return daily_mix_complet

def build_daily_mix_tracks():
    daily_mix_complet = pd.read_csv("daily_mix_complet.csv")
    df_top_tracks = pd.read_csv("artist_top_tracks_lastfm.csv")
    df_top_morceaux = pd.read_csv("top_morceaux.csv")
    df_track_affinity = pd.read_csv("tracks_affinity.csv")
    affinite_artistes = build_artist_affinity()

    TAILLE_MIX = 50
    NB_MORCEAUX_ANCRES = round(TAILLE_MIX / 3)      # ~17 morceaux connus
    NB_MORCEAUX_DECOUVERTE = TAILLE_MIX - NB_MORCEAUX_ANCRES  # ~33 morceaux découverte

    resultats = []

    for cluster_id in sorted(daily_mix_complet["cluster"].unique()):
        artistes_cluster = daily_mix_complet[daily_mix_complet["cluster"] == cluster_id]["artiste_source"].tolist()

        # ── 1/3 — ANCRES : tes artistes connus du cluster ──
        ancres = affinite_artistes[affinite_artistes["nom"].isin(artistes_cluster)]
        ancres = ancres.sort_values("affinite", ascending=False)

        # Répartir NB_MORCEAUX_ANCRES proportionnellement à l'affinité de chaque artiste
        total_affinite = ancres["affinite"].sum()
        morceaux_ancres = []

        for _, row_artiste in ancres.iterrows():
            artiste = row_artiste["nom"]
            part = row_artiste["affinite"] / total_affinite
            nb_morceaux_artiste = max(1, round(part * NB_MORCEAUX_ANCRES))

            morceaux_artiste = df_top_morceaux[df_top_morceaux["artiste"] == artiste]
            morceaux_scores = morceaux_artiste.merge(df_track_affinity, on="track_id", how="left").fillna(0)
            morceaux_scores["score_total"] = (
                morceaux_scores["nb_ecoutes"] + morceaux_scores["nb_periodes"] * 2
                + morceaux_scores["est_like"] * 3 + morceaux_scores["nb_playlists"] * 2
            )
            top_morceaux_connus = morceaux_scores.sort_values("score_total", ascending=False).head(nb_morceaux_artiste)

            for _, row in top_morceaux_connus.iterrows():
                morceaux_ancres.append({"cluster": cluster_id, "titre": row["titre"], "artiste": artiste, "type": "connu"})

        # Limiter strictement à NB_MORCEAUX_ANCRES (au cas où l'arrondi dépasse)
        morceaux_ancres = morceaux_ancres[:NB_MORCEAUX_ANCRES]

        # ── 2/3 — DÉCOUVERTE : diversifier un max d'artistes différents ──
        artistes_ancres_noms = ancres["nom"].tolist()
        artistes_decouverte = [a for a in artistes_cluster if a not in artistes_ancres_noms]

        morceaux_decouverte_dispo = df_top_tracks[df_top_tracks["artiste"].isin(artistes_decouverte)]

        # Pour diversifier : on prend le MEILLEUR morceau de CHAQUE artiste d'abord,
        # avant de reprendre un 2ème morceau du même artiste (round-robin)
        morceaux_par_artiste = {
            artiste: grp.sort_values("weight", ascending=False).to_dict("records")
            for artiste, grp in morceaux_decouverte_dispo.groupby("artiste")
        }

        morceaux_decouverte = []
        round_idx = 0
        while len(morceaux_decouverte) < NB_MORCEAUX_DECOUVERTE and any(morceaux_par_artiste.values()):
            for artiste, morceaux in morceaux_par_artiste.items():
                if round_idx < len(morceaux):
                    morceaux_decouverte.append({
                        "cluster": cluster_id,
                        "titre": morceaux[round_idx]["titre"],
                        "artiste": artiste,
                        "type": "decouverte"
                    })
                    if len(morceaux_decouverte) >= NB_MORCEAUX_DECOUVERTE:
                        break
            round_idx += 1

        resultats.extend(morceaux_ancres)
        resultats.extend(morceaux_decouverte)

    df_final = pd.DataFrame(resultats)
    df_final.to_csv("daily_mix_tracks.csv", index=False)
    return df_final


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("Étape 1 — Affinité par morceau...")
    df_tracks = build_track_affinity()
    print(f"→ {len(df_tracks)} morceaux uniques\n")

    print("Étape 2 — Affinité par artiste...")
    affinite_artistes = build_artist_affinity()
    print(affinite_artistes.sort_values("affinite", ascending=False).head(10))
    print()

    print("Étape 3 — Score recommandation artistes...")
    df_reco = build_artist_recommendations(affinite_artistes)
    print(df_reco[["artiste_source", "artiste_similaire", "score_reco"]].head(10))
    print()

    print("Étape 4 — KMeans clustering Daily Mix...")
    matrice, kmeans, tag_columns = build_daily_mix_clusters()
    print()

    print("Étape 5 — Assigner les recommandations aux clusters...")
    df_reco_clustered = assign_recommendations_to_clusters()
    print(f"→ {len(df_reco_clustered)} lignes dans df_reco_clustered")
    print()

    print("Étape 6 — Construire le Daily Mix complet (tops + similaires)...")
    daily_mix_complet = build_complete_daily_mix()
    print(f"→ {len(daily_mix_complet)} artistes dans daily_mix_complet")
    print(daily_mix_complet["cluster"].value_counts())

    print("Étape 7 — Construire les Daily Mix (morceaux finaux)...")
    daily_mix_tracks = build_daily_mix_tracks()
    print(f"→ {len(daily_mix_tracks)} morceaux au total")
    print(daily_mix_tracks.groupby("cluster")["type"].value_counts())

#uniquement en filtrage collaboratif (last fm donc peu de donnees) les dialy mix 