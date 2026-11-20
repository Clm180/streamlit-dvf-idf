"""Préparation des données DVF Île-de-France.

Entrée  : data/raw/<année>/<département>.csv.gz  (DVF géolocalisées, files.data.gouv.fr/geo-dvf)
Sorties : data/dvf_idf_clean.parquet + .csv  (1 ligne = 1 vente d'un logement)
          data/quality_report.csv  (journal des étapes de nettoyage)

Lancer depuis la racine du projet :  python src/prepare_data.py
"""
from pathlib import Path
import pandas as pd

RAW = Path("data/raw")
OUT = Path("data")
DEPTS = ["75", "77", "78", "91", "92", "93", "94", "95"]
NATURES = ["Vente", "Vente en l'état futur d'achèvement"]
LOGEMENTS = ["Appartement", "Maison"]
COLS = ["id_mutation", "date_mutation", "nature_mutation", "valeur_fonciere",
        "code_postal", "code_commune", "nom_commune", "code_departement",
        "type_local", "surface_reelle_bati", "nombre_pieces_principales",
        "surface_terrain", "longitude", "latitude"]

log = []
def step(name, df, unit="lignes"):
    log.append({"etape": name, "nb": len(df), "unite": unit})
    print(f"{name:<55} {len(df):>9,} {unit}")

# 1. Chargement
files = sorted(RAW.glob("*/*.csv.gz"))
df = pd.concat([pd.read_csv(f, dtype=str, low_memory=False) for f in files], ignore_index=True)
df = df[df.code_departement.isin(DEPTS)]
step("1. Lignes brutes chargées", df)

# 2. Doublons exacts (même ligne publiée plusieurs fois)
df = df.drop_duplicates()
step("2. Après suppression des doublons exacts", df)

# 3. Ventes uniquement (on exclut échanges, adjudications, expropriations, terrains)
df = df[df.nature_mutation.isin(NATURES)]
step("3. Ventes classiques + VEFA", df)

# 4. Une mutation = plusieurs lignes (logement + cave + parking...).
#    La valeur foncière est le prix TOTAL de la mutation, répété sur chaque ligne.
#    On ne garde que les mutations contenant exactement 1 logement et aucun local
#    commercial, sinon le prix au m² serait faux.
types = df.groupby("id_mutation").type_local.agg(
    n_log=lambda s: s.isin(LOGEMENTS).sum(),
    n_com=lambda s: (s == "Local industriel. commercial ou assimilé").sum())
ok = types[(types.n_log == 1) & (types.n_com == 0)].index
df = df[df.id_mutation.isin(ok) & df.type_local.isin(LOGEMENTS)][COLS]
step("4. Mutations avec exactement 1 logement", df, "ventes")

# 5. Typage + valeurs manquantes
for c in ["valeur_fonciere", "surface_reelle_bati", "nombre_pieces_principales",
          "surface_terrain", "longitude", "latitude"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
df["date_mutation"] = pd.to_datetime(df.date_mutation)
df = df.dropna(subset=["valeur_fonciere", "surface_reelle_bati"])
df = df[df.surface_reelle_bati > 0]
step("5. Prix et surface renseignés", df, "ventes")

# 6. Règles métier minimales (biens non habitables / prix symboliques)
df = df[(df.surface_reelle_bati >= 9) & (df.valeur_fonciere >= 15_000)]
step("6. Surface >= 9 m² et prix >= 15 000 €", df, "ventes")

# 7. Outliers : prix au m² hors [P1 ; P99] par département x type de bien
df["prix_m2"] = df.valeur_fonciere / df.surface_reelle_bati
df["annee"] = df.date_mutation.dt.year
q = df.groupby(["annee", "code_departement", "type_local"]).prix_m2.quantile([.01, .99]).unstack()
q.columns = ["p01", "p99"]
df = df.join(q, on=["annee", "code_departement", "type_local"])
df = df[df.prix_m2.between(df.p01, df.p99)].drop(columns=["p01", "p99"])
step("7. Prix/m² dans [P1 ; P99] par année, département et type", df, "ventes")

# 8. Colonnes calculées
df["mois"] = df.date_mutation.dt.to_period("M").astype(str)
df["vefa"] = df.nature_mutation.ne("Vente")
df["prix_m2"] = df.prix_m2.round(0)

df = df.sort_values("date_mutation")
df.to_parquet(OUT / "dvf_idf_clean.parquet", index=False)   # lu par l'app (léger)
df.to_csv(OUT / "dvf_idf_clean.csv", index=False)           # version lisible / export
pd.DataFrame(log).to_csv(OUT / "quality_report.csv", index=False)
print(f"\n=> {len(df):,} ventes exportées dans data/dvf_idf_clean.csv "
      f"({df.annee.min()}-{df.annee.max()}, {df.code_commune.nunique()} communes)")
