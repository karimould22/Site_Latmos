import streamlit as st
import xarray as xr
import pandas as pd
import plotly.express as px
import base64
import os
import tempfile

# Configuration de la page
st.set_page_config(page_title="Dashboard Meteo", layout="wide")

# Noms des fichiers image
FICHIER_FOND = "fond.jpg"
FICHIER_LOGO = "qualair.png"
FICHIER = "latmos_blanc.png"

# --- FONCTION POUR L'IMAGE DE FOND ET LE STYLE CSS ---
def appliquer_style_et_fond(image_fond_path):
    try:
        with open(image_fond_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url(data:image/png;base64,{encoded_string});
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            .block-container p, .block-container h1, .block-container h2, .block-container h3, .block-container h4 {{
                color: white !important;
            }}
            .block-container h1, .block-container h2, .block-container h3, .block-container h4 {{
                text-shadow: 1px 1px 3px black;
            }}
            .stSidebar label, .stSidebar p, .stSidebar h1, .stSidebar h2, .stSidebar h3, .stSidebar span {{
                color: black !important;
                text-shadow: none !important;
                font-weight: 600; 
            }}
            div[role="listbox"] ul li {{
                color: black !important;
                text-shadow: none;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
    except FileNotFoundError:
        pass

# --- FONCTION POUR LE PETIT LOGO EN HAUT A DROITE ---
def ajouter_petit_logo_top_right(logo_path):
    if os.path.exists(logo_path):
        try:
            with open(logo_path, "rb") as f:
                data = f.read()
                encoded_image = base64.b64encode(data).decode()
            
            st.markdown(
                f"""
                <div style="position: absolute; top: 10px; right: 20px; z-index: 1000;">
                    <img src="data:image/png;base64,{encoded_image}" width="80px" style="border-radius: 5px;">
                </div>
                """,
                unsafe_allow_html=True
            )
        except Exception as e:
            pass 

# Appliquer le fond et le petit logo
appliquer_style_et_fond(FICHIER_FOND)
ajouter_petit_logo_top_right(FICHIER)

# --- TITRE PRINCIPAL ---
st.title("Visualisation des donnees Meteo")

# --- ANCIEN LOGO DANS LA SIDEBAR ---
try:
    st.sidebar.image(FICHIER_LOGO, use_container_width=True)
except FileNotFoundError:
    pass

st.sidebar.header("Importation")

# --- BOUTON DE CHARGEMENT DE FICHIERS ---
fichiers_upload = st.sidebar.file_uploader(
    "Chargez vos fichiers NetCDF (.nc)", 
    type=["nc"], 
    accept_multiple_files=True
)

# --- TRADUCTEUR D'UNITES ---
TRADUCTION_UNITES = {
    "degree_celsius": "°C",
    "degrees_celsius": "°C",
    "celsius": "°C",
    "percent": "%",
    "percentage": "%",
    "m s-1": "m/s",
    "meters per second": "m/s",
    "meter per second": "m/s",
    "degrees": "°",
    "degree": "°",
    "deg": "°",
    "hpa": "hPa",
    "hectopascal": "hPa"
}

# --- CHARGEMENT DYNAMIQUE DES DONNEES ---
@st.cache_data
def charger_donnees(fichiers):
    if not fichiers:
        return None, None, None, None, None
        
    temp_dir = tempfile.mkdtemp()
    chemins = []
    
    for f in fichiers:
        chemin_temp = os.path.join(temp_dir, f.name)
        with open(chemin_temp, "wb") as f_out:
            f_out.write(f.read())
        chemins.append(chemin_temp)
        
    try:
        if len(chemins) == 1:
            dataset = xr.open_dataset(chemins[0])
        else:
            dataset = xr.open_mfdataset(chemins, combine='by_coords')
            
        unites = {}
        descriptions = {}
        
        for var in dataset.variables:
            unite_brute = str(dataset[var].attrs.get('units', '')).strip()
            unite_propre = TRADUCTION_UNITES.get(unite_brute.lower(), unite_brute)
            
            unites[var] = unite_propre
            descriptions[var] = dataset[var].attrs.get('long_name', 'Pas de description')
            
        nom_station = dataset.attrs.get('station_name', dataset.attrs.get('station', ''))
        nom_lieu = dataset.attrs.get('location', dataset.attrs.get('site', ''))
        
        if not nom_station or not nom_lieu:
            nom_premier_fichier = fichiers[0].name.replace('.nc', '')
            parties_nom = nom_premier_fichier.split('_')
            
            if not nom_station and len(parties_nom) > 1:
                nom_station = parties_nom[1] 
            if not nom_lieu and len(parties_nom) > 2:
                nom_lieu = parties_nom[2]    

        if not nom_station: nom_station = "Inconnue"
        if not nom_lieu: nom_lieu = "Inconnu"

        df = dataset.to_dataframe().reset_index()
        
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df = df.set_index('time')
        elif 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.set_index('Date')
            
        colonnes_numeriques = df.select_dtypes(include=['float32', 'float64', 'int32', 'int64']).columns
        return df[colonnes_numeriques], unites, descriptions, nom_station, nom_lieu
        
    except Exception as e:
        st.error(f"Erreur lors du chargement des fichiers : {e}")
        return None, None, None, None, None

df, dict_unites, dict_descriptions, station_dynamique, lieu_dynamique = charger_donnees(fichiers_upload)

# --- SI DES FICHIERS SONT CHARGES ---
if df is not None and not df.empty:
    
    st.sidebar.markdown("---")
    st.sidebar.header("Parametres")
    
    variable_choisie = st.sidebar.selectbox("1. Choisissez la variable :", df.columns)
    
    date_min = df.index.min().date()
    date_max = df.index.max().date()
    
    dates_selectionnees = st.sidebar.date_input(
        "2. Selectionnez la periode :",
        [date_min, date_max],
        min_value=date_min,
        max_value=date_max
    )
    
    frequence = st.sidebar.selectbox(
        "3. Lisser les donnees (Moyenne) :",
        ["Donnees brutes", "Moyenne par Jour", "Moyenne par Semaine", "Moyenne par Mois", "Moyenne par An"]
    )
    
    dict_frequence = {
        "Moyenne par Jour": "D",
        "Moyenne par Semaine": "W",
        "Moyenne par Mois": "MS",
        "Moyenne par An": "YS"
    }

    st.sidebar.markdown("---")
    st.sidebar.subheader("Informations")
    st.sidebar.info(
        f"Station : {station_dynamique}\n\n"
        f"Fichiers charges : {len(fichiers_upload)}\n\n"
        f"Dates disponibles : {df.index.min().strftime('%d/%m/%Y')} au {df.index.max().strftime('%d/%m/%Y')}"
    )
    
    with st.sidebar.expander("Aide & Description"):
        for var in df.columns:
            desc = dict_descriptions.get(var, "Inconnu")
            unite = dict_unites.get(var, "")
            texte_unite = f" ({unite})" if unite else ""
            st.write(f"- **{var}** : {desc}{texte_unite}")

    if len(dates_selectionnees) == 2:
        date_debut, date_fin = dates_selectionnees
        df_filtre = df.loc[str(date_debut):str(date_fin)]
        
        if frequence != "Donnees brutes":
            df_final = df_filtre[variable_choisie].resample(dict_frequence[frequence]).mean()
        else:
            df_final = df_filtre[variable_choisie]

        st.sidebar.markdown("---")
        csv = df_final.to_csv().encode('utf-8')
        st.sidebar.download_button(
            label="Telecharger les donnees (CSV)",
            data=csv,
            file_name=f"donnees_{variable_choisie}.csv",
            mime='text/csv',
        )

        st.markdown(f"<h3 style='text-align: center; color: white;'>Serie temporelle : {variable_choisie}</h3>", unsafe_allow_html=True)
        
        unite = dict_unites.get(variable_choisie, "")
        label_axe_y = f"{variable_choisie} [{unite}]" if unite else variable_choisie

        fig = px.line(
            x=df_final.index, 
            y=df_final.values, 
            labels={'x': 'Date', 'y': label_axe_y},
            markers=True 
        )
        
        if frequence == "Moyenne par Mois":
            fig.update_xaxes(tickformat="%b %Y", dtick="M1", title_text="")
        elif frequence == "Moyenne par An":
            fig.update_xaxes(tickformat="%Y", dtick="M12", title_text="")
        else:
            fig.update_xaxes(tickformat="%d %b %Y", title_text="")
        
        fig.update_traces(line_color='#1f77b4') 
        
        fig.update_layout(
            paper_bgcolor="white", 
            plot_bgcolor="white",
            font=dict(color="black", size=14),
            hovermode="x unified",
            xaxis=dict(
                title_font=dict(size=16, color="black"),
                tickfont=dict(size=14, color="black"),
                showgrid=True,
                gridcolor='lightgray'
            ),
            yaxis=dict(
                title_font=dict(size=16, color="black"),
                tickfont=dict(size=14, color="black"),
                showgrid=True,
                gridcolor='lightgray'
            )
        )

        st.plotly_chart(fig, use_container_width=True)
        
        # --- TITRE STATISTIQUES ---
        st.markdown("---")
        st.markdown(f"""
            <p style='color: white; font-size: 24px; font-weight: bold; text-shadow: 1px 1px 3px black; margin-bottom: 0px;'>
            Statistiques de '{variable_choisie}' sur cette periode :
            </p>
            """, unsafe_allow_html=True)
        
        # NETTOYAGE DU TABLEAU DES STATISTIQUES
        stats = df_final.describe()
        stats_propres = stats.drop(['25%', '50%', '75%']) 
        st.dataframe(stats_propres.to_frame(name="Valeurs").T, use_container_width=True)
        
        # --- SYNTHESES ANNUELLES ET SAISONNIERES ---
        st.markdown(f"""
            <p style='color: white; font-size: 24px; font-weight: bold; text-shadow: 1px 1px 3px black; margin-top: 30px;'>
            Syntheses annuelles et saisonnieres :
            </p>
            """, unsafe_allow_html=True)
            
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("<p style='color: white; font-size: 20px; font-weight: bold; text-shadow: 1px 1px 3px black;'>Par Annee</p>", unsafe_allow_html=True)
            df_annee = df_filtre[variable_choisie].groupby(df_filtre.index.year).agg(['mean', 'min', 'max'])
            df_annee.index.name = "Annee"
            df_annee.columns = ["Moyenne", "Min", "Max"]
            st.dataframe(df_annee, use_container_width=True)
            
        with col2:
            st.markdown("<p style='color: white; font-size: 20px; font-weight: bold; text-shadow: 1px 1px 3px black;'>Par Saison et par Annee</p>", unsafe_allow_html=True)
            
            # Creation d'un DataFrame temporaire pour manipuler facilement les saisons et annees
            df_pour_saison = pd.DataFrame({
                'Valeur': df_filtre[variable_choisie],
                'Annee': df_filtre.index.year,
                'Saison': df_filtre.index.month.map({
                    1: 'Hiver', 2: 'Hiver', 3: 'Printemps',
                    4: 'Printemps', 5: 'Printemps', 6: 'Ete',
                    7: 'Ete', 8: 'Ete', 9: 'Automne',
                    10: 'Automne', 11: 'Automne', 12: 'Hiver'
                })
            })
            
            # Forcer l'ordre des saisons chronologiquement
            df_pour_saison['Saison'] = pd.Categorical(
                df_pour_saison['Saison'], 
                categories=["Hiver", "Printemps", "Ete", "Automne"], 
                ordered=True
            )
            
            # Grouper par Annee puis par Saison
            df_saison = df_pour_saison.groupby(['Annee', 'Saison'])['Valeur'].agg(['mean', 'min', 'max']).dropna()
            df_saison.columns = ["Moyenne", "Min", "Max"]
            st.dataframe(df_saison, use_container_width=True)
        
    else:
        st.warning("Veuillez selectionner une date de debut et une date de fin.")

else:
    st.info("Veuillez glisser-deposer un ou plusieurs fichiers NetCDF dans le menu de gauche pour commencer l'analyse.")