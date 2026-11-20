"""Données : nettoyage, contrôles qualité, tableau interactif, export, hypothèses et limites."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import utils as u

f = u.get_filters()
SLATE, SLATE_LIGHT = u.SLATE, u.SLATE_LIGHT

st.title("Données : d'où viennent les chiffres ?")
st.markdown(
    "Source : **Demandes de valeurs foncières (DVF) géolocalisées**, DGFiP / Etalab, "
    "[files.data.gouv.fr/geo-dvf](https://files.data.gouv.fr/geo-dvf/latest/csv/), fichiers annuels "
    f"par département, {u.available_years()[0]}–{u.available_years()[-1]}, 8 départements d'Île-de-France."
)


@st.cache_data(show_spinner=False)
def quality_report() -> pd.DataFrame:
    return pd.read_csv(u.ROOT / "data" / "quality_report.csv")


# --------------------------------------------------------------------------- #
# 1. Funnel du nettoyage
# --------------------------------------------------------------------------- #
qr = quality_report()
qr["removed"] = (-qr["nb"].diff()).fillna(0).astype(int)
raw_n, final_n = int(qr["nb"].iloc[0]), int(qr["nb"].iloc[-1])
df_all = u.load_data()

st.subheader(
    f"Des {u.fmt_int(raw_n)} lignes brutes aux {u.fmt_int(final_n)} ventes analysées "
    f"({u.fmt_int(df_all['code_commune'].nunique())} communes)",
    anchor=False,
)
labels = [s.split(". ", 1)[1] if ". " in s else s for s in qr["etape"]]
fig = go.Figure(go.Funnel(
    y=labels, x=qr["nb"], marker_color=[SLATE if unit == "ventes" else SLATE_LIGHT for unit in qr["unite"]],
    text=[f"{u.fmt_int(n)} {unit}" for n, unit in zip(qr["nb"], qr["unite"])], textinfo="text",
    hovertemplate="%{y}<br>%{text}<extra></extra>",
))
fig.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(u.plotly_fr(fig), width="stretch")
st.caption("Bleu clair : lignes du fichier DVF ; bleu ardoise : ventes (1 ligne = 1 vente d'un logement) "
           "à partir de l'étape 4.")

r = qr.set_index(qr.index + 1)["removed"]
STEPS = [
    ("Chargement", f"Les fichiers DVF des 8 départements et des {len(u.available_years())} années "
                   f"sont empilés : {u.fmt_int(raw_n)} lignes."),
    ("Doublons exacts", f"{u.fmt_int(r[2])} lignes publiées deux fois à l'identique sont supprimées."),
    ("Ventes uniquement", f"Seules les ventes classiques et les VEFA (ventes sur plan) sont gardées ; "
                          f"échanges, adjudications, expropriations et ventes de terrains sont exclus "
                          f"({u.fmt_int(r[3])} lignes)."),
    ("1 seul logement par mutation", "Une *mutation* (un acte de vente) s'étale sur plusieurs lignes : "
     "logement, cave, parking, dépendances… et **DVF répète le prix total de la mutation sur chaque ligne**. "
     "Calculer un prix au m² ligne par ligne, ou sur une mutation de plusieurs logements, donnerait un "
     "résultat faux. On ne garde donc que les mutations contenant **exactement un logement** (appartement "
     "ou maison) **et aucun local commercial**, puis la ligne du logement. Les ventes d'immeubles ou de "
     "lots groupés sortent du périmètre. La forte baisse à cette étape vient surtout du changement "
     "d'unité : on passe de lignes à ventes."),
    ("Prix et surface renseignés", f"{u.fmt_int(r[5])} ventes sans valeur foncière ou sans surface bâtie "
                                   "sont retirées."),
    ("Seuils minimaux", f"Surface ≥ 9 m² (seuil légal d'un logement décent) et prix ≥ 15 000 € (prix "
                        f"symboliques, cessions familiales) : {u.fmt_int(r[6])} ventes retirées."),
    ("Valeurs extrêmes", f"Pour chaque année × département × type de bien, les ventes dont le prix au m² "
                         f"est sous le 1er centile ou au-dessus du 99e sont retirées ({u.fmt_int(r[7])} "
                         "ventes) : erreurs de saisie, ventes atypiques."),
]
with st.expander("Le détail de chaque étape", expanded=False):
    for i, (name, txt) in enumerate(STEPS, start=1):
        st.markdown(f"**{i}. {name}.** {txt}")
u.takeaway(
    f"le nettoyage ne garde que des ventes comparables entre elles : un logement, un prix, une surface. "
    f"Sur les ventes d'un seul logement (étape 4), {u.fmt_share(final_n / qr['nb'].iloc[3])} passent "
    "tous les contrôles suivants."
)

st.divider()

# --------------------------------------------------------------------------- #
# 2. Contrôles qualité
# --------------------------------------------------------------------------- #
st.subheader("Contrôles qualité sur le fichier propre", anchor=False)
m = st.columns(4)
m[0].metric("Ventes", u.fmt_int(len(df_all)))
m[1].metric("Identifiants de mutation uniques", u.fmt_share(df_all["id_mutation"].nunique() / len(df_all)),
            help="Une ligne = une mutation : aucun prix n'est compté deux fois.")
no_gps = df_all["latitude"].isna() | df_all["longitude"].isna()
m[2].metric("Ventes sans coordonnées GPS", u.fmt_int(no_gps.sum()),
            help="Exclues de la carte uniquement : "
                 + ", ".join(f"{y} : {u.fmt_int(n)}" for y, n in df_all[no_gps].groupby("annee").size().items()))
m[3].metric("Prix au m² médian (toutes années)", u.fmt_eur(df_all["prix_m2"].median(), True))

c1, c2 = st.columns(2)
COLS_FR = {
    "id_mutation": "Identifiant", "date_mutation": "Date", "nature_mutation": "Nature",
    "valeur_fonciere": "Prix", "code_postal": "Code postal", "code_commune": "Code commune",
    "nom_commune": "Commune", "code_departement": "Département", "type_local": "Type",
    "surface_reelle_bati": "Surface bâtie", "nombre_pieces_principales": "Pièces",
    "surface_terrain": "Surface terrain", "longitude": "Longitude", "latitude": "Latitude",
    "prix_m2": "Prix au m²",
}
miss = df_all[list(COLS_FR)].isna().mean().rename(index=COLS_FR).sort_values()
worst_col = miss.idxmax()
with c1:
    st.markdown(f"**Valeurs manquantes : seule « {worst_col} » est souvent vide ({u.fmt_share(miss.max(), 0)})**")
    fig = go.Figure(go.Bar(
        x=miss * 100, y=miss.index, orientation="h", marker_color=SLATE,
        text=[u.fmt_share(v) for v in miss], textposition="outside",
        hovertemplate="%{y} : %{text}<extra></extra>",
    ))
    fig.update_layout(height=430, xaxis_title="% de valeurs manquantes", margin=dict(l=10, r=40, t=10, b=10))
    fig.update_xaxes(ticksuffix=" %")
    st.plotly_chart(u.plotly_fr(fig), width="stretch")
    terr_apart = df_all.loc[df_all["type_local"] == "Appartement", "surface_terrain"].isna().mean()
    st.caption(f"La surface de terrain est vide pour {u.fmt_share(terr_apart, 0)} des appartements : "
               "c'est attendu, et cette colonne n'entre dans aucun indicateur.")

sub = u.get_subset(f, years=(f.year,))
with c2:
    if len(sub):
        st.markdown(f"**Prix au m² après nettoyage ({f.scope_label}, {f.year}, filtres actuels)**")
        fig = go.Figure()
        for t, color in u.TYPE_COLORS.items():
            v = sub.loc[sub["type_local"] == t, "prix_m2"]
            if len(v):
                fig.add_histogram(x=v, name=u.PROPERTY_LABELS[t], marker_color=color, opacity=0.65, nbinsx=60)
        fig.update_layout(barmode="overlay", height=430, xaxis_title="Prix au m² (€)", yaxis_title="Ventes",
                          legend=dict(orientation="h", y=1.08), margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(u.plotly_fr(fig), width="stretch")
        st.caption("Les queues de distribution sont coupées par la règle P1 / P99 (étape 7), appliquée par "
                   "année × département × type ; bornes effectives dans le tableau ci-dessous.")

bounds = (
    df_all[df_all["annee"] == f.year].groupby(["dept_name", "type_local"])["prix_m2"]
    .agg(["min", "max", "size"]).reset_index()
)
bounds = bounds[bounds["dept_name"].isin([u.DEPT_NAMES[d] for d in f.depts])]
bounds.columns = ["Département", "Type", "Borne basse (≈ P1)", "Borne haute (≈ P99)", "Ventes"]
bounds["Type"] = bounds["Type"].map(u.PROPERTY_LABELS)
with st.expander(f"Bornes P1 / P99 retenues en {f.year} par département et type de bien"):
    st.dataframe(
        bounds.style.format({"Borne basse (≈ P1)": lambda v: u.fmt_eur(v, True),
                             "Borne haute (≈ P99)": lambda v: u.fmt_eur(v, True), "Ventes": u.fmt_int}),
        hide_index=True, width="stretch",
    )
    st.caption("Plus petit et plus grand prix au m² conservés dans chaque groupe : ils approchent les "
               "centiles 1 et 99 calculés sur les données brutes par src/prepare_data.py.")

st.divider()

# --------------------------------------------------------------------------- #
# 3. Tableau interactif et export
# --------------------------------------------------------------------------- #
st.subheader("Explorer les ventes", anchor=False)
c1, c2 = st.columns([1, 2])
period = c1.radio("Période", [f"{f.year}", f"{f.prev_year} et {f.year}", "Toutes les années"], horizontal=True)
years = {f"{f.year}": (f.year,), f"{f.prev_year} et {f.year}": (f.prev_year, f.year)}.get(period)
search = c2.text_input("Rechercher une commune", placeholder="ex. Montreuil, Paris 11e…")

view = u.get_subset(f, years=years)
if search:
    view = view[view["nom_commune"].str.contains(search.strip(), case=False, regex=False)]
table = pd.DataFrame({
    "Date": view["date_mutation"],
    "Commune": view["nom_commune"].str.replace(" Arrondissement", "", regex=False),
    "Code postal": view["code_postal"],
    "Département": view["dept_name"],
    "Zone": view["zone"],
    "Type": view["type_local"],
    "Neuf (VEFA)": view["vefa"],
    "Surface (m²)": view["surface_reelle_bati"],
    "Pièces": view["nombre_pieces_principales"],
    "Prix (€)": view["valeur_fonciere"],
    "Prix au m² (€)": view["prix_m2"],
})
st.caption(f"{u.fmt_int(len(table))} ventes · filtres du menu latéral appliqués · cliquez sur un en-tête "
           "pour trier, survolez le tableau pour la recherche et le plein écran.")
st.dataframe(
    table, hide_index=True, width="stretch", height=420,
    column_config={
        "Date": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Surface (m²)": st.column_config.NumberColumn(format="localized"),
        "Pièces": st.column_config.NumberColumn(format="%d"),
        "Prix (€)": st.column_config.NumberColumn(format="localized"),
        "Prix au m² (€)": st.column_config.NumberColumn(format="localized"),
    },
)

ct = u.commune_table(f.year, f.depts, f.ptype, f.new, f.surface)
agg = pd.DataFrame({
    "code_commune": ct["code_commune"], "commune": ct["nom_commune"], "departement": ct["dept_name"],
    "zone": ct["zone"], f"ventes_{f.prev_year}": ct["sales_prev"], f"ventes_{f.year}": ct["sales"],
    "evolution_ventes": ct["sales_change"].round(4),
    f"prix_median_m2_{f.prev_year}": ct["median_m2_prev"], f"prix_median_m2_{f.year}": ct["median_m2"],
    "evolution_prix": ct["price_change"].round(4), f"prix_median_bien_{f.year}": ct["median_price"],
    f"fiable_{u.MIN_SALES}_ventes": (ct["sales"] >= u.MIN_SALES) & (ct["sales_prev"] >= u.MIN_SALES),
    "latitude": ct["latitude"], "longitude": ct["longitude"],
})


def to_csv(d: pd.DataFrame) -> bytes:
    """CSV lisible par Excel en français : séparateur « ; », virgule décimale, UTF-8 avec BOM."""
    return d.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


c1, c2 = st.columns(2)
suffix = period.replace(" et ", "_").replace("Toutes les années", "2023_2025").replace(" ", "")
c1.download_button(
    f"Télécharger les {u.fmt_int(len(table))} ventes (CSV)", to_csv(table),
    file_name=f"ventes_dvf_idf_{suffix}.csv", mime="text/csv", width="stretch",
)
c2.download_button(
    f"Télécharger les agrégats par commune {f.prev_year}–{f.year} (CSV)", to_csv(agg),
    file_name=f"communes_dvf_idf_{f.year}.csv", mime="text/csv", width="stretch",
)
st.caption("Fichiers au format CSV français (séparateur « ; », virgule décimale) : ouverture directe dans Excel.")

st.divider()

# --------------------------------------------------------------------------- #
# 4. Hypothèses et limites
# --------------------------------------------------------------------------- #
st.subheader("Hypothèses et limites", anchor=False)
share_p = r[7] / qr["nb"].iloc[5]
st.markdown(
    f"""
**Ce que les données couvrent**
- DVF recense les ventes enregistrées par les notaires. Le fichier ne couvre ni l'Alsace-Moselle ni
  Mayotte (sans effet ici) et **ne dit rien des acheteurs, des vendeurs, de l'état du bien, du DPE, ni
  du financement** (taux, apport).
- Les ventes de **plusieurs logements** (immeubles, lots groupés) sont exclues pour garder un prix au
  m² juste : le tableau de bord décrit le marché du logement à l'unité.

**Hypothèses de l'analyse**
- La surface utilisée est la **surface réelle bâtie** déclarée ; la surface Carrez, très majoritairement
  vide dans DVF, n'est pas exploitable.
- Les seuils **P1 / P99** (soit {u.fmt_share(share_p)} des ventes retirées à l'étape 7), **9 m²** et
  **15 000 €** sont des choix de l'analyste ; d'autres seuils déplaceraient légèrement les médianes.
- Les **médianes sont sensibles à la composition** des ventes (part d'appartements, de petites surfaces,
  de Paris) : un prix médian qui bouge ne veut pas forcément dire que les prix d'un même bien bougent.
  D'où le filtre type de bien et les découpages de la page Évolution.

**Règles d'affichage**
- Communes à moins de **{u.MIN_SALES} ventes par an** : masquées sur la carte et absentes des classements
  et du score ; points mensuels à moins de **{u.MIN_POINT_SALES} ventes** masqués.
- **{u.fmt_int(no_gps.sum())} ventes** sans coordonnées GPS : exclues de la carte uniquement.
- Le **score « territoires à surveiller »** repose sur des poids choisis (méthode détaillée dans le
  Zoom commune) : il hiérarchise des communes à examiner, il ne constitue pas un diagnostic.
"""
)
