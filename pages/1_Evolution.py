"""Évolution : séries mensuelles des prix et des volumes, N vs N-1, découpages zone et type."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src import utils as u

f = u.get_filters()

SLATE, SLATE_LIGHT, PREV_GREY = u.SLATE, u.SLATE_LIGHT, u.GREY_MID
UP, DOWN = u.UP, u.DOWN

st.title("Évolution : quand le marché a-t-il tourné ?")
st.caption(
    f"Périmètre : {f.scope_label} · "
    + (", ".join(f.active_labels) if f.active_labels else "tous les logements")
    + f" · Période complète {u.available_years()[0]}–{u.available_years()[-1]}, "
      f"comparaison mois par mois {f.year} vs {f.prev_year}."
)

# --------------------------------------------------------------------------- #
# Contrôles propres à la page
# --------------------------------------------------------------------------- #
c1, c2, c3 = st.columns(3)
freq_label = c1.radio("Granularité", ["Mensuelle", "Trimestrielle"], horizontal=True)
freq = "M" if freq_label == "Mensuelle" else "Q"
indicator = c2.radio(
    "Indicateur (comparaison et découpages)", ["Prix médian au m²", "Nombre de ventes"],
    horizontal=True,
)
is_price = indicator == "Prix médian au m²"
display = c3.radio(
    "Affichage des découpages", ["Valeurs", "Indice base 100"], horizontal=True,
    help=f"Indice base 100 = niveau moyen de {u.available_years()[0]} pour chaque segment : "
         "permet de comparer des segments de niveaux très différents.",
)


def x_ticks(periods: pd.Series, freq: str) -> dict:
    """Graduations en français : un repère par trimestre (mensuel) ou par trimestre (trimestriel)."""
    ps = pd.DatetimeIndex(periods.unique())
    vals = [p for p in ps if p.month in (1, 4, 7, 10)]
    return dict(tickvals=vals, ticktext=[u.period_label(p, freq) for p in vals], tickangle=0)


def fmt_value(v: float, price: bool) -> str:
    return u.fmt_eur(v, per_m2=True) if price else u.fmt_int(v)


# --------------------------------------------------------------------------- #
# Données de base (filtres sidebar complets, toutes années)
# --------------------------------------------------------------------------- #
ts_m = u.time_series(None, f.depts, f.ptype, f.new, f.surface, "M")
ts = ts_m if freq == "M" else u.time_series(None, f.depts, f.ptype, f.new, f.surface, "Q")

if ts_m["n"].sum() == 0:
    st.warning("Aucune vente ne correspond aux filtres. Élargissez la sélection dans le menu latéral.")
    st.stop()

# --------------------------------------------------------------------------- #
# 1. Le marché a-t-il touché le fond ? (fenêtres glissantes de 3 mois)
# --------------------------------------------------------------------------- #
roll = ts_m.dropna(subset=["roll_n"]).reset_index(drop=True)
vol_trough = roll.loc[roll["roll_n"].idxmin()]
price_roll = roll.dropna(subset=["roll_median"])
last_win = roll.iloc[-1]

st.subheader("Le marché a-t-il touché le fond ?", anchor=False)
m = st.columns(3)
m[0].metric(
    "Point bas des ventes (3 mois)", u.window_label(vol_trough["period"]),
    f"{u.fmt_int(vol_trough['roll_n'])} ventes", delta_color="off",
    help="Fenêtre glissante de 3 mois comptant le moins de ventes sur la période.",
)
if not price_roll.empty:
    price_trough = price_roll.loc[price_roll["roll_median"].idxmin()]
    m[1].metric(
        "Point bas des prix (3 mois)", u.window_label(price_trough["period"]),
        u.fmt_eur(price_trough["roll_median"], per_m2=True), delta_color="off",
        help="Fenêtre glissante de 3 mois au prix médian le plus bas. La médiane est calculée "
             "sur toutes les ventes des 3 mois.",
    )
else:
    price_trough = None
    m[1].metric("Point bas des prix (3 mois)", "—", help="Pas assez de ventes pour calculer une médiane.")

vol_rebound = u.yoy(last_win["roll_n"], vol_trough["roll_n"])
price_rebound = (
    u.yoy(last_win["roll_median"], price_trough["roll_median"]) if price_trough is not None else np.nan
)
m[2].metric(
    f"Derniers 3 mois ({u.window_label(last_win['period'])}) vs points bas",
    f"Ventes {u.fmt_pct(vol_rebound)}",
    f"Prix {u.delta_pct(price_rebound) or '—'}", delta_color="normal",
    help="Écart entre la dernière fenêtre de 3 mois et chacun des deux points bas.",
)

# --------------------------------------------------------------------------- #
# 2A. Volumes
# --------------------------------------------------------------------------- #
years = u.available_years()
ann = u.annual_stats(f.depts, f.ptype, f.new, f.surface).set_index("annee")
first_y, last_y = years[0], years[-1]
vol_vs_first = u.yoy(ann.loc[last_y, "n"], ann.loc[first_y, "n"])
if abs(vol_vs_first) <= 0.02:
    vol_phrase = f"retrouvent en {last_y} leur niveau de {first_y} ({u.fmt_pct(vol_vs_first)})"
elif vol_vs_first > 0:
    vol_phrase = f"dépassent en {last_y} leur niveau de {first_y} de {u.fmt_abs_pct(vol_vs_first)}"
else:
    vol_phrase = f"restent en {last_y} {u.fmt_abs_pct(vol_vs_first)} sous leur niveau de {first_y}"

if vol_trough["period"] == last_win["period"]:
    vol_title = (
        f"Les ventes sont à leur point bas sur les 3 derniers mois "
        f"({u.window_label(last_win['period'])}) et {vol_phrase}"
    )
else:
    vol_title = f"Les ventes ont touché le fond en {u.window_label(vol_trough['period'])} et {vol_phrase}"
st.subheader(vol_title, anchor=False)
fig = go.Figure()
fig.add_bar(
    x=ts["period"], y=ts["n"], name="Ventes " + ("du mois" if freq == "M" else "du trimestre"),
    marker_color=SLATE_LIGHT, customdata=ts["label"],
    hovertemplate="%{customdata} : %{y:,.0f} ventes<extra></extra>",
)
if freq == "M":
    roll_mean = ts_m["roll_n"] / 3
    fig.add_scatter(
        x=ts_m["period"], y=roll_mean, name="Moyenne mobile 3 mois", mode="lines",
        line=dict(color=SLATE, width=3), customdata=ts_m["label"],
        hovertemplate="%{customdata} : %{y:,.0f} ventes/mois (moy. 3 mois)<extra></extra>",
    )
fig.update_layout(height=380, legend=dict(orientation="h", y=1.08), yaxis_title="Nombre de ventes")
fig.update_xaxes(**x_ticks(ts["period"], freq))
st.plotly_chart(u.plotly_fr(fig), width="stretch")

peak_m = ts_m.loc[ts_m["n"].idxmax()]
low_m = ts_m.loc[ts_m["n"].idxmin()]
u.takeaway(
    f"les volumes sont très saisonniers : le mois le plus actif est {peak_m['label']} "
    f"({u.fmt_int(peak_m['n'])} ventes), le plus calme {low_m['label']} ({u.fmt_int(low_m['n'])}). "
    f"Il faut donc comparer un mois au même mois de l'année précédente (graphique plus bas). "
    f"Sur l'année, {first_y} : {u.fmt_int(ann.loc[first_y, 'n'])} ventes, "
    + ", ".join(
        f"{y} : {u.fmt_int(ann.loc[y, 'n'])} ({u.fmt_pct(u.yoy(ann.loc[y, 'n'], ann.loc[y - 1, 'n']))})"
        for y in years[1:]
    )
    + "."
)

# --------------------------------------------------------------------------- #
# 2B. Prix
# --------------------------------------------------------------------------- #
def link(vs_first: float) -> str:
    """Au-dessus du creux par construction : « mais » si sous le départ, « et » sinon."""
    return ", mais" if vs_first < -0.005 else " et"


if freq == "M" and price_trough is not None:
    first_win = price_roll.iloc[0]
    vs_trough = u.yoy(last_win["roll_median"], price_trough["roll_median"])
    vs_first = u.yoy(last_win["roll_median"], first_win["roll_median"])
    if price_trough["period"] == last_win["period"]:
        price_title = (
            f"Les prix sont à leur point bas sur les 3 derniers mois "
            f"({u.window_label(last_win['period'])}, {u.fmt_eur(last_win['roll_median'], True)})"
        )
    else:
        price_title = (
            f"Les prix ont touché un point bas en {u.window_label(price_trough['period'])} ; "
            f"les 3 derniers mois sont {u.position_vs(vs_trough, 'ce creux')}"
            f"{link(vs_first)} {u.position_vs(vs_first, 'début ' + str(first_y))}"
        )
else:
    qs = ts.dropna(subset=["median"])
    q_low, q_last, q_first = qs.loc[qs["median"].idxmin()], qs.iloc[-1], qs.iloc[0]
    vs_first_q = u.yoy(q_last["median"], q_first["median"])
    price_title = (
        f"Le prix médian trimestriel a touché un point bas au {q_low['label']} ; "
        f"le {q_last['label']} est {u.position_vs(u.yoy(q_last['median'], q_low['median']), 'ce creux')}"
        f"{link(vs_first_q)} {u.position_vs(vs_first_q, 'le ' + q_first['label'])}"
    )
st.subheader(price_title, anchor=False)

fig = go.Figure()
if freq == "M":
    fig.add_scatter(
        x=ts_m["period"], y=ts_m["median"], name="Médiane du mois", mode="markers+lines",
        line=dict(color=SLATE_LIGHT, width=1), marker=dict(size=6, color=SLATE_LIGHT),
        customdata=np.stack([ts_m["label"], ts_m["n"].map(u.fmt_int)], axis=-1),
        hovertemplate="%{customdata[0]} : %{y:,.0f} €/m² (%{customdata[1]} ventes)<extra></extra>",
    )
    fig.add_scatter(
        x=ts_m["period"], y=ts_m["roll_median"], name="Médiane glissante 3 mois", mode="lines",
        line=dict(color=SLATE, width=3),
        customdata=[u.window_label(p) for p in ts_m["period"]],
        hovertemplate="%{customdata} : %{y:,.0f} €/m²<extra></extra>",
    )
    if price_trough is not None:
        fig.add_annotation(
            x=price_trough["period"], y=price_trough["roll_median"],
            text=f"Point bas : {u.fmt_eur(price_trough['roll_median'], True)}",
            showarrow=True, arrowhead=2, ay=40, font=dict(color=SLATE),
        )
else:
    fig.add_scatter(
        x=ts["period"], y=ts["median"], name="Médiane du trimestre", mode="markers+lines",
        line=dict(color=SLATE, width=3), customdata=ts["label"],
        hovertemplate="%{customdata} : %{y:,.0f} €/m²<extra></extra>",
    )
fig.update_layout(height=380, legend=dict(orientation="h", y=1.08), yaxis_title="Prix médian (€/m²)")
fig.update_xaxes(**x_ticks(ts["period"], freq))
st.plotly_chart(u.plotly_fr(fig), width="stretch")

pm = ts_m.dropna(subset=["median"])
if not pm.empty:
    hi_m, lo_m = pm.loc[pm["median"].idxmax()], pm.loc[pm["median"].idxmin()]
    u.takeaway(
        f"d'un mois à l'autre, la médiane oscille fortement : du plus haut en {hi_m['label']} "
        f"({u.fmt_eur(hi_m['median'], True)}) au plus bas en {lo_m['label']} "
        f"({u.fmt_eur(lo_m['median'], True)}). Ces écarts reflètent surtout la **composition** des "
        "ventes du mois (part de Paris, d'appartements, de petites surfaces) plutôt qu'un vrai "
        "mouvement des prix : la médiane glissante sur 3 mois et les découpages par zone et par type "
        "ci-dessous en donnent une lecture plus fiable."
    )
if ts["median"].isna().any() and ts["n"].sum() > 0:
    st.caption(f"Points masqués : périodes comptant moins de {u.MIN_POINT_SALES} ventes.")

st.divider()

# --------------------------------------------------------------------------- #
# 3. N vs N-1, mois par mois
# --------------------------------------------------------------------------- #
col = "median" if is_price else "n"
cmp = ts[ts["period"].dt.year.isin([f.prev_year, f.year])].copy()
cmp["slot"] = cmp["period"].dt.month if freq == "M" else cmp["period"].dt.quarter
piv = cmp.pivot_table(index="slot", columns=cmp["period"].dt.year, values=col, aggfunc="first")
piv = piv.reindex(columns=[f.prev_year, f.year])
piv["chg"] = piv[f.year] / piv[f.prev_year] - 1
slot_labels = u.MONTHS_FR if freq == "M" else ["T1", "T2", "T3", "T4"]
x_lab = [slot_labels[i - 1] for i in piv.index]
valid = piv["chg"].dropna()
k_up, k_tot = int((valid > 0).sum()), len(valid)
n_slots = 12 if freq == "M" else 4
unit = ("mois" if freq == "M" else "trimestres") + (" comparables" if k_tot < n_slots else "")
what = "le prix médian" if is_price else "les ventes"
verb = "dépasse" if is_price else "dépassent"

st.subheader(
    f"En {f.year}, {what} {verb} le niveau de {f.prev_year} sur {k_up} {unit} sur {k_tot}",
    anchor=False,
)
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.65, 0.35], vertical_spacing=0.06)
for year, color, width in ((f.prev_year, PREV_GREY, 2), (f.year, SLATE, 3)):
    fig.add_scatter(
        x=x_lab, y=piv[year], name=str(year), mode="lines+markers",
        line=dict(color=color, width=width), row=1, col=1,
        customdata=[fmt_value(v, is_price) for v in piv[year]],
        hovertemplate=f"%{{x}} {year} : %{{customdata}}<extra></extra>",
    )
fig.add_bar(
    x=x_lab, y=piv["chg"] * 100, name="Écart en %", showlegend=False, row=2, col=1,
    marker_color=[UP if v > 0 else DOWN for v in piv["chg"].fillna(0)],
    text=[u.fmt_pct(v, 0) if pd.notna(v) else "" for v in piv["chg"]], textposition="outside",
    hovertemplate="%{x} : %{text}<extra></extra>",
)
fig.update_yaxes(title_text="€/m²" if is_price else "Ventes", row=1, col=1)
fig.update_yaxes(title_text=f"{f.year} vs {f.prev_year}", ticksuffix=" %", row=2, col=1)
fig.update_layout(height=480, legend=dict(orientation="h", y=1.06))
st.plotly_chart(u.plotly_fr(fig), width="stretch")

if k_tot:
    best_s, worst_s = valid.idxmax(), valid.idxmin()
    u.takeaway(
        f"comparer chaque {'mois' if freq == 'M' else 'trimestre'} au même de l'année précédente "
        f"neutralise la saisonnalité. Plus forte hausse : {slot_labels[best_s - 1]} "
        f"({u.fmt_pct(valid[best_s])}) ; plus forte baisse : {slot_labels[worst_s - 1]} "
        f"({u.fmt_pct(valid[worst_s])})."
        + (" Les couleurs indiquent le sens de variation, pas un jugement : une baisse des prix "
           "améliore l'accessibilité." if is_price else "")
    )

st.divider()


# --------------------------------------------------------------------------- #
# 4. Découpages par zone et par type de bien
# --------------------------------------------------------------------------- #
def breakdown(by: str, depts, ptype, colors: dict, names: dict, ignored: str) -> None:
    seg_ts = u.time_series(None, depts, ptype, f.new, f.surface, freq, by)
    seg_ann = u.annual_stats(depts, ptype, f.new, f.surface, by=(by,))
    seg_ann = seg_ann.set_index([by, "annee"])

    if freq == "M":
        y_col = "roll_median" if is_price else "roll_n"
    else:
        y_col = "median" if is_price else "n"
    seg_ts = seg_ts.copy()
    seg_ts["y"] = seg_ts[y_col] / (3 if (freq == "M" and not is_price) else 1)

    # Évolution N vs N-1 par segment (sur l'année complète)
    stat = "median" if is_price else "n"
    changes = {}
    for g in seg_ts[by].unique():
        try:
            changes[g] = u.yoy(seg_ann.loc[(g, f.year), stat], seg_ann.loc[(g, f.prev_year), stat])
        except KeyError:
            changes[g] = np.nan
    ch = pd.Series(changes).dropna().sort_values()

    if len(ch) >= 2:
        top, bottom = ch.index[-1], ch.index[0]
        (s_top, pl_top), (s_bot, pl_bot) = u.SUBJECTS[top], u.SUBJECTS[bottom]
        title = u.capitalize(
            f"{s_top} {u.trend_verb(ch[top], pl_top)} ({u.fmt_pct(ch[top])}), "
            f"{s_bot} {u.trend_verb(ch[bottom], pl_bot)} ({u.fmt_pct(ch[bottom])}) "
            f"entre {f.prev_year} et {f.year}"
        )
    else:
        title = f"Évolution {f.prev_year} → {f.year}"
    st.subheader(title, anchor=False)

    fig = go.Figure()
    for g in colors:
        s = seg_ts[seg_ts[by] == g]
        if s.empty:
            continue
        y = s["y"]
        if display == "Indice base 100":
            base = seg_ann.loc[(g, years[0]), stat] if (g, years[0]) in seg_ann.index else np.nan
            if not is_price:
                base = base / (12 if freq == "M" else 4)
            y = y / base * 100
        hover_val = (
            [f"{v:.1f}".replace(".", ",") for v in y] if display == "Indice base 100"
            else [fmt_value(v, is_price) for v in y]
        )
        fig.add_scatter(
            x=s["period"], y=y, name=names.get(g, g), mode="lines",
            line=dict(color=colors[g], width=3),
            customdata=np.stack([s["label"], hover_val], axis=-1),
            hovertemplate=f"<b>{names.get(g, g)}</b><br>%{{customdata[0]}} : %{{customdata[1]}}<extra></extra>",
        )
    if display == "Indice base 100":
        fig.add_hline(y=100, line_dash="dot", line_color="#888")
        y_title = f"Indice (moyenne {years[0]} = 100)"
    else:
        y_title = "€/m²" if is_price else ("Ventes par mois" if freq == "M" else "Ventes par trimestre")
    fig.update_layout(height=380, legend=dict(orientation="h", y=1.08), yaxis_title=y_title)
    fig.update_xaxes(**x_ticks(seg_ts["period"], freq))
    st.plotly_chart(u.plotly_fr(fig), width="stretch")

    smooth = "médiane glissante 3 mois" if is_price else "moyenne mobile 3 mois"
    st.caption(
        f"{'Courbes lissées (' + smooth + ').' if freq == 'M' else 'Valeurs trimestrielles.'} "
        f"Ce graphique ignore le filtre « {ignored} » pour comparer tous les segments ; "
        f"les autres filtres restent appliqués. Points masqués sous {u.MIN_POINT_SALES} ventes."
    )
    if len(ch) >= 2:
        u.takeaway(
            " ; ".join(f"{names.get(g, g)} {u.fmt_pct(v)}" for g, v in ch.sort_values(ascending=False).items())
            + f" ({indicator.lower()}, {f.year} vs {f.prev_year})."
        )


breakdown(
    "zone", None, f.ptype, u.ZONE_COLORS, {z: z for z in u.ZONE_COLORS}, "Départements",
)
breakdown(
    "type_local", f.depts, "Tous", u.TYPE_COLORS, u.PROPERTY_LABELS, "Type de bien",
)

st.divider()

# --------------------------------------------------------------------------- #
# 5. Tableau récapitulatif zone × type
# --------------------------------------------------------------------------- #
st.subheader(f"Récapitulatif {f.prev_year} → {f.year} par zone et type de bien", anchor=False)
tab = u.annual_stats(None, "Tous", f.new, f.surface, by=("zone", "type_local"))
tab = tab[tab["annee"].isin([f.prev_year, f.year])].copy()
n_small = int((tab["n"] < u.MIN_POINT_SALES).sum())
tab.loc[tab["n"] < u.MIN_POINT_SALES, "median"] = np.nan
wide = tab.pivot_table(index=["zone", "type_local"], columns="annee", values=["n", "median"])
summary = pd.DataFrame({
    "Zone": wide.index.get_level_values(0),
    "Type de bien": [u.PROPERTY_LABELS[t] for t in wide.index.get_level_values(1)],
    f"Ventes {f.prev_year}": wide[("n", f.prev_year)].to_numpy(),
    f"Ventes {f.year}": wide[("n", f.year)].to_numpy(),
    "Évol. ventes": (wide[("n", f.year)] / wide[("n", f.prev_year)] - 1).to_numpy(),
    f"Prix médian {f.prev_year}": wide[("median", f.prev_year)].to_numpy(),
    f"Prix médian {f.year}": wide[("median", f.year)].to_numpy(),
    "Évol. prix": (wide[("median", f.year)] / wide[("median", f.prev_year)] - 1).to_numpy(),
})
zone_order = {z: i for i, z in enumerate(u.ZONE_COLORS)}
summary = summary.sort_values(["Zone", "Type de bien"], key=lambda s: s.map(zone_order) if s.name == "Zone" else s)

styled = summary.style.format({
    f"Ventes {f.prev_year}": u.fmt_int, f"Ventes {f.year}": u.fmt_int,
    "Évol. ventes": u.fmt_pct, "Évol. prix": u.fmt_pct,
    f"Prix médian {f.prev_year}": lambda v: u.fmt_eur(v, True),
    f"Prix médian {f.year}": lambda v: u.fmt_eur(v, True),
}).map(
    lambda v: f"color: {UP if v > 0 else DOWN}" if pd.notna(v) else "",
    subset=["Évol. ventes", "Évol. prix"],
)
st.dataframe(styled, hide_index=True, width="stretch")
st.caption(
    "Ce tableau ignore les filtres « Départements » et « Type de bien » (ils sont en lignes) ; "
    "les filtres neuf / ancien et surface restent appliqués. Cliquez sur un en-tête pour trier."
    + (f" Prix non affiché (—) quand le segment compte moins de {u.MIN_POINT_SALES} ventes."
       if n_small else "")
)
