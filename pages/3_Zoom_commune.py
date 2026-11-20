"""Zoom commune : drill-down Île-de-France → département → commune, et scorecard des communes."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import utils as u

f = u.get_filters()

SLATE, IDF_GREY = u.SLATE, u.GREY_MID
UP, DOWN = u.UP, u.DOWN
MIN_Q = 10  # seuil par trimestre pour la courbe d'une commune (volumes plus faibles)


def de(nom: str) -> str:
    """Élision : « de Paris », « d'Ozoir-la-Ferrière »."""
    return f"d'{nom}" if nom[:1].upper() in "AEIOUYÉÈÊÎÔ" else f"de {nom}"


def evolution_phrase(x: float) -> str:
    """« progresse de 0,6 % » / « recule de 2,1 % » / « stagne (+0,2 %) »."""
    verb = u.trend_verb(x)
    return f"stagne ({u.fmt_pct(x)})" if verb == "stagne" else f"{verb} de {u.fmt_abs_pct(x)}"

st.title("Zoom commune : du département à la commune")
u.page_scope_caption(f)

# --------------------------------------------------------------------------- #
# 1. Sélection en cascade
# --------------------------------------------------------------------------- #
c1, c2 = st.columns(2)
dept = c1.selectbox(
    "Département", list(f.depts), format_func=lambda d: f"{d} – {u.DEPT_NAMES[d]}",
    help="Liste limitée aux départements sélectionnés dans le menu latéral.",
)
ct_dept = u.commune_table(f.year, (dept,), f.ptype, f.new, f.surface)
ct_dept = ct_dept[ct_dept["sales"] > 0].sort_values("label")
if ct_dept.empty:
    st.warning("Aucune vente dans ce département avec les filtres actuels.")
    st.stop()
default_code = ct_dept.loc[ct_dept["sales"].idxmax(), "code_commune"]
codes = ct_dept["code_commune"].tolist()
labels = dict(zip(ct_dept["code_commune"], ct_dept["label"]))
n_by = dict(zip(ct_dept["code_commune"], ct_dept["sales"]))
code = c2.selectbox(
    "Commune", codes, index=codes.index(default_code),
    format_func=lambda c: f"{labels[c]} ({u.fmt_int(n_by[c])} ventes en {f.year})",
    help="Par défaut : la commune la plus active du département.",
)
com = ct_dept.set_index("code_commune").loc[code]
name, dname = com["label"], u.DEPT_NAMES[dept]

if com["sales"] < u.MIN_SALES or com["sales_prev"] < u.MIN_SALES:
    st.warning(
        f"{name} compte {u.fmt_int(com['sales_prev'])} ventes en {f.prev_year} et "
        f"{u.fmt_int(com['sales'])} en {f.year} : sous le seuil de {u.MIN_SALES} ventes par an, "
        "les médianes et leurs évolutions sont peu fiables."
    )

# --------------------------------------------------------------------------- #
# 2. KPIs commune vs département vs IDF
# --------------------------------------------------------------------------- #
years2 = (f.prev_year, f.year)
d_com = u.filter_data(years2, None, f.ptype, f.new, f.surface, code)
d_dep = u.filter_data(years2, (dept,), f.ptype, f.new, f.surface)
d_idf = u.filter_data(years2, None, f.ptype, f.new, f.surface)


def stats(d: pd.DataFrame) -> dict:
    cur, prev = d[d["annee"] == f.year], d[d["annee"] == f.prev_year]
    return {
        "sales": len(cur),
        "sales_change": u.yoy(len(cur), len(prev)),
        "median_m2": cur["prix_m2"].median(),
        "price_change": u.yoy(cur["prix_m2"].median(), prev["prix_m2"].median()),
        "median_price": cur["valeur_fonciere"].median(),
        "median_surface": cur["surface_reelle_bati"].median(),
        "share_apart": (cur["type_local"] == "Appartement").mean() if len(cur) else np.nan,
    }


s_c, s_d, s_i = stats(d_com), stats(d_dep), stats(d_idf)

m = st.columns(4)
m[0].metric("Ventes", u.fmt_int(s_c["sales"]), u.delta_pct(s_c["sales_change"]), delta_color="normal",
            help=f"Ventes {f.year}, variation vs {f.prev_year}.")
m[1].metric("Prix médian au m²", u.fmt_eur(s_c["median_m2"], True), u.delta_pct(s_c["price_change"]),
            delta_color="normal")
m[2].metric("Écart vs département", u.fmt_pct(u.gap(s_c["median_m2"], s_d["median_m2"])),
            help=f"Prix médian au m² de {name} comparé à celui de {dname} ({u.fmt_eur(s_d['median_m2'], True)}).")
m[3].metric("Écart vs Île-de-France", u.fmt_pct(u.gap(s_c["median_m2"], s_i["median_m2"])),
            help=f"Prix médian au m² comparé à la médiane Île-de-France ({u.fmt_eur(s_i['median_m2'], True)}).")

# Tableau Valeur | Benchmark | Écart | %
ROWS = [
    ("Prix médian au m²", "median_m2", "level_m2"),
    ("Prix médian d'un bien", "median_price", "level_eur"),
    ("Surface médiane", "median_surface", "level_surf"),
    (f"Évolution du prix {f.prev_year} → {f.year}", "price_change", "rate"),
    (f"Évolution des ventes {f.prev_year} → {f.year}", "sales_change", "rate"),
    ("Part des appartements", "share_apart", "share"),
]


def fmt_level(v: float, kind: str) -> str:
    if kind == "level_m2":
        return u.fmt_eur(v, True)
    if kind == "level_eur":
        return u.fmt_eur(v)
    if kind == "level_surf":
        return f"{u.fmt_int(v)}{u.NBSP}m²"
    if kind == "share":
        return u.fmt_share(v)
    return u.fmt_pct(v)


def fmt_gap(v: float, ref: float, kind: str) -> tuple[str, str]:
    """(écart absolu, écart relatif) ; pour les taux, écart en points et pas de %."""
    if pd.isna(v) or pd.isna(ref):
        return "—", "—"
    diff = v - ref
    sign = "+" if diff > 0 else (u.MINUS if diff < 0 else "")
    if kind in ("rate", "share"):
        return f"{sign}{u._num(diff * 100, 1)}{u.NBSP}pt", "—"
    return sign + fmt_level(abs(diff), kind), u.fmt_pct(u.gap(v, ref))


rows = []
for label, key, kind in ROWS:
    gd, gdp = fmt_gap(s_c[key], s_d[key], kind)
    gi, gip = fmt_gap(s_c[key], s_i[key], kind)
    rows.append({
        "Indicateur": label, name: fmt_level(s_c[key], kind),
        dname: fmt_level(s_d[key], kind), "Écart vs dépt": gd, "% vs dépt": gdp,
        "Île-de-France": fmt_level(s_i[key], kind), "Écart vs IDF": gi, "% vs IDF": gip,
    })
st.subheader(f"{name} face à {dname} et à l'Île-de-France ({f.year})", anchor=False)
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
st.caption("Écarts en € ou m² et en % pour les niveaux ; en points (pt) pour les taux et les parts. "
           "Mêmes filtres type de bien, neuf / ancien et surface pour les trois territoires.")

st.divider()

# --------------------------------------------------------------------------- #
# 3. Évolution trimestrielle
# --------------------------------------------------------------------------- #
ts_c = u.time_series(None, None, f.ptype, f.new, f.surface, "Q", commune=code, min_n=MIN_Q)
ts_d = u.time_series(None, (dept,), f.ptype, f.new, f.surface, "Q")
ts_i = u.time_series(None, None, f.ptype, f.new, f.surface, "Q")
SERIES = [(name, ts_c, SLATE, 4), (dname, ts_d, u.DEPT_COLORS[dname], 2), ("Île-de-France", ts_i, IDF_GREY, 2)]

pc = s_c["price_change"]
title = (
    f"À {name}, le prix médian {evolution_phrase(pc)} en {f.year}, "
    f"contre {u.fmt_pct(s_d['price_change'])} pour {dname} et {u.fmt_pct(s_i['price_change'])} "
    "pour l'Île-de-France"
    if pd.notna(pc) else f"Évolution trimestrielle de {name}"
)
st.subheader(title, anchor=False)
first_year = u.available_years()[0]
ticks = [p for p in ts_i["period"]]
tick_text = [u.period_label(p, "Q") for p in ticks]

c1, c2 = st.columns(2)
fig = go.Figure()
for lbl, s, color, width in SERIES:
    fig.add_scatter(
        x=s["period"], y=s["median"], name=lbl, mode="lines+markers", line=dict(color=color, width=width),
        customdata=np.stack([s["label"], s["n"].map(u.fmt_int)], -1),
        hovertemplate=f"<b>{lbl}</b><br>%{{customdata[0]}} : %{{y:,.0f}} €/m² (%{{customdata[1]}} ventes)<extra></extra>",
    )
fig.update_layout(title="Prix médian au m² par trimestre", height=380, yaxis_title="€/m²",
                  legend=dict(orientation="h", y=-0.15))
fig.update_xaxes(tickvals=ticks[::2], ticktext=tick_text[::2])
c1.plotly_chart(u.plotly_fr(fig), width="stretch")

fig = go.Figure()
for lbl, s, color, width in SERIES:
    base = s.loc[s["period"].dt.year == first_year, "n"].mean()
    idx = s["n"] / base * 100 if base else s["n"] * np.nan
    fig.add_scatter(
        x=s["period"], y=idx, name=lbl, mode="lines+markers", line=dict(color=color, width=width),
        customdata=np.stack([s["label"], s["n"].map(u.fmt_int)], -1),
        hovertemplate=f"<b>{lbl}</b><br>%{{customdata[0]}} : indice %{{y:.0f}} (%{{customdata[1]}} ventes)<extra></extra>",
    )
fig.add_hline(y=100, line_dash="dot", line_color="#888")
fig.update_layout(title=f"Ventes par trimestre (indice, moyenne {first_year} = 100)", height=380,
                  yaxis_title="Indice", legend=dict(orientation="h", y=-0.15))
fig.update_xaxes(tickvals=ticks[::2], ticktext=tick_text[::2])
c2.plotly_chart(u.plotly_fr(fig), width="stretch")
n_masked = int(ts_c["median"].isna().sum())
u.takeaway(
    f"l'indice base 100 permet de comparer la dynamique des ventes {de(name)} à celle de territoires "
    f"beaucoup plus grands. Ventes {f.year} : {u.fmt_pct(s_c['sales_change'])} pour {name}, "
    f"{u.fmt_pct(s_d['sales_change'])} pour {dname}, {u.fmt_pct(s_i['sales_change'])} pour l'Île-de-France."
    + (f" {n_masked} trimestre(s) masqué(s) pour la commune (moins de {MIN_Q} ventes)." if n_masked else "")
)

st.divider()

# --------------------------------------------------------------------------- #
# 4. Distribution des prix au m²
# --------------------------------------------------------------------------- #
cur_c = d_com[d_com["annee"] == f.year]["prix_m2"]
if len(cur_c) >= 5:
    q1, q3 = cur_c.quantile([0.25, 0.75])
    st.subheader(
        f"En {f.year}, la moitié des ventes {de(name)} se situe entre {u.fmt_eur(q1, True)} "
        f"et {u.fmt_eur(q3, True)}",
        anchor=False,
    )
    fig = go.Figure(go.Histogram(
        x=cur_c, nbinsx=30, marker_color=SLATE, opacity=0.75, name=name,
        hovertemplate="%{x} €/m² : %{y} ventes<extra></extra>",
    ))
    for val, lbl, color, pos in (
        (s_c["median_m2"], f"Médiane {name}", SLATE, "top"),
        (s_d["median_m2"], f"Médiane {dname}", u.DEPT_COLORS[dname], "top left"),
        (s_i["median_m2"], "Médiane IDF", IDF_GREY, "top right"),
    ):
        fig.add_vline(x=val, line_dash="dash", line_color=color, line_width=2,
                      annotation_text=f"{lbl} : {u.fmt_eur(val, True)}", annotation_position=pos,
                      annotation_font_color=color)
    fig.update_layout(height=380, xaxis_title="Prix au m² (€)", yaxis_title="Nombre de ventes",
                      bargap=0.05, showlegend=False)
    st.plotly_chart(u.plotly_fr(fig), width="stretch")
    share_above = (cur_c > s_d["median_m2"]).mean()
    cur_d = d_dep[d_dep["annee"] == f.year]["prix_m2"]
    disp_c = (q3 - q1) / cur_c.median()
    disp_d = (cur_d.quantile(0.75) - cur_d.quantile(0.25)) / cur_d.median()
    comp = "plus" if disp_c > disp_d * 1.1 else ("moins" if disp_c < disp_d * 0.9 else "aussi")
    u.takeaway(
        f"{u.fmt_share(share_above, 0)} des ventes {de(name)} se font au-dessus de la médiane "
        f"départementale. L'écart interquartile représente {u.fmt_share(disp_c, 0)} de la médiane "
        f"communale, contre {u.fmt_share(disp_d, 0)} pour {dname} : les prix y sont {comp} dispersés "
        "que dans le département. Plus la distribution est large, moins la médiane seule résume la commune."
    )
else:
    st.info(f"Trop peu de ventes en {f.year} pour tracer une distribution ({len(cur_c)}).")

st.divider()

# --------------------------------------------------------------------------- #
# 5. Scorecard « territoires à surveiller »
# --------------------------------------------------------------------------- #
sc_all = u.scorecard(f.year, f.ptype, f.new, f.surface)
sc = sc_all[sc_all["code_departement"].isin(f.depts)]
if sc.empty:
    st.info("Aucune commune ne dépasse le seuil de ventes pour calculer le score.")
    st.stop()

top3 = ", ".join(sc["label"].head(3))
decile = sc_all.head(max(1, len(sc_all) // 10))
gc_share = (decile["zone"] == "Grande couronne").mean()
st.subheader(f"Communes à surveiller en priorité : {top3}", anchor=False)

c1, c2, c3 = st.columns(3)
c1.metric("Communes notées (sélection)", u.fmt_int(len(sc)),
          help=f"Communes des départements sélectionnés ayant au moins {u.MIN_SALES} ventes en "
               f"{f.prev_year} et en {f.year} (sur {u.fmt_int(len(sc_all))} en Île-de-France).")
rb = u.score_robustness(f.year, f.ptype, f.new, f.surface)
c2.metric(f"Part de la grande couronne dans le top 10 % régional ({len(decile)} communes)", u.fmt_share(gc_share, 0),
          f"{u.delta_pp(gc_share - rb['gc_rate'])} vs sa part des communes notées", delta_color="off",
          help=f"La grande couronne représente {u.fmt_share(rb['gc_rate'], 0)} des communes notées : "
               "c'est la référence à laquelle comparer sa part dans le top 10 %. Calculé sur toute "
               "l'Île-de-France, quel que soit le filtre département.")
if code in sc_all["code_commune"].values:
    r = sc_all.set_index("code_commune").loc[code]
    c3.metric(f"Rang régional de {name}", f"{int(r['rank'])}e / {u.fmt_int(len(sc_all))}",
              f"score {u.fmt_int(r['score'])} / 100", delta_color="off")
else:
    c3.metric(f"Rang régional de {name}", "—", help="Commune sous le seuil de ventes : non notée.")

with st.expander("Méthode du score : normalisation, poids et limites"):
    w = u.SCORE_WEIGHTS
    st.markdown(
        f"""
**Score = {u._num(w['price'], 1)} × baisse de prix + {u._num(w['volume'], 1)} × baisse de volume
+ {u._num(w['liquidity'], 1)} × faible liquidité**, ramené sur 100.

- **Baisse de prix** : évolution du prix médian au m² {f.prev_year} → {f.year}.
- **Baisse de volume** : évolution du nombre de ventes {f.prev_year} → {f.year}.
- **Faible liquidité** : ventes {f.year} de la commune divisées par la médiane des ventes des
  communes notées (1 = commune « typique »).

**Normalisation :** chaque composante est convertie en **rang percentile** (de 0 à 1) parmi les
{u.fmt_int(len(sc_all))} communes d'Île-de-France qui ont au moins {u.MIN_SALES} ventes les deux années :
1 = la situation la plus préoccupante (plus forte baisse, plus faible liquidité). Le rang neutralise
les écarts d'échelle entre composantes et limite le poids des valeurs extrêmes. Il est calculé sur toute
l'Île-de-France : le filtre département restreint l'affichage sans modifier les scores.

**Les poids sont un choix de l'analyste, pas une vérité.** Ils donnent autant d'importance aux prix
et aux volumes, et un rôle secondaire à la taille du marché. D'autres pondérations sont défendables
et changeraient le classement.

**Biais connu de la composante liquidité :** elle favorise mécaniquement les **petites communes**.
Les communes du top 10 % comptent en médiane {u.fmt_int(rb['sales_base'])} ventes en {f.year}, contre
{u.fmt_int(rb['sales_all'])} pour l'ensemble des communes notées. Or la grande couronne compte beaucoup
de petites communes : une partie de sa présence en tête du classement vient donc de la formule elle-même.
D'où le **test de robustesse** ci-dessous, qui recalcule le score sans cette composante
({u._num(u.ALT_WEIGHTS['price'], 1)} × prix + {u._num(u.ALT_WEIGHTS['volume'], 1)} × volume).

**Autres limites :** une commune peut avoir un score élevé à cause de quelques ventes atypiques (médianes
sur quelques dizaines de ventes, plus volatiles) ; la liquidité est mesurée sans connaître la taille du
parc de logements ; un score élevé signale une commune **à examiner**, pas un diagnostic.
"""
    )

# Test de robustesse : score sans la composante liquidité
excess_b, excess_a = rb["gc_base"] - rb["gc_rate"], rb["gc_alt"] - rb["gc_rate"]
st.subheader(
    f"Sans la composante liquidité, la grande couronne passe de {u.fmt_share(rb['gc_base'], 0)} à "
    f"{u.fmt_share(rb['gc_alt'], 0)} du top 10 %, pour {u.fmt_share(rb['gc_rate'], 0)} des communes notées",
    anchor=False,
)
w, wa = u.SCORE_WEIGHTS, u.ALT_WEIGHTS
robust = pd.DataFrame([
    {"Version du score": "Référence",
     "Poids prix / volume / liquidité": " / ".join(u._num(v, 1) for v in w.values()),
     "Grande couronne dans le top 10 %": u.fmt_share(rb["gc_base"], 0),
     "Écart à sa part des communes notées": u.delta_pp(excess_b).replace("-", u.MINUS),
     "Ventes médianes du top 10 %": u.fmt_int(rb["sales_base"])},
    {"Version du score": "Sans liquidité",
     "Poids prix / volume / liquidité": " / ".join(u._num(v, 1) for v in wa.values()),
     "Grande couronne dans le top 10 %": u.fmt_share(rb["gc_alt"], 0),
     "Écart à sa part des communes notées": u.delta_pp(excess_a).replace("-", u.MINUS),
     "Ventes médianes du top 10 %": u.fmt_int(rb["sales_alt"])},
])
st.dataframe(robust, hide_index=True, width="stretch")
verdict = u.overrep_verdict(rb)
u.takeaway(
    f"{rb['n_common']} des {rb['k']} communes du top 10 % le restent sans la composante liquidité : "
    "ce noyau est la partie la plus solide du classement. "
    + {
        "robuste": "La surreprésentation de la grande couronne résiste au retrait de la liquidité : "
                   "elle ne vient pas seulement de la formule.",
        "faible": "La surreprésentation de la grande couronne se réduit nettement sans la liquidité : "
                  "elle tient surtout à la formule et au grand nombre de communes qu'elle compte.",
        "absente": "Sans la liquidité, la grande couronne n'est plus surreprésentée : sa présence en tête "
                   "reflète son poids dans les communes notées et l'effet de la formule.",
    }[verdict]
    + f" Même sans liquidité, les communes du top restent plus petites que la moyenne "
      f"({u.fmt_int(rb['sales_alt'])} ventes en médiane contre {u.fmt_int(rb['sales_all'])}) : "
      "les médianes des petits marchés sont plus volatiles."
)

table = pd.DataFrame({
    "Rang": sc["rank"], "Commune": sc["label"], "Département": sc["dept_name"],
    f"Ventes {f.prev_year}": sc["sales_prev"], f"Ventes {f.year}": sc["sales"],
    "Évol. ventes": sc["sales_change"], f"Prix médian {f.year}": sc["median_m2"],
    "Évol. prix": sc["price_change"], "Liquidité": sc["liquidity"], "Score": sc["score"],
    "_code": sc["code_commune"],
})
styled = (
    table.drop(columns="_code").style.format({
        f"Ventes {f.prev_year}": u.fmt_int, f"Ventes {f.year}": u.fmt_int,
        "Évol. ventes": u.fmt_pct, "Évol. prix": u.fmt_pct,
        f"Prix médian {f.year}": lambda v: u.fmt_eur(v, True),
        "Liquidité": lambda v: f"{u._num(v, 2)}×", "Score": lambda v: u._num(v, 0),
    })
    .map(lambda v: f"color: {UP if v > 0 else DOWN}" if pd.notna(v) else "", subset=["Évol. ventes", "Évol. prix"])
    .map(lambda v: f"background-color: {u.rgba(u.OCHRE, 0.08 + 0.5 * v / 100)}", subset=["Score"])
    .apply(lambda r: [f"font-weight: 700; background-color: {u.HIGHLIGHT}"] * len(r)
           if table.loc[r.name, "_code"] == code else [""] * len(r), axis=1)
)
st.dataframe(styled, hide_index=True, width="stretch", height=420)
u.takeaway(
    f"valeurs médianes du top 10 % du score régional : prix {u.fmt_pct(decile['price_change'].median())}, "
    f"ventes {u.fmt_pct(decile['sales_change'].median())}. Lire ce classement avec le test de robustesse "
    "ci-dessus : un rang élevé désigne une commune à examiner. La commune sélectionnée est surlignée."
)
st.download_button(
    "Télécharger la scorecard (CSV)",
    table.drop(columns="_code").to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
    file_name=f"scorecard_communes_{f.year}.csv", mime="text/csv",
)
