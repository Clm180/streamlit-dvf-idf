"""Aide à la décision / Recommandations : 3 constats, 2 recommandations, 1 limite, preuves calculées."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src import utils as u

f_user = u.get_filters()
# Les conclusions portent sur tout le marché francilien (filtres d'exploration neutralisés),
# seule l'année de référence N du menu latéral est reprise.
FULL = (u.SURFACE_MIN, u.SURFACE_MAX)
N, N1 = f_user.year, f_user.prev_year
years = u.available_years()
Y0, YP, YL = years[0], years[-2], years[-1]
SLATE, SLATE_LIGHT = u.SLATE, u.SLATE_LIGHT

st.title("Decision Support / Recommendations")
st.caption("Aide à la décision : constats, recommandations et limite, tous appuyés par les données du tableau de bord.")
st.caption(
    f"Périmètre : toute l'Île-de-France, tous logements · comparaison {N} vs {N1} (année N du menu "
    "latéral) · les autres filtres sont volontairement ignorés pour que les conclusions ne dépendent "
    "pas de l'exploration en cours."
)
st.markdown(
    "Chaque point distingue le **constat**, mesuré dans les données, de son **interprétation**, qui reste "
    "une hypothèse à confirmer. Tous les chiffres sont recalculés à partir des données."
)


def phrase(x: float, plural: bool = False) -> str:
    """« progresse de 1,3 % » / « recule de 0,7 % » / « stagne (+0,2 %) »."""
    verb = u.trend_verb(x, plural)
    return f"{verb} ({u.fmt_pct(x)})" if verb.startswith("stagn") else f"{verb} de {u.fmt_abs_pct(x)}"


# --------------------------------------------------------------------------- #
# Calculs
# --------------------------------------------------------------------------- #
ann = u.annual_stats(None, "Tous", "Tous", FULL).set_index("annee")
ts_m = u.time_series(None, None, "Tous", "Tous", FULL, "M")
roll = ts_m.dropna(subset=["roll_median"])
p_trough = roll.loc[roll["roll_median"].idxmin()]
v_trough = ts_m.dropna(subset=["roll_n"]).loc[ts_m["roll_n"].idxmin()]

zone = u.annual_stats(None, "Tous", "Tous", FULL, by=("zone",)).set_index(["zone", "annee"])
typ = u.annual_stats(None, "Tous", "Tous", FULL, by=("type_local",)).set_index(["type_local", "annee"])


def chg(tab: pd.DataFrame, key: str, col: str = "median") -> float:
    return u.yoy(tab.loc[(key, N), col], tab.loc[(key, N1), col])


z_chg = {z: chg(zone, z) for z in u.ZONE_COLORS}
t_chg = {t: chg(typ, t) for t in u.TYPE_COLORS}
idf_chg = u.yoy(ann.loc[N, "median"], ann.loc[N1, "median"])

sc = u.scorecard(N, "Tous", "Tous", FULL)
decile = sc.head(max(1, len(sc) // 10))
gc_dec = (decile["zone"] == "Grande couronne").mean()
rb = u.score_robustness(N, "Tous", "Tous", FULL)
verdict = u.overrep_verdict(rb)
core = sc[sc["code_commune"].isin(rb["common"])]  # communes du top 10 % dans les deux versions du score

cur = u.filter_data((N,), None, "Tous", "Tous", FULL)
prev = u.filter_data((N1,), None, "Tous", "Tous", FULL)
sh_cur = (cur["type_local"] == "Appartement").mean()
house_gc = (cur.loc[cur["type_local"] == "Maison", "zone"] == "Grande couronne").mean()
sh_prev = (prev["type_local"] == "Appartement").mean()

# --------------------------------------------------------------------------- #
# Constats
# --------------------------------------------------------------------------- #
st.header("Trois constats clés")

# Constat 1 ---------------------------------------------------------------- #
s_drop = u.yoy(ann.loc[YP, "n"], ann.loc[Y0, "n"])
s_reb = u.yoy(ann.loc[YL, "n"], ann.loc[YP, "n"])
p_drop = u.yoy(ann.loc[YP, "median"], ann.loc[Y0, "median"])
p_reb = u.yoy(ann.loc[YL, "median"], ann.loc[YP, "median"])
p_total = u.yoy(ann.loc[YL, "median"], ann.loc[Y0, "median"])

# Le récit dépend du signe des évolutions : volumes repartis sans les prix (cas attendu), ou non
volumes_back = s_reb > 0.02
prices_lag = p_reb < s_reb / 3
trough_recent = p_trough["period"].year == YL
if volumes_back and prices_lag:
    title1 = f"1. Les volumes ont rebondi en {YL} ({u.fmt_pct(s_reb, 0)}), pas les prix ({u.fmt_pct(p_reb)})"
    interp1 = (
        "Le marché a retrouvé de la <b>liquidité</b> avant de retrouver du <b>pouvoir de prix</b> : "
        "les transactions repartent à des prix ajustés. Hypothèse compatible avec une détente des "
        "conditions de crédit, que DVF ne mesure pas."
        + (f" Le point bas des prix datant de {YL}, rien ne garantit encore qu'il soit derrière nous."
           if trough_recent else "")
    )
elif volumes_back:
    title1 = f"1. Volumes ({u.fmt_pct(s_reb, 0)}) et prix ({u.fmt_pct(p_reb)}) repartent ensemble en {YL}"
    interp1 = ("La reprise touche à la fois les volumes et les prix : signe possible d'une demande qui "
               "revient plus vite que l'offre (hypothèse, l'offre n'étant pas observée dans DVF).")
else:
    title1 = f"1. Les volumes ne repartent pas en {YL} ({u.fmt_pct(s_reb, 0)}) et les prix {phrase(p_reb)}"
    interp1 = ("Le marché reste grippé : peu de transactions, ce qui fragilise aussi la mesure des prix. "
               "Hypothèse : attentisme des acheteurs et des vendeurs, à confirmer par des données hors DVF.")

with st.container(border=True):
    st.subheader(title1, anchor=False)
    c1, c2 = st.columns([3, 2])
    with c1:
        u.evidence_box("constat", (
            f"Les ventes {phrase(s_drop, True).replace('reculent', 'chutent')} en {YP}, puis "
            f"{phrase(s_reb, True)} en {YL} : avec {u.fmt_int(ann.loc[YL, 'n'])} ventes, le marché est "
            f"{u.position_vs(u.yoy(ann.loc[YL, 'n'], ann.loc[Y0, 'n']), 'son niveau de ' + str(Y0))}. "
            f"Le prix médian au m², lui, {phrase(p_drop)} en {YP} puis {phrase(p_reb)} en {YL} : il reste "
            f"<b>{u.fmt_abs_pct(p_total)} {'sous' if p_total < 0 else 'au-dessus de'}</b> son niveau de {Y0}. "
            f"Point bas des ventes (3 mois glissants) : {u.window_label(v_trough['period'])} ; point bas des "
            f"prix : <b>{u.window_label(p_trough['period'])}</b> ({u.fmt_eur(p_trough['roll_median'], True)})."
        ))
        u.evidence_box("interpretation", interp1)
    with c2:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_bar(x=[str(y) for y in years], y=ann.loc[years, "n"], name="Ventes", marker_color=SLATE_LIGHT,
                    text=[u.fmt_int(v) for v in ann.loc[years, "n"]], textposition="inside",
                    hovertemplate="%{x} : %{text} ventes<extra></extra>")
        fig.add_scatter(x=[str(y) for y in years], y=ann.loc[years, "median"], name="Prix médian au m²",
                        mode="lines+markers+text", line=dict(color=SLATE, width=3),
                        text=[u.fmt_eur(v, True) for v in ann.loc[years, "median"]], textposition="top center",
                        hovertemplate="%{x} : %{text}<extra></extra>", secondary_y=True)
        lo, hi = ann["median"].min(), ann["median"].max()
        fig.update_yaxes(title_text="Ventes", secondary_y=False)
        fig.update_yaxes(title_text="€/m²", range=[lo * 0.97, hi * 1.02], secondary_y=True, showgrid=False)
        fig.update_layout(height=320, legend=dict(orientation="h", y=-0.15), margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(u.plotly_fr(fig), width="stretch")
    st.page_link("pages/1_Evolution.py", label="Preuve détaillée : page Évolution",
                 icon=u.page_icon("pages/1_Evolution.py"))

# Constat 2 ---------------------------------------------------------------- #
best_z = max(z_chg, key=z_chg.get)
worst_z = min(z_chg, key=z_chg.get)
best_t = max(t_chg, key=t_chg.get)
worst_t = min(t_chg, key=t_chg.get)
gap_z = z_chg[best_z] - z_chg[worst_z]
gap_t = t_chg[best_t] - t_chg[worst_t]
subj = u.SUBJECTS

TWO_SPEED = 0.01  # écart minimal (1 pt) pour parler de « deux vitesses »
noun = "reprise" if idf_chg > 0.005 else ("baisse" if idf_chg < -0.005 else "stabilisation")
zone_split, type_split = gap_z >= TWO_SPEED, gap_t >= TWO_SPEED
z_txt = f"{subj[best_z][0]} {u.fmt_pct(z_chg[best_z])} contre {subj[worst_z][0]} {u.fmt_pct(z_chg[worst_z])}"
t_txt = f"{subj[best_t][0]} {u.fmt_pct(t_chg[best_t])} contre {subj[worst_t][0]} {u.fmt_pct(t_chg[worst_t])}"
if zone_split and type_split:
    title2 = f"2. Une {noun} à deux vitesses : {z_txt}, {t_txt}"
elif type_split:
    title2 = (f"2. Une {noun} homogène entre zones (écart {u._num(gap_z * 100, 1)} pt), "
              f"mais à deux vitesses selon le type de bien : {t_txt}")
elif zone_split:
    title2 = (f"2. Une {noun} à deux vitesses selon les zones : {z_txt} ; écart de "
              f"{u._num(gap_t * 100, 1)} pt seulement entre types de biens")
else:
    title2 = f"2. Une {noun} homogène : moins de 1 pt d'écart entre zones et entre types de biens"

with st.container(border=True):
    st.subheader(title2, anchor=False)
    c1, c2 = st.columns([3, 2])
    with c1:
        u.evidence_box("constat", (
            f"Entre {N1} et {N}, le prix médian au m² "
            + ", ".join(
                f"{phrase(z_chg[z])} {'à Paris' if z == 'Paris' else 'en ' + z.lower()}" for z in u.ZONE_COLORS
            )
            + f" (Île-de-France : {u.fmt_pct(idf_chg)}). Par type de bien, il "
            + " et ".join(
                f"{phrase(t_chg[t])} pour les {u.PROPERTY_LABELS[t].lower()}" for t in u.TYPE_COLORS
            )
            + f". Écart entre zones extrêmes : <b>{u._num(gap_z * 100, 1)} pt</b> ; entre types : "
              f"<b>{u._num(gap_t * 100, 1)} pt</b>."
        ))
        parts = []
        if type_split:
            parts.append(
                f"Le segment des {u.PROPERTY_LABELS[worst_t].lower()} s'ajuste plus fortement que celui des "
                f"{u.PROPERTY_LABELS[best_t].lower()}. Hypothèse : des biens plus chers à l'unité, donc plus "
                "dépendants du crédit, réagissent davantage aux conditions de financement."
            )
        if zone_split:
            parts.append(
                f"L'écart entre {subj[best_z][0]} et {subj[worst_z][0]} suggère des marchés locaux distincts "
                "(attractivité, transports, structure du parc), à confirmer par des données hors DVF."
            )
        if not parts:
            parts.append("Le mouvement est général : il relève plutôt d'un facteur commun à toute la région "
                         "(conditions de crédit, conjoncture) que de dynamiques locales.")
        parts.append(f"Les deux lectures se recouvrent en partie : {u.fmt_share(house_gc, 0)} des ventes de "
                     f"maisons en {N} ont lieu en grande couronne.")
        u.evidence_box("interpretation", " ".join(parts))
    with c2:
        labels = [*u.ZONE_COLORS, *[u.PROPERTY_LABELS[t] for t in u.TYPE_COLORS]]
        vals = [*z_chg.values(), *t_chg.values()]
        colors = [*u.ZONE_COLORS.values(), *u.TYPE_COLORS.values()]
        fig = go.Figure(go.Bar(
            x=[v * 100 for v in vals], y=labels, orientation="h", marker_color=colors,
            text=[u.fmt_pct(v) for v in vals], textposition="outside",
            hovertemplate="%{y} : %{text}<extra></extra>",
        ))
        fig.add_vline(x=idf_chg * 100, line_dash="dash", line_color="#555",
                      annotation_text=f"IDF {u.fmt_pct(idf_chg)}", annotation_position="top")
        fig.update_layout(height=320, xaxis_title=f"Évolution du prix médian au m², {N1} → {N}",
                          yaxis=dict(autorange="reversed"), margin=dict(l=10, r=30, t=30, b=10))
        fig.update_xaxes(ticksuffix=" %")
        st.plotly_chart(u.plotly_fr(fig), width="stretch")
    st.page_link("pages/2_Territoires.py", label="Preuve détaillée : page Territoires",
                 icon=u.page_icon("pages/2_Territoires.py"))

# Constat 3 ---------------------------------------------------------------- #
top5 = core.head(5)
pb, pa, pr = (u.fmt_share(rb[k], 0) for k in ("gc_base", "gc_alt", "gc_rate"))
if verdict == "robuste":
    title3 = (f"3. Les communes à surveiller se concentrent en grande couronne : {pb} du top 10 %, "
              f"{pa} sans la composante liquidité, pour {pr} des communes notées")
elif verdict == "faible":
    title3 = (f"3. Les communes à surveiller sont surtout de petits marchés de grande couronne, mais la "
              f"zone n'est que légèrement surreprésentée ({pa} du top 10 % sans liquidité, pour {pr} des "
              "communes notées)")
else:
    title3 = (f"3. La place de la grande couronne parmi les communes à surveiller ({pb}) reflète surtout "
              f"son poids parmi les communes notées ({pr})")

with st.container(border=True):
    st.subheader(title3, anchor=False)
    c1, c2 = st.columns([3, 2])
    with c1:
        u.evidence_box("constat", (
            f"Sur les {u.fmt_int(rb['n'])} communes d'au moins {u.MIN_SALES} ventes en {N1} et en {N}, la "
            f"grande couronne en représente <b>{pr}</b>. Elle pèse <b>{pb}</b> du top 10 % du score de référence "
            f"(prix, volume, liquidité) et <b>{pa}</b> du top 10 % recalculé sans liquidité. "
            f"<b>{rb['n_common']} des {rb['k']} communes</b> figurent dans le top 10 % des deux versions ; en tête : "
            + ", ".join(f"<b>{r.label}</b> ({r.dept_name})" for r in top5.itertuples())
            + f". Dans le top 10 %, le prix médian {phrase(decile['price_change'].median())} et les ventes "
              f"{phrase(decile['sales_change'].median(), True)} (valeurs médianes), contre {u.fmt_pct(idf_chg)} et "
              f"{u.fmt_pct(u.yoy(ann.loc[N, 'n'], ann.loc[N1, 'n']))} pour l'Île-de-France. Ces communes sont "
              f"petites : {u.fmt_int(rb['sales_base'])} ventes en médiane ({u.fmt_int(rb['sales_alt'])} sans "
              f"liquidité), contre {u.fmt_int(rb['sales_all'])} pour l'ensemble des communes notées."
        ))
        u.evidence_box("interpretation", (
            "Ces communes cumulent baisse des prix et baisse des ventes, les signaux d'un marché qui se grippe. "
            + {
                "robuste": "La concentration en grande couronne résiste au retrait de la liquidité : elle "
                           "ne vient pas seulement de la formule.",
                "faible": "Mais la concentration en grande couronne tient en partie à la formule (la liquidité "
                          "favorise les petites communes) et au grand nombre de communes qu'elle compte : le "
                          "signal fiable est celui de <b>petits marchés locaux</b>, plus que celui d'une zone entière.",
                "absente": "Mais la grande couronne n'est pas surreprésentée une fois la liquidité retirée : le "
                           "signal porte sur des <b>communes isolées</b>, pas sur une zone.",
            }[verdict]
            + " Les médianes de petits marchés étant plus volatiles, le score désigne des communes "
              "<b>à examiner</b>, pas des communes en crise."
        ))
    with c2:
        labels3 = ["Communes notées", "Top 10 % (référence)", "Top 10 % (sans liquidité)"]
        vals3 = [rb["gc_rate"], rb["gc_base"], rb["gc_alt"]]
        fig = go.Figure(go.Bar(
            x=labels3, y=[v * 100 for v in vals3], marker_color=[u.GREY_MID, u.OCHRE, u.OCHRE_LIGHT],
            text=[u.fmt_share(v, 0) for v in vals3], textposition="outside",
            hovertemplate="%{x} : %{text} en grande couronne<extra></extra>",
        ))
        fig.update_layout(height=320, yaxis_title="Part de la grande couronne", yaxis_range=[0, 105],
                          margin=dict(l=10, r=10, t=10, b=10))
        fig.update_yaxes(ticksuffix=" %")
        st.plotly_chart(u.plotly_fr(fig), width="stretch")
    st.page_link("pages/3_Zoom_commune.py", label="Méthode, test de robustesse et scorecard complète : "
                 "page Zoom commune", icon=u.page_icon("pages/3_Zoom_commune.py"))

# --------------------------------------------------------------------------- #
# Recommandations
# --------------------------------------------------------------------------- #
st.header("Deux recommandations")
# Cible tirée des données : la zone dont le prix évolue le moins bien, et le type de bien le plus faible.
# Le score n'intervient qu'en appui (noyau robuste), pas comme preuve principale.
focus_z, focus_t = worst_z, worst_t
fz = "Paris" if focus_z == "Paris" else "la " + focus_z.lower()
ft = u.PROPERTY_LABELS[focus_t].lower()
core_share = (core["zone"] == focus_z).mean() if len(core) else np.nan
target = f"{fz} et les {ft}" if zone_split else f"les {ft}, toutes zones confondues"
zone_proof = f"{u.fmt_pct(z_chg[focus_z])} pour {fz} et de " if zone_split else ""

with st.container(border=True):
    st.subheader(f"1. Concentrer le suivi et les aides à l'accession sur {target}", anchor=False)
    t_sales = chg(typ, focus_t, "n")
    m = st.columns(3)
    if zone_split:
        m[0].metric(f"Prix {focus_z.lower() if focus_z != 'Paris' else 'Paris'} {N1} → {N}",
                    u.fmt_pct(z_chg[focus_z]), f"{u.delta_pp(z_chg[focus_z] - idf_chg)} vs IDF", delta_color="off")
    else:
        m[0].metric(f"Écart de prix entre zones {N1} → {N}", f"{u._num(gap_z * 100, 1)}{u.NBSP}pt",
                    help="Écart d'évolution du prix médian entre la zone la plus dynamique et la moins "
                         "dynamique : sous 1 pt, aucune zone ne se distingue.")
    m[1].metric(f"Prix des {ft} {N1} → {N}", u.fmt_pct(t_chg[focus_t]),
                f"{u.delta_pp(t_chg[focus_t] - idf_chg)} vs IDF", delta_color="off")
    if zone_split:
        m[2].metric(f"Part de {fz} dans le noyau robuste du score ({rb['n_common']} communes)",
                    u.fmt_share(core_share, 0),
                    help="Communes présentes dans le top 10 % des deux versions du score (avec et sans liquidité).")
    else:
        m[2].metric(f"Ventes de {ft} {N1} → {N}", u.fmt_pct(t_sales),
                    help="Évolution du nombre de ventes du segment : la liquidité du marché ciblé.")
    support = (
        f"En appui, {u.fmt_share(core_share, 0)} des communes du noyau robuste du score s'y trouvent ; ce "
        "chiffre est à lire avec le test de robustesse (constat 3). " if zone_split else
        f"Les zones évoluant de façon homogène (écart de {u._num(gap_z * 100, 1)} pt), le ciblage par type de "
        f"bien est plus pertinent qu'un ciblage géographique ; les ventes de {ft} évoluent de "
        f"{u.fmt_pct(t_sales)}. "
    )
    u.evidence_box("reco", (
        f"Prioriser {target} dans le <b>suivi trimestriel</b> de l'observatoire et dans "
        f"le <b>ciblage des aides à l'accession</b>. Preuve principale : le prix évolue de "
        f"{zone_proof}{u.fmt_pct(t_chg[focus_t])} pour les {ft}, contre "
        f"{u.fmt_pct(idf_chg)} pour l'Île-de-France. " + support
        + "Là où les prix s'ajustent, une aide à l'accession a plus d'effet de levier, à condition que le "
          "marché reste liquide : à suivre avec l'indicateur de volume."
    ))

with st.container(border=True):
    st.subheader(f"2. Examiner en priorité les {rb['n_common']} communes signalées par les deux versions du score",
                 anchor=False)
    u.evidence_box("reco", (
        f"Ces {rb['n_common']} communes restent dans le top 10 % que la liquidité soit prise en compte ou non : "
        "c'est le signal le moins dépendant des choix de pondération. Vérifier sur le terrain avant d'agir : "
        "délais de vente et stocks auprès des notaires et agences, programmes neufs livrés ou abandonnés, "
        "composition des ventes (une poignée de grandes maisons peut suffire à faire bouger une médiane). "
        "Reconduire le score chaque trimestre : une commune qui reste dans le top plusieurs périodes de suite "
        "est un signal bien plus solide qu'une apparition isolée."
    ))
    show = core[["rank", "label", "dept_name", "sales_prev", "sales", "price_change", "sales_change", "score"]]
    show.columns = ["Rang", "Commune", "Département", f"Ventes {N1}", f"Ventes {N}", "Évol. prix",
                    "Évol. ventes", "Score"]
    st.dataframe(
        show.style.format({f"Ventes {N1}": u.fmt_int, f"Ventes {N}": u.fmt_int, "Évol. prix": u.fmt_pct,
                           "Évol. ventes": u.fmt_pct, "Score": lambda v: u._num(v, 0)}),
        hide_index=True, width="stretch", height=260,
    )
    st.download_button(
        "Télécharger la liste des communes à examiner (CSV)",
        show.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
        file_name=f"communes_a_examiner_{N}.csv", mime="text/csv",
    )

# --------------------------------------------------------------------------- #
# Limite
# --------------------------------------------------------------------------- #
st.header("Une limite à garder en tête")
with st.container(border=True):
    st.subheader("Ces données décrivent le marché, elles n'en expliquent pas les causes", anchor=False)
    a_chg, m_chg = t_chg["Appartement"], t_chg["Maison"]
    lo_t, hi_t = min(a_chg, m_chg), max(a_chg, m_chg)
    inside = lo_t <= idf_chg <= hi_t
    u.evidence_box("limite", (
        "<b>Corrélation n'est pas causalité.</b> DVF enregistre des prix et des volumes, mais rien sur les "
        "<b>taux d'intérêt</b>, les <b>revenus</b> des ménages, l'<b>état</b> ou la performance énergétique des "
        "biens : les explications avancées ci-dessus restent des hypothèses.<br><br>"
        "<b>Les médianes dépendent de la composition des ventes.</b> "
        f"Entre {N1} et {N}, la part des appartements dans les ventes passe de {u.fmt_share(sh_prev)} à "
        f"{u.fmt_share(sh_cur)} ({u.delta_pp(sh_cur - sh_prev).replace('-', u.MINUS)}). "
        f"La médiane régionale ({u.fmt_pct(idf_chg)}) "
        + ("se situe entre" if inside else "sort de l'intervalle formé par")
        + f" l'évolution des appartements ({u.fmt_pct(a_chg)}) et celle des maisons ({u.fmt_pct(m_chg)}) : "
        "une partie de son mouvement tient au changement de composition, pas à l'évolution du prix d'un "
        "même bien. <b>Ne pas conclure</b> qu'un logement donné a perdu ou gagné exactement ce pourcentage."
    ))
    m = st.columns(3)
    m[0].metric(f"Part des appartements {N}", u.fmt_share(sh_cur), u.delta_pp(sh_cur - sh_prev), delta_color="off")
    m[1].metric(f"Appartements {N1} → {N}", u.fmt_pct(a_chg))
    m[2].metric(f"Maisons {N1} → {N}", u.fmt_pct(m_chg))
    st.page_link("pages/4_Donnees.py", label="Toutes les hypothèses et limites : page Données",
                 icon=u.page_icon("pages/4_Donnees.py"))
