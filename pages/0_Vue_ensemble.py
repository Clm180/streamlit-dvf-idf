"""Vue d'ensemble : accroche, contexte, décideur, questions BI et KPIs clés."""

import plotly.graph_objects as go
import streamlit as st

from src import utils as u

f = u.get_filters()

# --------------------------------------------------------------------------- #
# 1. Accroche
# --------------------------------------------------------------------------- #
h = u.regional_headline()
st.title("Observatoire des ventes de logements en Île-de-France")

sales_word = "chute" if h["sales_drop"] < 0 else "hausse"
rebound = (
    f"rebondi de {u.fmt_abs_pct(h['sales_rebound'], 0)}"
    if h["sales_rebound"] >= 0
    else f"encore reculé de {u.fmt_abs_pct(h['sales_rebound'], 0)}"
)
price_pos = "sous" if h["price_change"] < 0 else "au-dessus de"
with st.container(border=True):
    st.markdown(
        f"<p style='font-size:1.3rem;line-height:1.5;margin:0'>"
        f"Après une {sales_word} de <b>{u.fmt_abs_pct(h['sales_drop'], 0)}</b> des ventes "
        f"en {h['prev']}, le marché francilien a <b>{rebound}</b> en {h['last']}. "
        f"Pourtant, le prix médian au m² reste <b>{u.fmt_abs_pct(h['price_change'])} "
        f"{price_pos}</b> son niveau de {h['first']}. "
        f"<b>La reprise touche-t-elle tous les territoires ?</b></p>",
        unsafe_allow_html=True,
    )

# --------------------------------------------------------------------------- #
# 2. Contexte, décideur, questions
# --------------------------------------------------------------------------- #
c1, c2 = st.columns(2)
with c1:
    with st.expander("**Contexte : que décrivent les données ?**"):
        st.markdown(
            f"""
- **Source :** *Demandes de valeurs foncières* (DVF, version géolocalisée), publiées par
  la DGFiP et Etalab sur data.gouv.fr : toutes les ventes immobilières enregistrées par les notaires.
- **Périmètre :** les 8 départements d'Île-de-France, ventes de **{h['first']} à {h['last']}**.
- **Unité d'analyse :** la vente d'**un seul logement** (appartement ou maison), vente classique
  ou vente sur plan (VEFA). Les ventes de plusieurs logements sont exclues, car DVF y répète le
  prix total sur chaque ligne, ce qui fausserait le prix au m².
- **Après nettoyage :** **{u.fmt_int(h['n_sales'])} ventes** dans **{u.fmt_int(h['n_communes'])}
  communes** (Paris compté par arrondissement). Détails sur la page *Données*.
"""
        )
with c2:
    with st.expander("**Pour qui, et pour quelles décisions ?**"):
        st.markdown(
            """
**Décideur :** analyste d'un observatoire régional du logement / service habitat de la Région.

**Décisions éclairées :**
- où cibler les aides à l'accession à la propriété ;
- quels territoires surveiller (marché grippé, prix en chute, faible liquidité) ;
- où le marché redémarre, et où il ne redémarre pas.
"""
        )

st.markdown(
    """
**Trois questions guident le tableau de bord**
1. Comment les prix et les volumes ont-ils évolué de 2023 à 2025 ? Le marché a-t-il touché le fond ?
2. Quels départements et communes surperforment ou décrochent par rapport à la médiane régionale ?
3. Quels territoires faut-il surveiller (forte baisse des prix et/ou des ventes, marché peu liquide) ?
"""
)

st.divider()

# --------------------------------------------------------------------------- #
# 3. Vue d'ensemble
# --------------------------------------------------------------------------- #
df = u.get_subset(f)
cur = df[df["annee"] == f.year]
prev = df[df["annee"] == f.prev_year]
k_cur, k_prev = u.kpi_summary(cur), u.kpi_summary(prev)

st.header(f"Vue d'ensemble : {f.scope_label}, {f.year} vs {f.prev_year}")
active = f.active_labels
st.caption("Filtres actifs : " + (", ".join(active) if active else "aucun (tous les logements)"))

if cur.empty:
    st.warning("Aucune vente ne correspond aux filtres. Élargissez la sélection dans le menu latéral.")
    st.stop()

# Écart vs médiane IDF (mêmes filtres, tous départements)
region = u.get_subset(f, region=True)
r_cur = region[region["annee"] == f.year]["prix_m2"].median()
r_prev = region[region["annee"] == f.prev_year]["prix_m2"].median()
gap_cur = u.gap(k_cur["median_m2"], r_cur)
gap_prev = u.gap(k_prev["median_m2"], r_prev)

# Ligne 1 : volumes et prix
m = st.columns(4)
m[0].metric(
    "Nombre de ventes", u.fmt_int(k_cur["sales"]),
    u.delta_pct(u.yoy(k_cur["sales"], k_prev["sales"])), delta_color="normal",
    help=f"Ventes d'un logement enregistrées en {f.year}. Variation vs {f.prev_year}.",
)
m[1].metric(
    "Prix médian au m²", u.fmt_eur(k_cur["median_m2"], per_m2=True),
    u.delta_pct(u.yoy(k_cur["median_m2"], k_prev["median_m2"])), delta_color="normal",
    help="Médiane des prix au m² de chaque vente (prix / surface réelle bâtie).",
)
m[2].metric(
    "Prix médian d'un bien", u.fmt_eur(k_cur["median_price"]),
    u.delta_pct(u.yoy(k_cur["median_price"], k_prev["median_price"])), delta_color="normal",
    help="Médiane de la valeur foncière d'un logement.",
)
if f.all_depts:
    m[3].metric(
        "Écart vs médiane Île-de-France", "—",
        help="Sélectionnez un ou plusieurs départements dans le menu latéral : "
             "avec les 8 départements, l'écart vaut 0 % par définition.",
    )
else:
    m[3].metric(
        "Écart vs médiane Île-de-France", u.fmt_pct(gap_cur),
        u.delta_pp(gap_cur - gap_prev), delta_color="off",
        help=f"Prix médian au m² de la sélection comparé à la médiane Île-de-France "
             f"({u.fmt_eur(r_cur, per_m2=True)}) avec les mêmes filtres. "
             f"Variation = évolution de l'écart depuis {f.prev_year}, en points.",
    )

# Ligne 2 : composition et territoires
m = st.columns(5)
if f.ptype == "Tous":
    m[0].metric(
        "Part des appartements", u.fmt_share(k_cur["share_apart"]),
        u.delta_pp(k_cur["share_apart"] - k_prev["share_apart"]), delta_color="off",
        help="Part des appartements dans les ventes. Variation en points. "
             "Un changement de cette composition fait bouger à lui seul le prix médian.",
    )
else:
    m[0].metric("Part des appartements", "—", help="Choisissez « Tous » en type de bien pour voir la composition.")
if f.new == "Tous":
    m[1].metric(
        "Part du neuf (VEFA)", u.fmt_share(k_cur["share_vefa"]),
        u.delta_pp(k_cur["share_vefa"] - k_prev["share_vefa"]), delta_color="off",
        help="Part des ventes de logements neufs sur plan. Variation en points.",
    )
else:
    m[1].metric("Part du neuf (VEFA)", "—", help="Choisissez « Tous » en neuf / ancien pour voir la composition.")

dt = u.dept_table(f)
best, worst = u.best_worst_dept(dt)
m[2].metric(
    "Meilleur département (prix)", best["dept_name"], u.delta_pct(best["price_change"]),
    delta_color="normal",
    help=f"Plus forte évolution du prix médian au m², {f.prev_year} → {f.year}, parmi les "
         "8 départements, avec les filtres type de bien, neuf / ancien et surface appliqués.",
)
m[3].metric(
    "Département le plus faible (prix)", worst["dept_name"], u.delta_pct(worst["price_change"]),
    delta_color="normal",
    help=f"Plus faible évolution du prix médian au m², {f.prev_year} → {f.year}, mêmes règles.",
)
mac = u.most_active_commune(cur, prev)
m[4].metric(
    "Commune la plus active", mac["name"].replace(" Arrondissement", ""),
    u.delta_pct(mac["sales_change"]), delta_color="normal",
    help=f"{u.fmt_int(mac['sales'])} ventes en {f.year} dans la sélection. "
         f"Variation = évolution du nombre de ventes vs {f.prev_year}.",
)

st.caption(
    "Code couleur : vert = hausse, rouge = baisse. Pour les prix, c'est une lecture de la "
    "performance du marché : une baisse des prix n'est pas forcément une mauvaise nouvelle "
    "pour le décideur, puisqu'elle améliore l'accessibilité pour les ménages."
)

# --------------------------------------------------------------------------- #
# 4. Graphique de preuve : variation de prix par département
# --------------------------------------------------------------------------- #
region_change = u.yoy(r_cur, r_prev)
dt = dt.sort_values("price_change")
colors = [
    u.DEPT_COLORS[n] if c in f.depts else u.GREY
    for n, c in zip(dt["dept_name"], dt["code"])
]
n_down = int((dt["price_change"] < 0).sum())
if worst["price_change"] < 0:
    worst_txt = f"{worst['dept_name']} accuse la plus forte baisse des prix ({u.fmt_pct(worst['price_change'])})"
else:
    worst_txt = f"{worst['dept_name']} affiche la plus faible hausse des prix ({u.fmt_pct(worst['price_change'])})"
title = f"{worst_txt} ; {n_down} départements sur 8 encore en baisse en {f.year}"

fig = go.Figure(
    go.Bar(
        x=dt["price_change"] * 100,
        y=dt["dept_name"],
        orientation="h",
        marker_color=colors,
        text=[u.fmt_pct(v) for v in dt["price_change"]],
        textposition="outside",
        customdata=list(zip(
            [u.fmt_eur(v, per_m2=True) for v in dt["median_m2_prev"]],
            [u.fmt_eur(v, per_m2=True) for v in dt["median_m2"]],
            [u.fmt_int(v) for v in dt["sales"]],
            [u.fmt_pct(v) for v in dt["sales_change"]],
        )),
        hovertemplate=(
            "<b>%{y}</b><br>"
            f"{f.prev_year} : %{{customdata[0]}}<br>{f.year} : %{{customdata[1]}}<br>"
            "Évolution du prix : %{text}<br>"
            f"Ventes {f.year} : %{{customdata[2]}} (%{{customdata[3]}})<extra></extra>"
        ),
    )
)
fig.add_vline(
    x=region_change * 100, line_dash="dash", line_color="#555",
    annotation_text=f"Île-de-France : {u.fmt_pct(region_change)}",
    annotation_position="top",
)
fig.update_layout(
    title=dict(text=title, font=dict(size=17)),
    xaxis_title=f"Évolution du prix médian au m², {f.prev_year} → {f.year} (%)",
    yaxis_title=None,
    height=420,
    showlegend=False,
)
fig.update_xaxes(ticksuffix=" %", zeroline=True, zerolinecolor="#999")
st.plotly_chart(u.plotly_fr(fig), width="stretch")

above = dt[dt["price_change"] > region_change]["dept_name"].tolist()
u.takeaway(
    f"en Île-de-France, le prix médian au m² a évolué de {u.fmt_pct(region_change)} entre "
    f"{f.prev_year} et {f.year} (filtres actuels). {best['dept_name']} est en tête "
    f"({u.fmt_pct(best['price_change'])}), {worst['dept_name']} ferme la marche "
    f"({u.fmt_pct(worst['price_change'])}). Départements au-dessus de la tendance régionale : "
    f"{', '.join(above) if above else 'aucun'}. Les barres grises sont hors de votre sélection."
)

# --------------------------------------------------------------------------- #
# 5. Navigation
# --------------------------------------------------------------------------- #
others = [p for p in u.existing_pages() if p[1] != "pages/0_Vue_ensemble.py"]
if others:
    st.divider()
    st.subheader("Aller plus loin", anchor=False)
    cols = st.columns(len(others))
    for col, (_, path, title, icon, blurb) in zip(cols, others):
        col.page_link(path, label=f"{title} : {blurb}", icon=icon)
