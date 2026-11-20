"""Territoires : carte des communes, classement et benchmark des départements, top / bottom communes."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import utils as u

f = u.get_filters()

UP, DOWN = u.UP, u.DOWN
CLIP = 20  # bornes de l'échelle divergente (%) : au-delà, couleur saturée

st.title("Territoires : où le marché surperforme-t-il ou décroche-t-il ?")
u.page_scope_caption(f)

ct = u.commune_table(f.year, f.depts, f.ptype, f.new, f.surface)
if ct["sales"].sum() == 0:
    st.warning("Aucune vente ne correspond aux filtres. Élargissez la sélection dans le menu latéral.")
    st.stop()

both = ct[(ct["sales"] >= u.MIN_SALES) & (ct["sales_prev"] >= u.MIN_SALES)]

# --------------------------------------------------------------------------- #
# 1. Bandeau
# --------------------------------------------------------------------------- #
m = st.columns(3)
cover = both["sales"].sum() / ct["sales"].sum()
m[0].metric(
    "Communes analysées", f"{u.fmt_int(len(both))} / {u.fmt_int((ct['sales'] > 0).sum())}",
    f"{u.fmt_share(cover)} des ventes {f.year}", delta_color="off",
    help=f"Communes comptant au moins {u.MIN_SALES} ventes en {f.prev_year} ET en {f.year}. "
         "En dessous, la médiane est trop instable pour être interprétée.",
)
share_down = (both["price_change"] < 0).mean() if len(both) else np.nan
m[1].metric(
    "Communes dont le prix recule", u.fmt_share(share_down),
    help=f"Part des communes analysées dont le prix médian au m² baisse entre {f.prev_year} et {f.year}.",
)
if len(both):
    w = both.loc[both["price_change"].idxmin()]
    m[2].metric(
        "Plus forte baisse de prix", w["label"], u.delta_pct(w["price_change"]), delta_color="normal",
        help=f"{w['dept_name']} · {u.fmt_int(w['sales'])} ventes en {f.year}.",
    )

st.divider()

# --------------------------------------------------------------------------- #
# 2. Carte des communes
# --------------------------------------------------------------------------- #
COLOR_OPTIONS = {
    "Prix médian au m² (N)": "median_m2",
    "Évolution du prix (N vs N-1)": "price_change",
    "Évolution des ventes (N vs N-1)": "sales_change",
}
c1, c2 = st.columns([2, 1])
color_label = c1.radio("Couleur des communes", list(COLOR_OPTIONS), horizontal=True)
color_col = COLOR_OPTIONS[color_label]
is_change = color_col != "median_m2"

shown = both if is_change else ct[ct["sales"] >= u.MIN_SALES]
shown = shown.dropna(subset=["latitude", "longitude", color_col]).copy()
hidden = ct[(ct["sales"] > 0) & ~ct["code_commune"].isin(shown["code_commune"])]

if is_change:
    k_down = int((shown[color_col] < 0).sum())
    what = "leur prix reculer" if color_col == "price_change" else "leurs ventes reculer"
    title = f"{u.fmt_int(k_down)} communes sur {u.fmt_int(len(shown))} voient {what} en {f.year}"
    if k_down:
        gc_share = (shown.loc[shown[color_col] < 0, "zone"] == "Grande couronne").mean()
        title += f", dont {u.fmt_share(gc_share, 0)} en grande couronne"
else:
    top_c = shown.loc[shown["median_m2"].idxmax()]
    low_c = shown.loc[shown["median_m2"].idxmin()]
    title = (
        f"En {f.year}, le prix médian va de {u.fmt_eur(low_c['median_m2'], True)} ({low_c['label']}) "
        f"à {u.fmt_eur(top_c['median_m2'], True)} ({top_c['label']})"
    )
st.subheader(title, anchor=False)

if shown.empty:
    st.info("Aucune commune ne dépasse le seuil de ventes avec ces filtres.")
else:
    shown["hover_n"] = [
        f"{u.fmt_int(a)} ventes en {f.year} ({u.fmt_int(b)} en {f.prev_year})"
        for a, b in zip(shown["sales"], shown["sales_prev"])
    ]
    shown["hover_p"] = [u.fmt_eur(v, True) for v in shown["median_m2"]]
    shown["hover_pc"] = [u.fmt_pct(v) for v in shown["price_change"]]
    shown["hover_sc"] = [u.fmt_pct(v) for v in shown["sales_change"]]
    if is_change:
        shown["color"] = (shown[color_col] * 100).clip(-CLIP, CLIP)
        scale, midpoint, rng = u.DIV_SCALE, 0, [-CLIP, CLIP]
        cbar_title, cbar_suffix = "Évolution", " %"
    else:
        shown["color"] = shown["median_m2"]
        scale, midpoint, rng = u.SEQ_SCALE, None, None
        cbar_title, cbar_suffix = "€/m²", ""

    lat_span = shown["latitude"].max() - shown["latitude"].min()
    lon_span = shown["longitude"].max() - shown["longitude"].min()
    zoom = float(np.clip(min(np.log2(700 / max(lon_span * 1.2, 0.02)),
                             np.log2(280 / max(lat_span * 1.2, 0.02))), 7, 12))

    fig = px.scatter_map(
        shown, lat="latitude", lon="longitude", size="sales", color="color",
        color_continuous_scale=scale, color_continuous_midpoint=midpoint, range_color=rng,
        size_max=28, zoom=zoom, height=620, map_style="carto-positron",
        center=dict(lat=shown["latitude"].median(), lon=shown["longitude"].median()),
        custom_data=["label", "dept_name", "hover_n", "hover_p", "hover_pc", "hover_sc"],
    )
    fig.update_traces(hovertemplate=(
        "<b>%{customdata[0]}</b> (%{customdata[1]})<br>%{customdata[2]}<br>"
        f"Prix médian {f.year} : %{{customdata[3]}}<br>"
        "Évolution du prix : %{customdata[4]}<br>Évolution des ventes : %{customdata[5]}<extra></extra>"
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_colorbar=dict(title=cbar_title, ticksuffix=cbar_suffix),
    )
    st.plotly_chart(u.plotly_fr(fig).update_layout(margin=dict(l=0, r=0, t=0, b=0)), width="stretch")

    n_gps = int(u.filter_data((f.year,), f.depts, f.ptype, f.new, f.surface)["latitude"].isna().sum())
    st.caption(
        f"Taille du point = nombre de ventes en {f.year}. "
        + (f"Couleur bornée à ±{CLIP} % (au-delà, couleur saturée) ; rouge = baisse, vert = hausse : "
           "sens de variation, sans jugement de valeur. " if is_change else "")
        + f"{u.fmt_int(len(hidden))} communes masquées (moins de {u.MIN_SALES} ventes"
        + (f" en {f.prev_year} ou en {f.year}" if is_change else f" en {f.year}")
        + f", soit {u.fmt_share(hidden['sales'].sum() / ct['sales'].sum())} des ventes). "
        f"{u.fmt_int(n_gps)} ventes {f.year} sans coordonnées GPS sont exclues de la carte uniquement."
    )
    if is_change and len(shown):
        by_zone = shown.groupby("zone")[color_col].median()
        u.takeaway(
            "évolution médiane des communes par zone : "
            + " ; ".join(f"{z} {u.fmt_pct(by_zone[z])}" for z in u.ZONE_COLORS if z in by_zone.index)
            + ". Une commune isolée qui change de couleur peut refléter quelques ventes atypiques : "
              "à confirmer dans le Zoom commune."
        )
    elif len(shown):
        ratio = top_c["median_m2"] / low_c["median_m2"]
        by_zone = shown.groupby("zone")["median_m2"].median()
        u.takeaway(
            f"le prix au m² varie d'un facteur {str(round(ratio, 1)).replace('.', ',')} entre la commune "
            "la plus chère et la moins chère. Prix médian de la commune type par zone : "
            + " ; ".join(f"{z} {u.fmt_eur(by_zone[z], True)}" for z in u.ZONE_COLORS if z in by_zone.index)
            + "."
        )

st.divider()

# --------------------------------------------------------------------------- #
# 3. Classement des départements
# --------------------------------------------------------------------------- #
dt = u.dept_table(f)
region = u.get_subset(f, region=True)
r_cur = region[region["annee"] == f.year]
r_prev = region[region["annee"] == f.prev_year]
idf = {
    "median_m2": r_cur["prix_m2"].median(),
    "price_change": u.yoy(r_cur["prix_m2"].median(), r_prev["prix_m2"].median()),
    "sales": np.nan,
    "sales_change": u.yoy(len(r_cur), len(r_prev)),
}
RANK_OPTIONS = {
    "Prix médian au m²": ("median_m2", lambda v: u.fmt_eur(v, True)),
    "Évolution du prix": ("price_change", u.fmt_pct),
    "Nombre de ventes": ("sales", u.fmt_int),
    "Évolution des ventes": ("sales_change", u.fmt_pct),
}
rank_label = st.radio("Indicateur du classement", list(RANK_OPTIONS), horizontal=True)
col, fmt = RANK_OPTIONS[rank_label]
dr = dt.sort_values(col)
top, bottom = dr.iloc[-1], dr.iloc[0]
if col == "median_m2":
    title = (f"{top['dept_name']} reste le plus cher ({fmt(top[col])}), "
             f"{bottom['dept_name']} le plus abordable ({fmt(bottom[col])})")
elif col == "price_change":
    title = (f"{top['dept_name']} affiche la meilleure évolution des prix ({fmt(top[col])}), "
             f"{bottom['dept_name']} la plus faible ({fmt(bottom[col])})")
elif col == "sales":
    title = (f"{top['dept_name']} concentre le plus de ventes ({fmt(top[col])}, "
             f"{u.fmt_share(top[col] / dr[col].sum(), 0)} de l'Île-de-France)")
else:
    title = (f"{top['dept_name']} : plus forte évolution des ventes ({fmt(top[col])}) ; "
             f"{bottom['dept_name']} : la plus faible ({fmt(bottom[col])})")
st.subheader(title, anchor=False)

scale = 100 if col in ("price_change", "sales_change") else 1
fig = go.Figure(go.Bar(
    x=dr[col] * scale, y=dr["dept_name"], orientation="h",
    marker_color=[u.DEPT_COLORS[n] if c in f.depts else u.GREY for n, c in zip(dr["dept_name"], dr["code"])],
    text=[fmt(v) for v in dr[col]], textposition="outside",
    hovertemplate="<b>%{y}</b> : %{text}<extra></extra>",
))
if pd.notna(idf[col]):
    fig.add_vline(x=idf[col] * scale, line_dash="dash", line_color="#555",
                  annotation_text=f"Île-de-France : {fmt(idf[col])}", annotation_position="top")
fig.update_layout(height=400, xaxis_title=rank_label + (f", {f.prev_year} → {f.year}" if scale == 100 else f" ({f.year})"))
if scale == 100:
    fig.update_xaxes(ticksuffix=" %")
st.plotly_chart(u.plotly_fr(fig), width="stretch")
st.caption("Classement sur les 8 départements avec les filtres type de bien, neuf / ancien et surface ; "
           "les barres grises sont hors de votre sélection.")

# --------------------------------------------------------------------------- #
# 4. Benchmark par département
# --------------------------------------------------------------------------- #
st.subheader(f"Benchmark {f.year} : chaque département face à la médiane Île-de-France", anchor=False)
BENCH_OPTIONS = {"Prix médian au m²": ("prix_m2", True), "Prix médian d'un bien": ("valeur_fonciere", False)}
bench_label = st.radio("Indicateur du benchmark", list(BENCH_OPTIONS), horizontal=True)
bcol, per_m2 = BENCH_OPTIONS[bench_label]

cur_by = r_cur.groupby("dept_name")[bcol].median()
prev_by = r_prev.groupby("dept_name")[bcol].median()
ref = r_cur[bcol].median()
bench = pd.DataFrame({
    "Département": cur_by.index,
    f"Valeur {f.year}": cur_by.to_numpy(),
    "Médiane IDF": ref,
    "Écart": cur_by.to_numpy() - ref,
    "Écart (%)": cur_by.to_numpy() / ref - 1,
    f"Évolution {f.prev_year} → {f.year}": (cur_by / prev_by - 1).reindex(cur_by.index).to_numpy(),
}).sort_values("Écart (%)", ascending=False)
idf_row = pd.DataFrame([{
    "Département": "Île-de-France", f"Valeur {f.year}": ref, "Médiane IDF": ref, "Écart": 0.0,
    "Écart (%)": 0.0, f"Évolution {f.prev_year} → {f.year}": u.yoy(ref, r_prev[bcol].median()),
}])
bench = pd.concat([bench, idf_row], ignore_index=True)

eur = (lambda v: u.fmt_eur(v, True)) if per_m2 else u.fmt_eur
selected_names = {u.DEPT_NAMES[d] for d in f.depts}
evo_col = f"Évolution {f.prev_year} → {f.year}"


def signed_eur(v: float) -> str:
    return ("+" if v > 0 else u.MINUS if v < 0 else "") + eur(abs(v))


styled = (
    bench.style.format({
        f"Valeur {f.year}": eur, "Médiane IDF": eur, "Écart": signed_eur,
        "Écart (%)": u.fmt_pct, evo_col: u.fmt_pct,
    })
    .map(lambda v: f"color: {UP if v > 0 else DOWN}" if pd.notna(v) and v != 0 else "",
         subset=["Écart (%)", evo_col])
    .apply(lambda r: ["font-weight: 700" if (r["Département"] in selected_names and not f.all_depts)
                      or r["Département"] == "Île-de-France" else ""] * len(r), axis=1)
)
st.dataframe(styled, hide_index=True, width="stretch")
above = bench[(bench["Écart (%)"] > 0) & (bench["Département"] != "Île-de-France")]["Département"].tolist()
u.takeaway(
    f"{len(above)} départements sur 8 sont au-dessus de la médiane régionale "
    f"({', '.join(above) if above else 'aucun'}). L'écart mesure un niveau de prix, l'évolution "
    "mesure une dynamique : un département peut être cher et décrocher, ou abordable et repartir."
)
st.download_button(
    "Télécharger le benchmark (CSV)",
    bench.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
    file_name=f"benchmark_departements_{f.year}.csv", mime="text/csv",
)

st.divider()

# --------------------------------------------------------------------------- #
# 5. Top 10 / Bottom 10 communes
# --------------------------------------------------------------------------- #
if len(both) >= 2:
    k = min(10, len(both) // 2) if len(both) < 20 else 10
    topk = both.nlargest(k, "price_change")
    botk = both.nsmallest(k, "price_change")
    st.subheader(
        f"Évolution du prix {f.prev_year} → {f.year} : de {u.fmt_pct(botk.iloc[0]['price_change'])} "
        f"({botk.iloc[0]['label']}) à {u.fmt_pct(topk.iloc[0]['price_change'])} ({topk.iloc[0]['label']})",
        anchor=False,
    )

    def bar(d: pd.DataFrame, name: str) -> go.Figure:
        d = d.sort_values("price_change")
        fig = go.Figure(go.Bar(
            x=d["price_change"] * 100, y=d["label"], orientation="h",
            marker_color=[u.DEPT_COLORS[n] for n in d["dept_name"]],
            text=[u.fmt_pct(v) for v in d["price_change"]], textposition="outside",
            customdata=np.stack([d["dept_name"], d["sales_prev"].map(u.fmt_int), d["sales"].map(u.fmt_int)], -1),
            hovertemplate=(f"<b>%{{y}}</b> (%{{customdata[0]}})<br>%{{text}}<br>"
                           f"Ventes {f.prev_year} : %{{customdata[1]}} · {f.year} : %{{customdata[2]}}<extra></extra>"),
        ))
        fig.update_layout(title=name, height=420, xaxis_title=None)
        fig.update_xaxes(ticksuffix=" %")
        return u.plotly_fr(fig)

    c1, c2 = st.columns(2)
    c1.plotly_chart(bar(topk, f"Top {k} : plus fortes hausses"), width="stretch")
    c2.plotly_chart(bar(botk, f"Bottom {k} : plus fortes baisses"), width="stretch")
    zone_bot = botk["zone"].value_counts()
    u.takeaway(
        f"parmi les {k} plus fortes baisses, "
        + ", ".join(f"{n} {'à Paris' if z == 'Paris' else 'en ' + z.lower()}"
                    for z, n in zone_bot.items())
        + f". Ces classements portent sur des communes d'au moins {u.MIN_SALES} ventes par an : "
          "une médiane sur quelques dizaines de ventes reste sensible à la composition du parc vendu."
    )
    st.caption("Couleur des barres = département (même code couleur sur toutes les pages).")
else:
    st.info("Pas assez de communes au-dessus du seuil pour établir un classement.")
