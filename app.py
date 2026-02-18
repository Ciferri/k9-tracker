import streamlit as st
import sqlite3
import pandas as pd
import os
import altair as alt

# --- CONFIGURATION ET CHEMINS ---
st.set_page_config(page_title="K9-Tracker Analytics", page_icon="🐕", layout="wide")

# Chemin relatif vers la base de données depuis le dossier /web
DB_PATH = "../data/agility_complete.db"

def load_data(query, params=()):
    """Connexion sécurisée à la base de données"""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except sqlite3.OperationalError:
        st.error(f"❌ Impossible de trouver la base de données à l'adresse : {DB_PATH}")
        return pd.DataFrame()

# --- SIDEBAR STYLE ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/616/616408.png", width=100)
st.sidebar.title("K9-Tracker v1.0")
menu = st.sidebar.selectbox("Menu Principal", ["🏠 Tableau de Bord", 
    "🔍 Recherche Profil", "🏆 Top 10 par Race", "📊 Statistiques Régionales", 
    "👨‍⚖️ Analyse des Juges","⚔️ Mode Versus"])

# --- PAGE 1 : TABLEAU DE BORD (Accueil) ---
if menu == "🏠 Tableau de Bord":
    st.title("🐾 Bienvenue sur K9-Tracker")
    
    st.markdown("""
    ### L'encyclopédie vivante de l'Agility
    Explorez la plus grande base de données de résultats d'agility en France. **K9-Tracker** centralise les données 
    pour offrir une vision statistique globale.
    """)
    st.markdown("---")

    # 1. CHIFFRES CLÉS (Les infos "sympas")
    stats = load_data("""
        SELECT 
            (SELECT COUNT(*) FROM resultats) as total_lignes,
            (SELECT COUNT(DISTINCT id_concours) FROM liste_concours) as total_concours,
            (SELECT COUNT(DISTINCT nom_chien) FROM resultats) as total_chiens,
            (SELECT COUNT(DISTINCT conducteur) FROM resultats) as total_conducteurs
    """)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Parcours analysés", f"{int(stats['total_lignes'][0]):,}".replace(',', ' '))
    col2.metric("Concours", f"{int(stats['total_concours'][0]):,}".replace(',', ' '))
    col3.metric("Chiens suivis", f"{int(stats['total_chiens'][0]):,}".replace(',', ' '))
    col4.metric("Conducteurs", f"{int(stats['total_conducteurs'][0]):,}".replace(',', ' '))

    st.markdown("---")

    # 2. LES 10 DERNIERS CONCOURS (Division par 3 et Tri chronologique)
    st.subheader("🗓️ Derniers événements intégrés")
    
    query_recents = """
        SELECT 
            lc.date_concours AS Date, 
            lc.nom_concours AS [Club Organisateur],
            (COUNT(r.id_concours) / 3) AS [Participants (est.)]
        FROM liste_concours lc
        LEFT JOIN resultats r ON lc.id_concours = r.id_concours
        GROUP BY lc.id_concours
        ORDER BY 
            SUBSTR(lc.date_concours, 7, 4) DESC,
            SUBSTR(lc.date_concours, 4, 2) DESC,
            SUBSTR(lc.date_concours, 1, 2) DESC
        LIMIT 10
    """
    
    df_recents = load_data(query_recents)
    if not df_recents.empty:
        st.table(df_recents)

    # 3. GRAPHIQUE DES RACES (Version Altair Ultra-Précise)
    st.markdown("---")
    st.subheader("🐕 Top 10 des races les plus actives")
    
    top_races = load_data("""
        SELECT race, COUNT(*) as nb 
        FROM resultats 
        WHERE race IS NOT NULL AND race != '' 
        GROUP BY race 
        ORDER BY nb DESC 
        LIMIT 10
    """)
    
    if not top_races.empty:
        # Création du graphique Altair avec affichage complet des noms
        chart = alt.Chart(top_races).mark_bar(color="#ff4b4b").encode(
            x=alt.X("nb:Q", title="Nombre de parcours"),
            y=alt.Y(
                "race:N", 
                sort="-x", 
                title="Race",
                axis=alt.Axis(labelLimit=300) # <-- Augmente la limite de pixels pour le texte
            ),
            tooltip=["race", "nb"]
        ).properties(
            height=400
        ).configure_axis(
            labelFontSize=12 # Optionnel : ajuste la taille de la police si besoin
        )
        
        st.altair_chart(chart, use_container_width=True)


# --- PAGE 2 : RECHERCHE ---
elif menu == "🔍 Recherche Profil":
    st.title("🔎 Recherche & Analyses")

    # 1. BARRE DE RECHERCHE LARGE
    search_query = st.text_input("Rechercher un chien ou un conducteur", placeholder="Ex: Pixi...").upper()

    if search_query:
        # On récupère l'id_couple en plus des infos d'affichage
        search_results = load_data("""
            SELECT DISTINCT id_couple, nom_chien, conducteur, race 
            FROM resultats 
            WHERE UPPER(nom_chien) LIKE ? OR UPPER(conducteur) LIKE ?
            LIMIT 50
        """, (f'%{search_query}%', f'%{search_query}%'))

        if not search_results.empty:
            # On stocke l'id_couple de manière invisible dans la liste via un dictionnaire
            options_dict = {f"{row['nom_chien']} ({row['conducteur']} - {row['race']})": row['id_couple'] for _, row in search_results.iterrows()}
            options_list = list(options_dict.keys())
            
            selection = st.selectbox("🎯 Résultats trouvés, choisissez le profil à analyser :", ["--- Choisir un profil ---"] + options_list)
            
            if selection != "--- Choisir un profil ---":
                # On récupère l'id_couple correspondant à la sélection
                selected_id_couple = options_dict[selection]
                
                # On extrait les noms juste pour l'affichage du titre
                selected_dog = selection.split(" (")[0]
                selected_conducteur = selection.split(" (")[1].split(" - ")[0]
                
                st.markdown("---")
                st.header(f"📊 Statistiques du couple {selected_dog} & {selected_conducteur}")

                # Récupération dynamique des années via id_couple
                df_years = load_data("""
                    SELECT DISTINCT SUBSTR(lc.date_concours, 7, 4) as annee
                    FROM resultats r
                    JOIN liste_concours lc ON r.id_concours = lc.id_concours
                    WHERE r.id_couple = ?
                    ORDER BY annee DESC
                """, (selected_id_couple,))
                
                annees_chien = df_years['annee'].tolist() if not df_years.empty else ["2026"]

                # 2. MÉTRIQUES : TAUX DE RÉUSSITE ET ÉLIMINATIONS

                st.markdown("---")
                col_filtre1, col_filtre2 = st.columns(2)
                
                with col_filtre1:
                    choix_annee_stats = st.selectbox("📅 Année pour les statistiques :", annees_chien)
                with col_filtre2:
                    choix_epreuve = st.radio("🏃 Type d'épreuve :", ["Toutes", "Agility", "Jumping"], horizontal=True)

                # Préparation de la variable SQL pour le filtre d'épreuve
                like_epreuve = "%" if choix_epreuve == "Toutes" else f"%{choix_epreuve}%"

                # 2. MÉTRIQUES : TAUX DE RÉUSSITE ET ÉLIMINATIONS
                stats_perf = load_data("""
                    SELECT 
                        COUNT(r.id) as total,
                        SUM(CASE 
                            WHEN (r.vitesse != '-' AND r.vitesse != '' AND r.vitesse IS NOT NULL AND r.vitesse != '0') 
                             AND (r.penalites IN ('0', '0.00', '0,00', '-', '') OR r.penalites IS NULL) 
                            THEN 1 ELSE 0 
                        END) as sans_faute,
                        SUM(CASE 
                            WHEN (r.vitesse = '-' OR r.vitesse = '' OR r.vitesse IS NULL OR r.vitesse = '0') 
                            THEN 1 ELSE 0 
                        END) as elimines
                    FROM resultats r
                    JOIN liste_concours lc ON r.id_concours = lc.id_concours
                    WHERE r.id_couple = ? 
                      AND SUBSTR(lc.date_concours, 7, 4) = ?
                      AND UPPER(r.nom_epreuve) LIKE UPPER(?)
                """, (selected_id_couple, choix_annee_stats, like_epreuve))

                col1, col2, col3 = st.columns(3)
                total_runs = stats_perf['total'][0]
                
                if total_runs > 0:
                    nb_sans_faute = stats_perf['sans_faute'][0]
                    nb_elimines = stats_perf['elimines'][0]
                    reussite = (nb_sans_faute / total_runs) * 100
                    taux_elim = (nb_elimines / total_runs) * 100
                    
                    col1.metric(f"Taux de Réussite", f"{reussite:.1f}%", help=f"{nb_sans_faute} parcours Sans Faute")
                    col2.metric(f"Taux d'Élimination", f"{taux_elim:.1f}%", help=f"{nb_elimines} éliminations")
                else:
                    col1.metric("Taux de Réussite", "0.0%")
                    col2.metric("Taux d'Élimination", "0.0%")
                    
                col3.metric("Parcours effectués", total_runs)

                # 3. GRAPHIQUES : Vitesse et Répartition des fautes
                st.markdown("---")
                col_chart1, col_chart2 = st.columns(2)

                # --- A. Histogramme + Courbe (Vitesse) ---
                with col_chart1:
                    st.subheader(f"📈 Évolution de la vitesse ({choix_epreuve})")
                    df_vitesse = load_data("""
                        SELECT 
                            SUBSTR(lc.date_concours, 4, 2) as mois,
                            AVG(CAST(r.vitesse AS FLOAT)) as moyenne_vit
                        FROM resultats r
                        JOIN liste_concours lc ON r.id_concours = lc.id_concours
                        WHERE r.id_couple = ? 
                        AND SUBSTR(lc.date_concours, 7, 4) = ?
                        AND UPPER(r.nom_epreuve) LIKE UPPER(?)
                        AND r.qualificatif != 'Eliminé' 
                        AND r.vitesse > 0
                        GROUP BY mois ORDER BY mois ASC
                    """, (selected_id_couple, choix_annee_stats, like_epreuve))

                    if not df_vitesse.empty:
                        mois_noms = {"01":"Jan", "02":"Fév", "03":"Mar", "04":"Avr", "05":"Mai", "06":"Juin", 
                                     "07":"Juil", "08":"Août", "09":"Sept", "10":"Oct", "11":"Nov", "12":"Déc"}
                        df_vitesse['mois_nom'] = df_vitesse['mois'].map(mois_noms)

                        bars = alt.Chart(df_vitesse).mark_bar(color="#ff4b4b", opacity=0.4).encode(
                            x=alt.X("mois_nom:N", sort=list(mois_noms.values()), title="Mois"),
                            y=alt.Y("moyenne_vit:Q", title="Vitesse (m/s)")
                        )
                        line = alt.Chart(df_vitesse).mark_line(color="#1f77b4", size=3).encode(
                            x=alt.X("mois_nom:N", sort=list(mois_noms.values())),
                            y=alt.Y("moyenne_vit:Q")
                        )
                        st.altair_chart(bars + line, use_container_width=True)

                # --- B. Camembert : Répartition des fautes ---
                with col_chart2:
                    st.subheader(f"🎯 Précision des parcours ({choix_epreuve})")
                    
                    df_raw = load_data("""
                        SELECT r.vitesse, r.penalites
                        FROM resultats r
                        JOIN liste_concours lc ON r.id_concours = lc.id_concours
                        WHERE r.id_couple = ? 
                        AND SUBSTR(lc.date_concours, 7, 4) = ?
                        AND UPPER(r.nom_epreuve) LIKE UPPER(?)
                    """, (selected_id_couple, choix_annee_stats, like_epreuve))

                    if not df_raw.empty:
                        def categoriser(row):
                            vit = str(row['vitesse']).strip()
                            pen_str = str(row['penalites']).replace(',', '.').strip()
                            if vit in ['-', '', '0', 'None']: return 'Eliminé'
                            try:
                                pen = float(pen_str) if pen_str not in ['-', ''] else 0.0
                                if pen == 0: return 'Sans Faute'
                                if pen <= 5: return 'Excellent'
                                if pen <= 10: return 'Très Bon'
                                return 'Bon'
                            except:
                                return 'Sans Faute' if pen_str == '-' else 'Bon'

                        df_raw['Categorie'] = df_raw.apply(categoriser, axis=1)
                        df_pie = df_raw['Categorie'].value_counts().reset_index()
                        df_pie.columns = ['Categorie', 'Nb']

                        total = df_pie['Nb'].sum()
                        df_pie['Taux'] = (df_pie['Nb'] / total * 100).round(1)

                        categories_fixes = pd.DataFrame({'Categorie': ['Sans Faute', 'Excellent', 'Très Bon', 'Bon', 'Eliminé']})
                        df_plot = pd.merge(categories_fixes, df_pie, on='Categorie', how='left').fillna(0)
                        
                        df_plot['Label_Legend'] = df_plot.apply(
                            lambda x: f"{x['Categorie']} ({x['Taux']:.1f}%)" if x['Nb'] > 0 else x['Categorie'], 
                            axis=1
                        )

                        chart = alt.Chart(df_plot).mark_arc(innerRadius=60).encode(
                            theta=alt.Theta(field="Nb", type="quantitative"),
                            color=alt.Color(field="Label_Legend", type="nominal", 
                                scale=alt.Scale(
                                    domain=df_plot['Label_Legend'].tolist(),
                                    range=['#2ecc71', '#98e690', '#f1c40f', '#e67e22', '#95a5a6']
                                ),
                                legend=alt.Legend(title="Qualification")
                            ),
                            tooltip=[
                                alt.Tooltip('Categorie', title='Résultat'),
                                alt.Tooltip('Nb', title='Nombre'),
                                alt.Tooltip('Taux', title='Taux (%)', format='.1f')
                            ]
                        ).properties(height=300)

                        st.altair_chart(chart, use_container_width=True)
                        st.write(f"📊 Analyse basée sur **{total}** parcours au total.")
                    else:
                        st.info("Aucune donnée pour ce type d'épreuve.")
                        
                # 4. TABLEAU HISTORIQUE FILTRABLE
                st.markdown("---")
                st.subheader("📋 Historique des concours")
                choix_annee_tab = st.selectbox("Filtrer le tableau par année :", ["Toutes"] + annees_chien)

                query_hist = """
                    SELECT lc.date_concours AS Date, lc.nom_concours AS Lieu, r.nom_epreuve, r.vitesse, r.penalites, r.qualificatif 
                    FROM resultats r
                    JOIN liste_concours lc ON r.id_concours = lc.id_concours
                    WHERE r.id_couple = ? AND UPPER(r.nom_epreuve) LIKE UPPER(?)
                """
                params = [selected_id_couple, like_epreuve]
                if choix_annee_tab != "Toutes":
                    query_hist += " AND SUBSTR(lc.date_concours, 7, 4) = ?"
                    params.append(choix_annee_tab)
                
                query_hist += " ORDER BY SUBSTR(lc.date_concours, 7, 4) DESC, SUBSTR(lc.date_concours, 4, 2) DESC, SUBSTR(lc.date_concours, 1, 2) DESC"
                st.dataframe(load_data(query_hist, tuple(params)), use_container_width=True, hide_index=True)        
                
        else:
            st.warning(f"Aucun résultat trouvé pour '{search_query}'.")

# --- PAGE 3 : TOP 10 ---
elif menu == "🏆 Top 10 par Race":
    st.title("🏆 Hall of Fame par Race")
    races = load_data("SELECT DISTINCT race FROM resultats WHERE race IS NOT NULL AND race != '' ORDER BY race")
    choix_race = st.selectbox("Sélectionnez une race", races)
    
    if choix_race:
        # On ajoute le tiret '-' dans la liste des pénalités acceptées
        query = """
            SELECT nom_chien, conducteur, vitesse, region, club, penalites
            FROM resultats 
            WHERE UPPER(race) = UPPER(?) 
            AND (penalites IN ('0', '0.00', '0,00', '', '-') OR penalites IS NULL)
            AND vitesse > 0
            ORDER BY CAST(vitesse AS FLOAT) DESC 
            LIMIT 10
        """
        top_dogs = load_data(query, (choix_race,))
        
        if not top_dogs.empty:
            st.subheader(f"Les 10 {choix_race} les plus rapides ⚡ (Sans-faute)")
            st.table(top_dogs)
        else:
            st.warning(f"Aucun 'sans-faute' détecté pour {choix_race}.")

# --- PAGE 4 : RÉGIONS ---
elif menu == "📊 Statistiques Régionales":
    st.title("📍 Comparatif National par Région")
    st.markdown("Découvrez quelles régions françaises ont les parcours les plus rapides et les meilleurs taux de réussite.")

    # 1. FILTRES DE RECHERCHE
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        # On extrait les années disponibles dans la base
        annees_db = load_data("SELECT DISTINCT SUBSTR(date_concours, 7, 4) as annee FROM liste_concours ORDER BY annee DESC")
        liste_annees = ["Toutes"] + annees_db['annee'].dropna().tolist() if not annees_db.empty else ["Toutes"]
        choix_annee_reg = st.selectbox("📅 Année :", liste_annees)
        
    with col_f2:
        choix_grade = st.selectbox("🏆 Niveau (Grade) :", ["Tous les grades", "Grade 1", "Grade 2", "Grade 3"])

    # Construction dynamique de la requête SQL
    query_reg = """
        SELECT 
            UPPER(TRIM(r.region)) as Region,
            COUNT(r.id) as Total_Parcours,
            
            -- Calcul de la Vitesse Moyenne
            AVG(CASE WHEN CAST(REPLACE(r.vitesse, ',', '.') AS FLOAT) > 0 
                     THEN CAST(REPLACE(r.vitesse, ',', '.') AS FLOAT) ELSE NULL END) as Vitesse_Moyenne,
                     
            -- Calcul des Sans Faute
            SUM(CASE WHEN (r.vitesse != '-' AND r.vitesse != '' AND r.vitesse IS NOT NULL AND r.vitesse != '0') 
                      AND (r.penalites IN ('0', '0.00', '0,00', '-', '') OR r.penalites IS NULL) 
                     THEN 1 ELSE 0 END) as Sans_Faute
                     
        FROM resultats r
        JOIN liste_concours lc ON r.id_concours = lc.id_concours
        WHERE r.region IS NOT NULL 
          AND TRIM(r.region) != '' 
          -- LA LISTE NOIRE DES PAYS ÉTRANGERS
          AND UPPER(TRIM(r.region)) NOT IN (
              'ETRANGER', 'SUISSE', 'ESPAGNE', 'BELGIQUE', 'ALLEMAGNE', 
              'ITALIE', 'LUXEMBOURG', 'PAYS-BAS', 'PAYS BAS', 'MONACO', 
              'ANDORRE', 'ROYAUME-UNI', 'ANGLETERRE', 'PORTUGAL'
          )
    """
    
    params = []
    
    # Ajout du filtre Année
    if choix_annee_reg != "Toutes":
        query_reg += " AND SUBSTR(lc.date_concours, 7, 4) = ?"
        params.append(choix_annee_reg)
        
    # Ajout du filtre Grade (Recherche du mot "Grade 1", "Grade 2", etc. dans le nom de l'épreuve)
    if choix_grade != "Tous les grades":
        query_reg += " AND UPPER(r.nom_epreuve) LIKE ?"
        params.append(f"%{choix_grade.upper()}%")

    # On regroupe par région et on filtre pour avoir un minimum de représentativité (ex: > 50 parcours)
    query_reg += """
        GROUP BY Region
        HAVING Total_Parcours > 50
        ORDER BY Vitesse_Moyenne DESC
    """

    df_stats = load_data(query_reg, tuple(params))

    if not df_stats.empty:
        # Calcul du Taux de Réussite en Python
        df_stats['Taux_Reussite'] = (df_stats['Sans_Faute'] / df_stats['Total_Parcours'] * 100).round(1)
        df_stats['Vitesse_Moyenne'] = df_stats['Vitesse_Moyenne'].round(2)

        st.markdown("---")
        
        # 1. On calcule une hauteur dynamique pour que chaque barre respire (ex: 35 pixels par région)
        hauteur_graphique = max(400, len(df_stats) * 35)

        col_c1, col_c2 = st.columns(2)

        # GRAPHIQUE 1 : Vitesse Moyenne
        with col_c1:
            st.subheader("⚡ Palmarès de la Vitesse (m/s)")
            
            # On crée une "fenêtre" de 500px de haut avec une bordure
            with st.container(height=500, border=True):
                chart_vitesse = alt.Chart(df_stats).mark_bar(color="#3498db", cornerRadiusEnd=4).encode(
                    x=alt.X("Vitesse_Moyenne:Q", title="Vitesse Moyenne (m/s)", scale=alt.Scale(zero=False)),
                    y=alt.Y("Region:N", sort="-x", title="Région", axis=alt.Axis(labelLimit=500)),
                    tooltip=["Region", "Vitesse_Moyenne", "Total_Parcours"]
                ).properties(height=hauteur_graphique) # On applique la grande hauteur au graphique
                
                text_vitesse = chart_vitesse.mark_text(align='left', baseline='middle', dx=3).encode(text='Vitesse_Moyenne:Q')
                st.altair_chart(chart_vitesse + text_vitesse, use_container_width=True)

        # GRAPHIQUE 2 : Taux de Réussite
        with col_c2:
            st.subheader("🎯 Taux de Réussite (%)")
            
            # Pareil ici, une fenêtre de 500px
            with st.container(height=500, border=True):
                chart_reussite = alt.Chart(df_stats).mark_bar(color="#2ecc71", cornerRadiusEnd=4).encode(
                    x=alt.X("Taux_Reussite:Q", title="Taux de Réussite (%)"),
                    y=alt.Y("Region:N", sort="-x", title="", axis=alt.Axis(labelLimit=500)),
                    tooltip=["Region", "Taux_Reussite", "Total_Parcours"]
                ).properties(height=hauteur_graphique)
                
                text_reussite = chart_reussite.mark_text(align='left', baseline='middle', dx=3).encode(text='Taux_Reussite:Q')
                st.altair_chart(chart_reussite + text_reussite, use_container_width=True)

        st.info("💡 Note : Les régions ayant enregistré moins de 50 parcours selon vos filtres sont masquées pour garantir la pertinence des moyennes. Vous pouvez faire défiler les graphiques vers le bas.")
    else:
        st.warning("Aucune donnée suffisante pour ces critères.")
        
# --- PAGE 5 : JUGES ---
elif menu == "👨‍⚖️ Analyse des Juges":
    st.title("⚖️ Analyse des Juges")
    st.markdown("Découvrez le profil des juges : qui dessine les parcours les plus fluides ? Qui pose les plus grands défis techniques ?")

    # 1. FILTRE PAR GRADE (Nouveauté)
    st.sidebar.markdown("---") # Petit séparateur visuel dans la barre latérale si besoin, ou juste ici en haut de page
    
    col_filter, col_vide = st.columns([1, 2])
    with col_filter:
        choix_grade_juge = st.selectbox(
            "🏆 Filtrer par Niveau :", 
            ["Tous les grades", "Grade 1", "Grade 2", "Grade 3"]
        )

    # Préparation du filtre SQL
    sql_grade_filter = ""
    params_grade = []
    
    if choix_grade_juge != "Tous les grades":
        # On cherche le mot "Grade X" dans le nom de l'épreuve
        sql_grade_filter = "AND UPPER(nom_epreuve) LIKE ?"
        params_grade.append(f"%{choix_grade_juge.upper()}%")

    # 2. REQUÊTE PRINCIPALE (DYNAMIQUE)
    # On intègre le filtre sql_grade_filter directement dans la clause WHERE
    query_juges = f"""
        SELECT 
            UPPER(TRIM(juge)) as Juge,
            COUNT(id) as Total_Parcours,
            
            -- Calcul Vitesse Moyenne
            AVG(CASE WHEN CAST(REPLACE(vitesse, ',', '.') AS FLOAT) > 0 
                     THEN CAST(REPLACE(vitesse, ',', '.') AS FLOAT) ELSE NULL END) as Vitesse_Moyenne,
                     
            -- Calcul Distance Moyenne (Vitesse * Temps)
            AVG(CASE WHEN CAST(REPLACE(vitesse, ',', '.') AS FLOAT) > 0 AND CAST(REPLACE(temps, ',', '.') AS FLOAT) > 0
                     THEN (CAST(REPLACE(vitesse, ',', '.') AS FLOAT) * CAST(REPLACE(temps, ',', '.') AS FLOAT)) ELSE NULL END) as Distance_Moyenne,
                     
            -- Calcul Sans Faute
            SUM(CASE WHEN (vitesse != '-' AND vitesse != '' AND vitesse IS NOT NULL AND vitesse != '0') 
                      AND (penalites IN ('0', '0.00', '0,00', '-', '') OR penalites IS NULL) 
                     THEN 1 ELSE 0 END) as Sans_Faute,
                     
            -- Calcul Éliminés
            SUM(CASE WHEN (vitesse = '-' OR vitesse = '' OR vitesse IS NULL OR vitesse = '0') 
                     THEN 1 ELSE 0 END) as Elimines
                     
        FROM resultats
        WHERE juge IS NOT NULL AND TRIM(juge) != ''
        {sql_grade_filter}
        GROUP BY Juge
        HAVING Total_Parcours > 30 
    """
    
    # On passe les paramètres (si grade sélectionné)
    df_juges = load_data(query_juges, tuple(params_grade))

    if not df_juges.empty:
        # Calculs des pourcentages et arrondis
        df_juges['Taux_Reussite (%)'] = (df_juges['Sans_Faute'] / df_juges['Total_Parcours'] * 100).round(1)
        df_juges['Taux_Elimination (%)'] = (df_juges['Elimines'] / df_juges['Total_Parcours'] * 100).round(1)
        df_juges['Vitesse_Moyenne'] = df_juges['Vitesse_Moyenne'].round(2)
        df_juges['Distance_Moyenne'] = df_juges['Distance_Moyenne'].round(0)

        # --- PARTIE 1 : LE CLASSEMENT COMPLET (SCROLLABLE) ---
        st.header(f"🏆 Palmarès ({choix_grade_juge})")
        
        critere = st.selectbox("Trier le classement par :", [
            "Volume : Plus grand nombre de parcours jugés",
            "Vitesse : Vitesse moyenne la plus haute",
            "Réussite : Plus haut taux de réussite (Sans Faute)",
            "Distance : Parcours les plus longs (Distance moyenne)"
        ])

        if "Volume" in critere:
            col_tri = "Total_Parcours"
            couleur_barre = "#8e44ad"
        elif "Vitesse" in critere:
            col_tri = "Vitesse_Moyenne"
            couleur_barre = "#3498db"
        elif "Réussite" in critere:
            col_tri = "Taux_Reussite (%)"
            couleur_barre = "#2ecc71"
        else:
            col_tri = "Distance_Moyenne"
            couleur_barre = "#e67e22"

        classement_juges = df_juges.sort_values(by=col_tri, ascending=False)
        hauteur_graphique = max(400, len(classement_juges) * 35)

        chart_juges = alt.Chart(classement_juges).mark_bar(color=couleur_barre, cornerRadiusEnd=4).encode(
            x=alt.X(f"{col_tri}:Q", title=critere.split(":")[0], scale=alt.Scale(zero=False)),
            y=alt.Y("Juge:N", sort="-x", title="Nom du Juge", axis=alt.Axis(labelLimit=300)),
            tooltip=["Juge", "Total_Parcours", "Vitesse_Moyenne", "Distance_Moyenne", "Taux_Reussite (%)", "Taux_Elimination (%)"]
        ).properties(height=hauteur_graphique)
        
        text_top = chart_juges.mark_text(align='left', baseline='middle', dx=3).encode(text=f'{col_tri}:Q')
        
        with st.container(height=500, border=True):
            st.altair_chart(chart_juges + text_top, use_container_width=True)

        st.markdown("---")

        # --- PARTIE 2 : RECHERCHE INDIVIDUELLE ---
        st.header("🔍 Profil détaillé d'un juge")
        
        liste_noms_juges = df_juges.sort_values(by="Juge")['Juge'].tolist()
        choix_juge_recherche = st.selectbox("Rechercher un juge spécifique :", ["--- Choisir un juge ---"] + liste_noms_juges)

        if choix_juge_recherche != "--- Choisir un juge ---":
            stats_du_juge = df_juges[df_juges['Juge'] == choix_juge_recherche].iloc[0]

            st.subheader(f"Statistiques pour {choix_juge_recherche} ({choix_grade_juge})")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Parcours Jugés", f"{int(stats_du_juge['Total_Parcours']):,}".replace(',', ' '))
            c2.metric("Vitesse Moyenne", f"{stats_du_juge['Vitesse_Moyenne']} m/s")
            c3.metric("Distance Moyenne", f"{stats_du_juge['Distance_Moyenne']} m")
            c4.metric("Taux d'Élimination", f"{stats_du_juge['Taux_Elimination (%)']}%", 
                      help=f"Taux de réussite (Sans Faute) : {stats_du_juge['Taux_Reussite (%)']}%")

    else:
        st.warning(f"Aucune donnée disponible pour le filtre : {choix_grade_juge}. Essayez un autre grade.")
        
        
# --- PAGE 6 : MODE VERSUS ---
elif menu == "⚔️ Mode Versus":
    st.title("⚔️ L'Arène des Champions")
    st.markdown("Comparez deux binômes et découvrez qui domine l'autre lors des confrontations directes !")

    # --- SÉLECTION DES COMBATTANTS (Par Recherche Texte) ---
    st.subheader("🔍 Sélection des Challengers")
    
    col_sel1, col_sel2 = st.columns(2)
    
    # --- CHALLENGER 1 ---
    with col_sel1:
        st.markdown("🟥 **Challenger ROUGE**")
        search_1 = st.text_input("Nom du chien 1 :", placeholder="Tapez un nom...", key="s1")
        
        id_1 = None
        nom_1 = "Inconnu"
        
        if search_1:
            res_1 = load_data("""
                SELECT DISTINCT id_couple, nom_chien, conducteur, race 
                FROM resultats 
                WHERE UPPER(nom_chien) LIKE ? OR UPPER(conducteur) LIKE ? LIMIT 20
            """, (f'%{search_1.upper()}%', f'%{search_1.upper()}%'))
            
            if not res_1.empty:
                opts_1 = {f"{row['nom_chien']} ({row['conducteur']})": row['id_couple'] for _, row in res_1.iterrows()}
                choix_1 = st.selectbox("Choisir le profil précis :", list(opts_1.keys()), key="box1")
                id_1 = opts_1[choix_1]
                nom_1 = choix_1.split(" (")[0]
            else:
                st.warning("Aucun profil trouvé.")

    # --- CHALLENGER 2 ---
    with col_sel2:
        st.markdown("🟦 **Challenger BLEU**")
        search_2 = st.text_input("Nom du chien 2 :", placeholder="Tapez un nom...", key="s2")
        
        id_2 = None
        nom_2 = "Inconnu"
        
        if search_2:
            res_2 = load_data("""
                SELECT DISTINCT id_couple, nom_chien, conducteur, race 
                FROM resultats 
                WHERE UPPER(nom_chien) LIKE ? OR UPPER(conducteur) LIKE ? LIMIT 20
            """, (f'%{search_2.upper()}%', f'%{search_2.upper()}%'))
            
            if not res_2.empty:
                opts_2 = {f"{row['nom_chien']} ({row['conducteur']})": row['id_couple'] for _, row in res_2.iterrows()}
                choix_2 = st.selectbox("Choisir le profil précis :", list(opts_2.keys()), key="box2")
                id_2 = opts_2[choix_2]
                nom_2 = choix_2.split(" (")[0]
            else:
                st.warning("Aucun profil trouvé.")

    st.markdown("---")

    # SI LES DEUX SONT SÉLECTIONNÉS
    if id_1 and id_2 and id_1 != id_2:
        
        # --- PARTIE A : COMPARATIF GLOBAL ---
        st.header(f"📊 {nom_1} vs {nom_2}")

        def get_global_stats(id_c):
            return load_data("""
                SELECT 
                    COUNT(id) as total,
                    AVG(CASE WHEN CAST(REPLACE(vitesse, ',', '.') AS FLOAT) > 0 THEN CAST(REPLACE(vitesse, ',', '.') AS FLOAT) ELSE NULL END) as vit_moy,
                    SUM(CASE WHEN (penalites IN ('0', '0.00', '0,00', '-', '') OR penalites IS NULL) AND (vitesse NOT IN ('-', '', '0', 'None')) THEN 1 ELSE 0 END) as sans_faute
                FROM resultats 
                WHERE id_couple = ?
            """, (id_c,))

        stats_1 = get_global_stats(id_1).iloc[0]
        stats_2 = get_global_stats(id_2).iloc[0]

        # Calcul sécurisé des stats
        t1 = stats_1['total'] if stats_1['total'] else 0
        t2 = stats_2['total'] if stats_2['total'] else 0
        sf1 = (stats_1['sans_faute'] / t1 * 100) if t1 > 0 else 0
        sf2 = (stats_2['sans_faute'] / t2 * 100) if t2 > 0 else 0
        v1 = round(stats_1['vit_moy'], 2) if pd.notnull(stats_1['vit_moy']) else 0
        v2 = round(stats_2['vit_moy'], 2) if pd.notnull(stats_2['vit_moy']) else 0

        # Affichage Face à Face
        c1, c2, c3 = st.columns([1, 0.2, 1])
        with c1:
            st.metric(f"Vitesse Moyenne ({nom_1})", f"{v1} m/s")
            st.metric("Taux de Réussite", f"{sf1:.1f}%")
        with c2:
            st.markdown("<h2 style='text-align: center; margin-top: 50px;'>VS</h2>", unsafe_allow_html=True)
        with c3:
            st.metric(f"Vitesse Moyenne ({nom_2})", f"{v2} m/s", delta=round(v2 - v1, 2))
            st.metric("Taux de Réussite", f"{sf2:.1f}%", delta=round(sf2 - sf1, 1))

        # --- PARTIE B : L'HISTORIQUE DES DUELS ---
        st.markdown("---")
        st.header("⚔️ Confrontations Directes")

        # Requête (inchangée)
        query_duels = """
            SELECT 
                lc.date_concours, 
                lc.nom_concours,
                r1.nom_epreuve,
                r1.vitesse as vit_1, r1.penalites as pen_1,
                r2.vitesse as vit_2, r2.penalites as pen_2
            FROM resultats r1
            JOIN resultats r2 ON r1.id_concours = r2.id_concours AND r1.nom_epreuve = r2.nom_epreuve
            JOIN liste_concours lc ON r1.id_concours = lc.id_concours
            WHERE r1.id_couple = ? AND r2.id_couple = ?
            ORDER BY SUBSTR(lc.date_concours, 7, 4) DESC, SUBSTR(lc.date_concours, 4, 2) DESC
        """
        
        df_duels = load_data(query_duels, (id_1, id_2))

        if not df_duels.empty:
            # --- 1. CALCUL UNIQUE (STATS + VAINQUEURS) ---
            score_1, score_2 = 0, 0
            vainqueurs_list = []
            
            # Listes pour les stats
            vitesses_1, vitesses_2 = [], []
            penalites_1, penalites_2 = [], []
            eli_1_count, eli_2_count = 0, 0
            
            # Boucle unique de traitement
            for _, row in df_duels.iterrows():
                # Nettoyage
                v_str_1 = str(row['vit_1']).strip()
                v_str_2 = str(row['vit_2']).strip()
                eli_1 = v_str_1 in ['-', '', '0', 'None']
                eli_2 = v_str_2 in ['-', '', '0', 'None']

                # Conversion
                try:
                    pen_1 = float(str(row['pen_1']).replace(',', '.')) if str(row['pen_1']) not in ['-', ''] else 0.0
                    spd_1 = float(str(row['vit_1']).replace(',', '.')) if not eli_1 else 0.0
                    pen_2 = float(str(row['pen_2']).replace(',', '.')) if str(row['pen_2']) not in ['-', ''] else 0.0
                    spd_2 = float(str(row['vit_2']).replace(',', '.')) if not eli_2 else 0.0
                except:
                    pen_1, spd_1 = 999, 0
                    pen_2, spd_2 = 999, 0

                # --- A. LOGIQUE VAINQUEUR ---
                if eli_1 and eli_2:
                    res = 0 
                elif eli_1:
                    res = 2; score_2 += 1
                elif eli_2:
                    res = 1; score_1 += 1
                elif pen_1 < pen_2:
                    res = 1; score_1 += 1
                elif pen_2 < pen_1:
                    res = 2; score_2 += 1
                elif spd_1 > spd_2:
                    res = 1; score_1 += 1
                elif spd_2 > spd_1:
                    res = 2; score_2 += 1
                else:
                    res = 0
                
                vainqueurs_list.append(res)

                # --- B. LOGIQUE STATS ---
                if not eli_1: vitesses_1.append(spd_1)
                else: eli_1_count += 1
                
                if not eli_2: vitesses_2.append(spd_2)
                else: eli_2_count += 1
                
                if str(row['pen_1']) not in ['-', '']: penalites_1.append(pen_1)
                if str(row['pen_2']) not in ['-', '']: penalites_2.append(pen_2)

            # --- C. INSERTION DE LA COLONNE MANQUANTE (Le Fix !) ---
            df_duels['Vainqueur_Code'] = vainqueurs_list

            # --- 2. AFFICHAGE DES STATS (Histogramme) ---
            st.subheader("📊 Statistiques en Confrontation Directe")
            
            # Calcul moyennes
            avg_v1 = sum(vitesses_1)/len(vitesses_1) if vitesses_1 else 0
            avg_v2 = sum(vitesses_2)/len(vitesses_2) if vitesses_2 else 0
            avg_p1 = sum(penalites_1)/len(penalites_1) if penalites_1 else 0
            avg_p2 = sum(penalites_2)/len(penalites_2) if penalites_2 else 0
            pct_e1 = (eli_1_count / len(df_duels) * 100)
            pct_e2 = (eli_2_count / len(df_duels) * 100)

            data_chart = pd.DataFrame({
                'Chien': [nom_1, nom_2, nom_1, nom_2, nom_1, nom_2],
                'Métrique': ['Vitesse (m/s)', 'Vitesse (m/s)', 'Fautes (pts)', 'Fautes (pts)', '% Élimination', '% Élimination'],
                'Valeur': [avg_v1, avg_v2, avg_p1, avg_p2, pct_e1, pct_e2]
            })

            chart = alt.Chart(data_chart).mark_bar().encode(
                x=alt.X('Chien:N', axis=None),
                y=alt.Y('Valeur:Q'),
                color=alt.Color('Chien:N', scale=alt.Scale(range=['#e74c3c', '#3498db']), legend=None),
                column=alt.Column('Métrique:N', header=alt.Header(titleOrient="bottom")),
                tooltip=['Chien', 'Métrique', alt.Tooltip('Valeur', format='.2f')]
            ).properties(width=130, height=200)
            
            st.altair_chart(chart)

            st.markdown("---")

            # --- 3. AFFICHAGE DU SCORE GLOBAL ---
            st.subheader(f"🏆 Score Actuel : {nom_1} [{score_1}] - [{score_2}] {nom_2}")
            if score_1 + score_2 > 0:
                chart_win = pd.DataFrame({'Chien': [nom_1, nom_2], 'Victoires': [score_1, score_2]})
                bar = alt.Chart(chart_win).mark_bar().encode(
                    x=alt.X('Victoires:Q', axis=None), 
                    y=alt.Y('Chien:N', sort='-x', axis=None), 
                    color=alt.Color('Chien', scale=alt.Scale(range=['#e74c3c', '#3498db']), legend=None),
                    tooltip=['Chien', 'Victoires']
                ).properties(height=50)
                st.altair_chart(bar, use_container_width=True)

            # --- 4. AFFICHAGE DÉTAILLÉ (Feuille de Match) ---
            groupes_concours = df_duels.groupby(['date_concours', 'nom_concours'], sort=False)

            for (date, lieu), groupe in groupes_concours:
                with st.container(border=True):
                    st.markdown(f"#### 🏟️ {lieu} <span style='color:gray; font-size:0.8em'>- {date}</span>", unsafe_allow_html=True)
                    
                    # En-têtes symétriques
                    h1, h2, h3 = st.columns([2, 3, 3])
                    h1.markdown("**Épreuve**")
                    h2.markdown(f"<div style='text-align: right; color:#e74c3c; padding-right: 10px;'><b>{nom_1}</b></div>", unsafe_allow_html=True)
                    h3.markdown(f"<div style='text-align: left; color:#3498db; padding-left: 10px;'><b>{nom_2}</b></div>", unsafe_allow_html=True)
                    st.markdown("<hr style='margin: 5px 0'>", unsafe_allow_html=True)

                    for _, row in groupe.iterrows():
                        epreuve = row['nom_epreuve']
                        v_code = row['Vainqueur_Code'] # <--- C'est ici que ça plantait avant !
                        
                        # -- J1 --
                        vit1 = row['vit_1']
                        pen1 = row['pen_1']
                        if vit1 in ['-', '', '0', None]:
                            txt_1 = "⛔ ELIM"
                            style_1 = "color: #95a5a6;"
                        else:
                            txt_1 = f"{pen1} pts ({vit1}s)"
                            if v_code == 1:
                                txt_1 = f"👑 <b>{txt_1}</b>"
                                style_1 = "color: #e74c3c; font-size: 1.1em;"
                            else:
                                style_1 = "color: #333;"

                        # -- J2 --
                        vit2 = row['vit_2']
                        pen2 = row['pen_2']
                        if vit2 in ['-', '', '0', None]:
                            txt_2 = "ELIM ⛔"
                            style_2 = "color: #95a5a6;"
                        else:
                            txt_2 = f"{pen2} pts ({vit2}s)"
                            if v_code == 2:
                                txt_2 = f"<b>{txt_2}</b> 👑"
                                style_2 = "color: #3498db; font-size: 1.1em;"
                            else:
                                style_2 = "color: #333;"

                        # Affichage Ligne
                        c1, c2, c3 = st.columns([2, 3, 3])
                        with c1: st.write(f"{epreuve}")
                        with c2: st.markdown(f"<div style='text-align: right; {style_1} border-right: 1px solid #ddd; padding-right: 15px;'>{txt_1}</div>", unsafe_allow_html=True)
                        with c3: st.markdown(f"<div style='text-align: left; {style_2} padding-left: 15px;'>{txt_2}</div>", unsafe_allow_html=True)

        else:
            st.info("Aucune confrontation directe trouvée.")
        