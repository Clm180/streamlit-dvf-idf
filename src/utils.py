"""Fonctions partagées : chargement des données, filtres sidebar, KPIs, formatage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "dvf_idf_clean.parquet"

# --------------------------------------------------------------------------- #
# Référentiels
# --------------------------------------------------------------------------- #
DEPT_NAMES = {
    "75": "Paris",
    "77": "Seine-et-Marne",
    "78": "Yvelines",
    "91": "Essonne",
    "92": "Hauts-de-Seine",
    "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne",
    "95": "Val-d'Oise",
}
ALL_DEPTS = tuple(DEPT_NAMES)

# Zones géographiques (pré-remplissent le filtre départements)
ZONE_DEPTS = {
    "Paris": ("75",),
    "Petite couronne": ("92", "93", "94"),
    "Grande couronne": ("77", "78", "91", "95"),
}
DEPT_ZONE = {d: z for z, ds in ZONE_DEPTS.items() for d in ds}
ZONE_ALL = "Toute l'Île-de-France"
ZONE_CUSTOM = "Sélection personnalisée"
ZONE_OPTIONS = [ZONE_ALL, *ZONE_DEPTS, ZONE_CUSTOM]

# --------------------------------------------------------------------------- #
# Palette (sobre) : une couleur principale, des gris, un seul accent.
# Vert / rouge désaturés réservés aux variations (hausse / baisse).
# --------------------------------------------------------------------------- #
SLATE = "#3e5c76"         # couleur principale (bleu ardoise)
SLATE_DARK = "#2b4256"
SLATE_LIGHT = "#a9b8c6"
OCHRE = "#b5873a"         # accent unique
OCHRE_LIGHT = "#d6b98a"   # variante claire de l'accent
GREY_DARK = "#5f6368"
GREY_MID = "#9aa0a6"
GREY = "#d5d8dc"          # éléments hors sélection
GREY_BG = "#f4f5f6"       # fond des encadrés
HIGHLIGHT = "#e6ebef"     # ligne surlignée dans un tableau
TEXT = "#1d2733"
UP = "#4f7f5f"            # hausse
DOWN = "#a8574f"          # baisse
NEUTRAL_MID = "#f1f1ef"   # centre des échelles divergentes



def rgba(hex_color: str, alpha: float) -> str:
    """Couleur de la palette avec transparence (fonds de cellules de tableau)."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha:.2f})"


# Échelles continues de la carte
SEQ_SCALE = [[0, "#e8edf1"], [0.5, SLATE_LIGHT], [1, SLATE_DARK]]
DIV_SCALE = [[0, DOWN], [0.5, NEUTRAL_MID], [1, UP]]

# Zones : mêmes teintes de base que les départements qu'elles regroupent
ZONE_COLORS = {
    "Paris": SLATE_DARK,
    "Petite couronne": "#6f8aa1",
    "Grande couronne": OCHRE,
}
# Départements : nuances cohérentes par zone (bleu-gris en petite couronne, ocre / sable en grande couronne)
DEPT_COLORS = {
    "Paris": SLATE_DARK,
    "Hauts-de-Seine": "#4f6d87",
    "Seine-Saint-Denis": "#7790a6",
    "Val-de-Marne": "#9fb1c1",
    "Yvelines": "#8c6a2f",
    "Seine-et-Marne": OCHRE,
    "Essonne": "#caa463",
    "Val-d'Oise": "#dcc394",
}
TYPE_COLORS = {"Appartement": SLATE, "Maison": OCHRE}

# Icônes Material (monochromes), utilisées seulement pour la navigation et les encadrés
ICONS = {
    "app": ":material/apartment:",
    "overview": ":material/dashboard:",
    "evolution": ":material/show_chart:",
    "territories": ":material/map:",
    "zoom": ":material/location_city:",
    "data": ":material/table_chart:",
    "decision": ":material/fact_check:",
    "constat": ":material/bar_chart:",
    "interpretation": ":material/lightbulb:",
    "reco": ":material/task_alt:",
    "limite": ":material/report:",
}

MIN_SALES = 20  # seuil sous lequel une commune est jugée peu fiable
SURFACE_MIN, SURFACE_MAX = 9, 300  # SURFACE_MAX sur le curseur = « sans plafond »

PROPERTY_TYPES = ["Tous", "Appartement", "Maison"]
PROPERTY_LABELS = {"Tous": "Tous", "Appartement": "Appartements", "Maison": "Maisons"}
NEW_OPTIONS = ["Tous", "Ancien", "Neuf (VEFA)"]

MONTHS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
             "juil.", "août", "sept.", "oct.", "nov.", "déc."]


# --------------------------------------------------------------------------- #
# Formatage à la française
# --------------------------------------------------------------------------- #
NBSP = " "     # espace insécable (avant les unités)
NNBSP = " "    # espace fine insécable (séparateur de milliers)
MINUS = "−"    # signe moins typographique


def fmt_int(x: float) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x:,.0f}".replace(",", NNBSP)


def fmt_eur(x: float, per_m2: bool = False) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{fmt_int(x)}{NBSP}€" + ("/m²" if per_m2 else "")


def _num(x: float, decimals: int) -> str:
    return f"{abs(x):,.{decimals}f}".replace(",", " ").replace(".", ",").replace(" ", NNBSP)


def fmt_pct(x: float, decimals: int = 1, signed: bool = True) -> str:
    """Pourcentage pour l'affichage (x en fraction : -0.046 -> −4,6 %)."""
    if x is None or pd.isna(x):
        return "—"
    sign = (MINUS if x < 0 else "+") if signed else (MINUS if x < 0 else "")
    return f"{sign}{_num(x * 100, decimals)}{NBSP}%"


def fmt_share(x: float, decimals: int = 1) -> str:
    """Part non signée (0.62 -> 62,0 %)."""
    return fmt_pct(x, decimals, signed=False)


def fmt_abs_pct(x: float, decimals: int = 1) -> str:
    """Valeur absolue d'une variation, pour les phrases (« une baisse de 4,6 % »)."""
    return fmt_pct(abs(x), decimals, signed=False)


def delta_pct(x: float, decimals: int = 1) -> str | None:
    """Delta pour st.metric : '-' ASCII en tête pour que la couleur soit détectée."""
    if x is None or pd.isna(x):
        return None
    return f"{'-' if x < 0 else '+'}{_num(x * 100, decimals)}{NBSP}%"


def delta_pp(x: float, decimals: int = 1) -> str | None:
    """Delta en points de pourcentage (x en fraction : 0.012 -> +1,2 pt)."""
    if x is None or pd.isna(x):
        return None
    return f"{'-' if x < 0 else '+'}{_num(x * 100, decimals)}{NBSP}pt"


def month_label(period: str) -> str:
    """'2025-03' -> 'mars 2025'."""
    y, mth = period.split("-")
    return f"{MONTHS_FR[int(mth) - 1]} {y}"


# --------------------------------------------------------------------------- #
# Chargement
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Chargement des données DVF…")
def load_data() -> pd.DataFrame:
    df = pd.read_parquet(DATA_PATH)
    for col in ("code_departement", "code_commune", "code_postal"):
        df[col] = df[col].astype("string")
    df["dept_name"] = df["code_departement"].map(DEPT_NAMES)
    df["zone"] = df["code_departement"].map(DEPT_ZONE)
    return df


def available_years() -> list[int]:
    return sorted(load_data()["annee"].unique().tolist())


# --------------------------------------------------------------------------- #
# Filtres
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Filters:
    year: int
    depts: tuple[str, ...]
    ptype: str          # "Tous" / "Appartement" / "Maison"
    new: str            # "Tous" / "Ancien" / "Neuf (VEFA)"
    surface: tuple[int, int]

    @property
    def prev_year(self) -> int:
        return self.year - 1

    @property
    def all_depts(self) -> bool:
        return set(self.depts) == set(ALL_DEPTS)

    @property
    def scope_label(self) -> str:
        if self.all_depts:
            return "Île-de-France"
        for zone, ds in ZONE_DEPTS.items():
            if set(self.depts) == set(ds):
                return zone
        return ", ".join(DEPT_NAMES[d] for d in self.depts)

    @property
    def active_labels(self) -> list[str]:
        out = []
        if self.ptype != "Tous":
            out.append(PROPERTY_LABELS[self.ptype])
        if self.new != "Tous":
            out.append(self.new)
        if self.surface != (SURFACE_MIN, SURFACE_MAX):
            lo, hi = self.surface
            out.append(f"{lo}–{hi} m²" if hi < SURFACE_MAX else f"≥ {lo} m²")
        return out


_DEFAULTS = {
    "year": None,  # renseigné à la première exécution (dernière année)
    "zone": ZONE_ALL,
    "depts": list(ALL_DEPTS),
    "ptype": "Tous",
    "new": "Tous",
    "surface": (SURFACE_MIN, SURFACE_MAX),
}


def _init_state() -> None:
    years = available_years()
    for name, default in _DEFAULTS.items():
        key = f"flt_{name}"
        if key not in st.session_state:
            st.session_state[key] = years[-1] if name == "year" else default


def _sync(name: str) -> None:
    st.session_state[f"flt_{name}"] = st.session_state[f"_w_{name}"]


def _zone_of(depts) -> str:
    s = set(depts)
    if s == set(ALL_DEPTS):
        return ZONE_ALL
    for zone, ds in ZONE_DEPTS.items():
        if s == set(ds):
            return zone
    return ZONE_CUSTOM


def _on_zone() -> None:
    zone = st.session_state["_w_zone"]
    st.session_state["flt_zone"] = zone
    if zone == ZONE_ALL:
        st.session_state["flt_depts"] = list(ALL_DEPTS)
    elif zone in ZONE_DEPTS:
        st.session_state["flt_depts"] = list(ZONE_DEPTS[zone])
    # « Sélection personnalisée » : on garde les départements actuels


def _on_depts() -> None:
    _sync("depts")
    st.session_state["flt_zone"] = _zone_of(st.session_state["flt_depts"])


def _reset() -> None:
    for name in _DEFAULTS:
        st.session_state.pop(f"flt_{name}", None)


def _surface_label(v: int) -> str:
    return f"{v} m² et +" if v == SURFACE_MAX else f"{v} m²"


def sidebar_filters() -> Filters:
    """Filtres communs à toutes les pages.

    Les valeurs sont stockées dans des clés persistantes (flt_*) et recopiées
    dans les clés des widgets (_w_*), car Streamlit efface l'état d'un widget
    quand on change de page.
    """
    _init_state()
    # Année N : il faut une année N-1 dans les données
    year_options = available_years()[1:]
    if st.session_state["flt_year"] not in year_options:
        st.session_state["flt_year"] = year_options[-1]
    for name in _DEFAULTS:
        st.session_state[f"_w_{name}"] = st.session_state[f"flt_{name}"]

    sb = st.sidebar
    sb.header("Filtres")
    sb.selectbox(
        "Année de référence (N)", year_options, key="_w_year",
        format_func=lambda y: f"{y} vs {y - 1}",
        on_change=_sync, args=("year",),
        help="2023 sert d'année de comparaison pour 2024 et apparaît dans "
             "les séries de la page Évolution (2023-2025)",
    )
    sb.selectbox(
        "Zone", ZONE_OPTIONS, key="_w_zone", on_change=_on_zone,
        help="Pré-remplit la liste des départements ci-dessous.",
    )
    sb.multiselect(
        "Départements", list(ALL_DEPTS), key="_w_depts",
        format_func=lambda d: f"{d} – {DEPT_NAMES[d]}",
        on_change=_on_depts,
    )
    sb.radio(
        "Type de bien", PROPERTY_TYPES, key="_w_ptype",
        format_func=PROPERTY_LABELS.get, horizontal=True,
        on_change=_sync, args=("ptype",),
    )
    sb.radio(
        "Neuf / ancien", NEW_OPTIONS, key="_w_new", horizontal=True,
        on_change=_sync, args=("new",),
        help="VEFA = vente en l'état futur d'achèvement (logement neuf vendu sur plan).",
    )
    sb.slider(
        "Surface habitable (m²)", SURFACE_MIN, SURFACE_MAX, key="_w_surface",
        step=1, format="%d m²", on_change=_sync, args=("surface",),
        help=f"Par défaut, toutes les ventes sont incluses : la borne {SURFACE_MAX} m² "
             "signifie « sans plafond ».",
    )
    lo, hi = st.session_state["flt_surface"]
    sb.caption(f"Surface retenue : {_surface_label(lo)} → {_surface_label(hi)}")
    sb.button("Réinitialiser les filtres", on_click=_reset, width="stretch")

    depts = tuple(st.session_state["flt_depts"])
    if not depts:
        sb.warning("Aucun département sélectionné : toute l'Île-de-France est affichée.")
        depts = ALL_DEPTS

    sb.divider()
    sb.caption(
        "Source : DVF géolocalisées (DGFiP / Etalab), 2023–2025. "
        "Ventes d'un seul logement (appartement ou maison)."
    )
    sb.markdown(
        "**Clément Eugène**  \n"
        "[LinkedIn](https://www.linkedin.com/in/cl%C3%A9ment-eug%C3%A8ne-820903340/) · "
        "[GitHub](https://github.com/Clm180)"
    )

    f = Filters(
        year=int(st.session_state["flt_year"]),
        depts=tuple(sorted(depts)),
        ptype=st.session_state["flt_ptype"],
        new=st.session_state["flt_new"],
        surface=tuple(st.session_state["flt_surface"]),
    )
    st.session_state["_filters"] = f
    return f


def get_filters() -> Filters:
    """Filtres courants, posés par app.py avant l'exécution de la page."""
    if "_filters" not in st.session_state:  # page lancée seule (tests)
        return sidebar_filters()
    return st.session_state["_filters"]


@st.cache_data(show_spinner=False)
def filter_data(
    years: tuple[int, ...] | None,
    depts: tuple[str, ...] | None,
    ptype: str,
    new: str,
    surface: tuple[int, int],
    commune: str | None = None,
) -> pd.DataFrame:
    """Sous-ensemble filtré. years=None = toutes les années ; depts=None = toute l'IDF ;
    commune = code INSEE pour restreindre à une seule commune."""
    df = load_data()
    mask = pd.Series(True, index=df.index)
    if years is not None:
        mask &= df["annee"].isin(years)
    if depts is not None:
        mask &= df["code_departement"].isin(depts)
    if commune is not None:
        mask &= df["code_commune"] == commune
    if ptype != "Tous":
        mask &= df["type_local"] == ptype
    if new == "Ancien":
        mask &= ~df["vefa"]
    elif new == "Neuf (VEFA)":
        mask &= df["vefa"]
    lo, hi = surface
    if lo > SURFACE_MIN:
        mask &= df["surface_reelle_bati"] >= lo
    if hi < SURFACE_MAX:
        mask &= df["surface_reelle_bati"] <= hi
    return df.loc[mask]


def get_subset(
    f: Filters, years: tuple[int, ...] | None = (), region: bool = False
) -> pd.DataFrame:
    """Applique les filtres.

    years=() (défaut) -> N-1 et N ; years=None -> toutes les années.
    region=True ignore le filtre département (référence Île-de-France).
    """
    if years == ():
        years = (f.prev_year, f.year)
    return filter_data(years, None if region else f.depts, f.ptype, f.new, f.surface)


# --------------------------------------------------------------------------- #
# KPIs
# --------------------------------------------------------------------------- #
def kpi_summary(df: pd.DataFrame) -> dict:
    n = len(df)
    return {
        "sales": n,
        "median_m2": df["prix_m2"].median() if n else np.nan,
        "median_price": df["valeur_fonciere"].median() if n else np.nan,
        "share_apart": (df["type_local"] == "Appartement").mean() if n else np.nan,
        "share_vefa": df["vefa"].mean() if n else np.nan,
    }


def yoy(cur: float, prev: float) -> float:
    """Variation relative (fraction). NaN si la référence est absente ou nulle."""
    if prev is None or pd.isna(prev) or prev == 0 or pd.isna(cur):
        return np.nan
    return cur / prev - 1


def gap(value: float, ref: float) -> float:
    """Écart relatif à une référence (fraction)."""
    return yoy(value, ref)


@st.cache_data(show_spinner=False)
def dept_table(f: Filters) -> pd.DataFrame:
    """Prix médian €/m² et ventes par département, N vs N-1.

    Respecte les filtres type de bien / neuf-ancien / surface (pour éviter les
    effets de composition), mais couvre les 8 départements.
    """
    df = get_subset(f, region=True)
    g = (
        df.groupby(["dept_name", "annee"], observed=True)
        .agg(median_m2=("prix_m2", "median"), sales=("prix_m2", "size"))
        .unstack("annee")
    )
    out = pd.DataFrame({
        "median_m2_prev": g[("median_m2", f.prev_year)],
        "median_m2": g[("median_m2", f.year)],
        "sales_prev": g[("sales", f.prev_year)],
        "sales": g[("sales", f.year)],
    })
    out["price_change"] = out["median_m2"] / out["median_m2_prev"] - 1
    out["sales_change"] = out["sales"] / out["sales_prev"] - 1
    code_by_name = {v: k for k, v in DEPT_NAMES.items()}
    out["code"] = out.index.map(code_by_name)
    return out.reset_index().sort_values("price_change")


def best_worst_dept(table: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    t = table.dropna(subset=["price_change"])
    return t.iloc[-1], t.iloc[0]


def most_active_commune(df_cur: pd.DataFrame, df_prev: pd.DataFrame) -> dict | None:
    if df_cur.empty:
        return None
    counts = df_cur.groupby(["code_commune", "nom_commune"], observed=True).size()
    (code, name), n = counts.idxmax(), counts.max()
    n_prev = (df_prev["code_commune"] == code).sum()
    return {"name": name, "sales": int(n), "sales_change": yoy(n, n_prev)}


@st.cache_data(show_spinner=False)
def regional_headline() -> dict:
    """Chiffres clés IDF (sans filtre) pour l'accroche de l'accueil."""
    df = load_data()
    g = df.groupby("annee").agg(sales=("prix_m2", "size"), median_m2=("prix_m2", "median"))
    years = g.index.tolist()
    first, prev, last = years[0], years[-2], years[-1]
    return {
        "first": first, "prev": prev, "last": last,
        "sales_drop": yoy(g.loc[prev, "sales"], g.loc[first, "sales"]),
        "sales_rebound": yoy(g.loc[last, "sales"], g.loc[prev, "sales"]),
        "price_change": yoy(g.loc[last, "median_m2"], g.loc[first, "median_m2"]),
        "n_sales": len(df),
        "n_communes": df["code_commune"].nunique(),
    }


# --------------------------------------------------------------------------- #
# Séries temporelles
# --------------------------------------------------------------------------- #
MIN_POINT_SALES = 30  # un point (période × segment) sous ce seuil est masqué


def window_label(end: pd.Timestamp, months: int = 3) -> str:
    """Libellé d'une fenêtre glissante se terminant au mois `end` (« janv.–mars 2024 »)."""
    start = end - pd.DateOffset(months=months - 1)
    if start.year == end.year:
        return f"{MONTHS_FR[start.month - 1]}–{MONTHS_FR[end.month - 1]} {end.year}"
    return f"{MONTHS_FR[start.month - 1]} {start.year}–{MONTHS_FR[end.month - 1]} {end.year}"


def period_label(ts: pd.Timestamp, freq: str) -> str:
    if freq == "M":
        return f"{MONTHS_FR[ts.month - 1]} {ts.year}"
    return f"T{ts.quarter} {ts.year}"


@st.cache_data(show_spinner=False)
def time_series(
    years: tuple[int, ...] | None,
    depts: tuple[str, ...] | None,
    ptype: str,
    new: str,
    surface: tuple[int, int],
    freq: str = "M",
    by: str | None = None,
    commune: str | None = None,
    min_n: int = MIN_POINT_SALES,
) -> pd.DataFrame:
    """Ventes et prix médian au m² par période (mois « M » ou trimestre « Q »).

    En mensuel, ajoute une fenêtre glissante de 3 mois :
    - roll_n : nombre total de ventes sur les 3 mois ;
    - roll_median : médiane calculée sur TOUTES les ventes des 3 mois
      (et non médiane des 3 médianes mensuelles).
    Les médianes reposant sur moins de MIN_POINT_SALES ventes sont masquées (NaN).
    """
    full = load_data()
    df = filter_data(years, depts, ptype, new, surface, commune)
    month = pd.to_datetime(df["mois"])
    period = month if freq == "M" else month.dt.to_period("Q").dt.start_time
    all_months = pd.to_datetime(sorted(full["mois"].unique()))
    if years is not None:
        all_months = all_months[all_months.year.isin(years)]
    periods = all_months if freq == "M" else pd.DatetimeIndex(
        sorted(set(all_months.to_period("Q").start_time))
    )

    groups = [None] if by is None else sorted(df[by].dropna().unique())
    out = []
    for g in groups:
        sub = df if g is None else df[df[by] == g]
        sub_period = period.loc[sub.index]
        values = {p: v.to_numpy() for p, v in sub["prix_m2"].groupby(sub_period)}
        rows = []
        for i, p in enumerate(periods):
            v = values.get(p, np.array([]))
            row = {"period": p, "n": len(v), "median": np.median(v) if len(v) else np.nan}
            if freq == "M":
                if i >= 2:
                    win = np.concatenate([values.get(q, np.array([])) for q in periods[i - 2: i + 1]])
                    row["roll_n"] = len(win)
                    row["roll_median"] = np.median(win) if len(win) else np.nan
                else:
                    row["roll_n"], row["roll_median"] = np.nan, np.nan
            rows.append(row)
        res = pd.DataFrame(rows)
        if by is not None:
            res.insert(0, by, g)
        out.append(res)

    ts = pd.concat(out, ignore_index=True)
    ts.loc[ts["n"] < min_n, "median"] = np.nan
    if freq == "M":
        ts.loc[ts["roll_n"] < min_n, "roll_median"] = np.nan
    ts["label"] = [period_label(p, freq) for p in ts["period"]]
    return ts


@st.cache_data(show_spinner=False)
def annual_stats(
    depts: tuple[str, ...] | None,
    ptype: str,
    new: str,
    surface: tuple[int, int],
    by: tuple[str, ...] = (),
) -> pd.DataFrame:
    """Ventes et prix médian au m² par année (et par segment)."""
    df = filter_data(None, depts, ptype, new, surface)
    keys = [*by, "annee"]
    return (
        df.groupby(keys, observed=True)
        .agg(n=("prix_m2", "size"), median=("prix_m2", "median"))
        .reset_index()
    )


# --------------------------------------------------------------------------- #
# Agrégats par commune et scorecard
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def commune_table(
    year: int,
    depts: tuple[str, ...] | None,
    ptype: str,
    new: str,
    surface: tuple[int, int],
) -> pd.DataFrame:
    """Une ligne par commune : ventes et prix médian en N-1 et N, évolutions, position.

    Les coordonnées sont la médiane des coordonnées des ventes (plus robuste que la
    moyenne) ; les ventes sans GPS sont ignorées pour la position uniquement.
    """
    df = filter_data((year - 1, year), depts, ptype, new, surface)
    keys = ["code_commune", "nom_commune", "code_departement", "dept_name", "zone"]
    g = (
        df.groupby([*keys, "annee"], observed=True)
        .agg(n=("prix_m2", "size"), median=("prix_m2", "median"),
             median_price=("valeur_fonciere", "median"))
        .unstack("annee")
    )
    out = pd.DataFrame(index=g.index)
    for col, name in (("n", "sales"), ("median", "median_m2"), ("median_price", "median_price")):
        out[f"{name}_prev"] = g[(col, year - 1)] if (col, year - 1) in g.columns else np.nan
        out[name] = g[(col, year)] if (col, year) in g.columns else np.nan
    out[["sales_prev", "sales"]] = out[["sales_prev", "sales"]].fillna(0).astype(int)
    out["price_change"] = out["median_m2"] / out["median_m2_prev"] - 1
    out["sales_change"] = np.where(out["sales_prev"] > 0, out["sales"] / out["sales_prev"] - 1, np.nan)
    pos = df.dropna(subset=["latitude", "longitude"]).groupby("code_commune")[["latitude", "longitude"]].median()
    out = out.reset_index().join(pos, on="code_commune")
    out["label"] = out["nom_commune"].str.replace(" Arrondissement", "", regex=False)
    return out


SCORE_WEIGHTS = {"price": 0.4, "volume": 0.4, "liquidity": 0.2}
ALT_WEIGHTS = {"price": 0.5, "volume": 0.5, "liquidity": 0.0}  # test de robustesse


@st.cache_data(show_spinner=False)
def scorecard(
    year: int,
    ptype: str,
    new: str,
    surface: tuple[int, int],
    min_sales: int = MIN_SALES,
    weights: tuple[float, float, float] = tuple(SCORE_WEIGHTS.values()),
) -> pd.DataFrame:
    """Score « territoire à surveiller » (0-100) pour les communes ≥ min_sales ventes en N-1 et N.

    Chaque composante est convertie en rang percentile (0 = situation la moins
    préoccupante, 1 = la plus préoccupante) sur l'ensemble des communes d'Île-de-France
    retenues, puis pondérée par SCORE_WEIGHTS. Le filtre département ne change donc
    pas le score d'une commune : il ne fait que restreindre l'affichage.
    """
    ct = commune_table(year, None, ptype, new, surface)
    sc = ct[(ct["sales"] >= min_sales) & (ct["sales_prev"] >= min_sales)].copy()
    if sc.empty:
        return sc
    sc["liquidity"] = sc["sales"] / sc["sales"].median()
    sc["r_price"] = (-sc["price_change"]).rank(pct=True)     # forte baisse de prix -> rang élevé
    sc["r_volume"] = (-sc["sales_change"]).rank(pct=True)    # forte baisse de volume -> rang élevé
    sc["r_liquidity"] = (-sc["liquidity"]).rank(pct=True)    # peu de ventes -> rang élevé
    w_price, w_volume, w_liq = weights
    sc["score"] = 100 * (w_price * sc["r_price"] + w_volume * sc["r_volume"] + w_liq * sc["r_liquidity"])
    sc = sc.sort_values("score", ascending=False).reset_index(drop=True)
    sc["rank"] = np.arange(1, len(sc) + 1)
    return sc


@st.cache_data(show_spinner=False)
def score_robustness(year: int, ptype: str, new: str, surface: tuple[int, int]) -> dict:
    """Compare le top 10 % du score de référence et celui du score sans liquidité.

    Renvoie la part de la grande couronne dans chaque top 10 %, sa part parmi toutes les
    communes notées (taux de base), le recouvrement des deux tops et les ventes médianes.
    """
    base = scorecard(year, ptype, new, surface)
    alt = scorecard(year, ptype, new, surface, weights=tuple(ALT_WEIGHTS.values()))
    if base.empty:
        return {}
    k = max(1, len(base) // 10)
    top_b, top_a = base.head(k), alt.head(k)
    common = sorted(set(top_b["code_commune"]) & set(top_a["code_commune"]))
    gc = lambda d: (d["zone"] == "Grande couronne").mean()  # noqa: E731
    return {
        "k": k, "n": len(base),
        "gc_base": gc(top_b), "gc_alt": gc(top_a), "gc_rate": gc(base),
        "n_common": len(common), "common": common,
        "sales_base": top_b["sales"].median(), "sales_alt": top_a["sales"].median(),
        "sales_all": base["sales"].median(),
    }


def overrep_verdict(rb: dict) -> str:
    """Surreprésentation de la grande couronne dans le top 10 % une fois la liquidité retirée.

    « robuste » : ≥ 10 pt au-dessus de sa part des communes notées ; « faible » : ≥ 3 pt ;
    « absente » sinon.
    """
    excess = rb["gc_alt"] - rb["gc_rate"]
    if excess >= 0.10:
        return "robuste"
    if excess >= 0.03:
        return "faible"
    return "absente"


def trend_verb(x: float, plural: bool = False, tol: float = 0.005) -> str:
    """Verbe décrivant une évolution (tolérance ±0,5 % = stabilité)."""
    if pd.isna(x):
        return "ne sont pas comparables" if plural else "n'est pas comparable"
    if x > tol:
        return "progressent" if plural else "progresse"
    if x < -tol:
        return "reculent" if plural else "recule"
    return "stagnent" if plural else "stagne"


# Sujet grammatical de chaque segment dans les titres-constats (libellé, pluriel)
SUBJECTS = {
    "Paris": ("Paris", False),
    "Petite couronne": ("la petite couronne", False),
    "Grande couronne": ("la grande couronne", False),
    "Appartement": ("les appartements", True),
    "Maison": ("les maisons", True),
}


def capitalize(s: str) -> str:
    return s[:1].upper() + s[1:]


def position_vs(x: float, ref_label: str, tol: float = 0.005) -> str:
    """« 3,2 % au-dessus de <ref> » / « 1,5 % sous <ref> » / « au niveau de <ref> »."""
    if pd.isna(x):
        return f"sans comparaison possible avec {ref_label}"
    if abs(x) <= tol:
        return f"au niveau de {ref_label}"
    return f"{fmt_abs_pct(x)} {'au-dessus de' if x > 0 else 'sous'} {ref_label}"


# --------------------------------------------------------------------------- #
# Mise en page
# --------------------------------------------------------------------------- #
# Registre des pages : (section, fichier, titre, icône, accroche pour les liens)
PAGES = [
    ("Comprendre", "pages/0_Vue_ensemble.py", "Vue d'ensemble", ICONS["overview"],
     "Les chiffres clés du marché"),
    ("Comprendre", "pages/1_Evolution.py", "Évolution", ICONS["evolution"],
     "Quand le marché a-t-il tourné ?"),
    ("Analyser", "pages/2_Territoires.py", "Territoires", ICONS["territories"],
     "Qui surperforme, qui décroche ?"),
    ("Analyser", "pages/3_Zoom_commune.py", "Zoom commune", ICONS["zoom"],
     "Du département à la commune"),
    ("Décider", "pages/4_Donnees.py", "Données", ICONS["data"],
     "Qualité, tableau et export"),
    ("Décider", "pages/5_Aide_decision.py", "Decision Support / Recommendations", ICONS["decision"],
     "Constats et recommandations"),
]


def page_icon(path: str) -> str:
    """Icône de navigation d'une page du registre (pour st.page_link)."""
    return next(p[3] for p in PAGES if p[1] == path)


def existing_pages() -> list[tuple]:
    """Pages du registre dont le fichier existe déjà (développement progressif)."""
    return [p for p in PAGES if (ROOT / p[1]).exists()]


def plotly_fr(fig):
    """Séparateurs français (virgule décimale, espace pour les milliers)."""
    fig.update_layout(separators=", ", margin=dict(l=10, r=10, t=60, b=10))
    return fig


def takeaway(text: str) -> None:
    """Encadré « Ce qu'il faut retenir » sous un graphique."""
    st.info(f"**Ce qu'il faut retenir :** {text}")


# Encadrés : même fond gris clair, différenciés par un fin liseré (couleur / style) et l'icône
_BOX_STYLES = {
    "constat": ("Constat (données)", SLATE, "solid"),
    "interpretation": ("Interprétation (hypothèse)", OCHRE, "dashed"),
    "reco": ("Recommandation", SLATE_DARK, "solid"),
    "limite": ("Limite", GREY_DARK, "dotted"),
}
_box_counter = {"n": 0}


def _box_css() -> str:
    rules = [
        f"div[class*='st-key-evbox-'] {{background:{GREY_BG};border-radius:4px;"
        "padding:0.6rem 0.9rem;margin:0.3rem 0;gap:0.15rem}"
    ]
    for kind, (_, color, style) in _BOX_STYLES.items():
        rules.append(f"div[class*='st-key-evbox-{kind}-'] {{border-left:2px {style} {color}}}")
    rules.append("div[class*='st-key-evbox-'] p {margin-bottom:0.2rem}")
    return "<style>" + "".join(rules) + "</style>"


def evidence_box(kind: str, html: str) -> None:
    """Encadré typé : distingue constat, interprétation, recommandation et limite.

    `html` accepte du HTML simple (<b>, <br>).
    """
    label, _, _ = _BOX_STYLES[kind]
    _box_counter["n"] += 1
    with st.container(key=f"evbox-{kind}-{_box_counter['n']}"):
        st.markdown(_box_css(), unsafe_allow_html=True)
        st.caption(f"{ICONS[kind]} **{label.upper()}**")
        st.markdown(html, unsafe_allow_html=True)


def page_scope_caption(f: Filters) -> None:
    st.caption(
        f"Périmètre : {f.scope_label} · "
        + (", ".join(f.active_labels) if f.active_labels else "tous les logements")
        + f" · {f.year} vs {f.prev_year}"
    )
