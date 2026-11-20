# Observatoire des ventes de logements en Île-de-France

Tableau de bord Streamlit de Business Intelligence sur les ventes de logements en Île-de-France
de 2023 à 2025, construit à partir des données publiques DVF (Demandes de valeurs foncières).

Projet individuel — EFREI, M1 BDML, cours Data Visualization. Auteur : Clément Eugène.

## Contexte et décideur

Après la hausse des taux de crédit, le marché immobilier francilien a connu un choc en 2024
(forte baisse des ventes), puis un rebond des volumes en 2025. La question n'est plus seulement
« le marché repart-il ? » mais « **où** repart-il, et où ne repart-il pas ? ».

**Décideur visé :** analyste d'un observatoire régional du logement ou du service habitat de la
Région Île-de-France.

**Décisions éclairées :**

- où cibler les aides à l'accession à la propriété ;
- quels territoires surveiller (marché grippé, prix en baisse, faible liquidité) ;
- où le marché redémarre, et où il ne redémarre pas.

## Questions BI

1. Comment les prix et les volumes ont-ils évolué de 2023 à 2025 ? Le marché a-t-il touché le fond ?
2. Quels départements et communes surperforment ou décrochent par rapport à la médiane régionale ?
3. Quels territoires faut-il surveiller (forte baisse des prix et/ou des ventes, marché peu liquide) ?

## Données

**Source :** Demandes de valeurs foncières géolocalisées (DVF), DGFiP / Etalab, publiées sur
data.gouv.fr — <https://files.data.gouv.fr/geo-dvf/latest/csv/>

Fichiers utilisés : un fichier par année et par département, au format
`https://files.data.gouv.fr/geo-dvf/latest/csv/<année>/departements/<département>.csv.gz`,
pour les années 2023, 2024, 2025 et les départements 75, 77, 78, 91, 92, 93, 94, 95
(24 fichiers). Exemple : <https://files.data.gouv.fr/geo-dvf/latest/csv/2025/departements/75.csv.gz>

Les données brutes (environ 1,3 million de lignes) ne sont pas incluses dans le rendu. Le fichier
nettoyé utilisé par l'application est fourni dans `data/`.

### Télécharger les données brutes

Les fichiers doivent être rangés dans `data/raw/<année>/<département>.csv.gz`.

Sous PowerShell (Windows), depuis la racine du projet :

```powershell
foreach ($y in 2023, 2024, 2025) {
  New-Item -ItemType Directory -Force "data/raw/$y" | Out-Null
  foreach ($d in "75", "77", "78", "91", "92", "93", "94", "95") {
    Invoke-WebRequest "https://files.data.gouv.fr/geo-dvf/latest/csv/$y/departements/$d.csv.gz" -OutFile "data/raw/$y/$d.csv.gz"
  }
}
```

Sous bash (macOS / Linux) :

```bash
for y in 2023 2024 2025; do
  mkdir -p data/raw/$y
  for d in 75 77 78 91 92 93 94 95; do
    curl -sSL -o data/raw/$y/$d.csv.gz "https://files.data.gouv.fr/geo-dvf/latest/csv/$y/departements/$d.csv.gz"
  done
done
```

### Régénérer le fichier nettoyé

```bash
python src/prepare_data.py
```

Le script produit :

- `data/dvf_idf_clean.parquet` — fichier lu par l'application ;
- `data/dvf_idf_clean.csv` — même contenu, au format CSV ;
- `data/quality_report.csv` — nombre de lignes restantes après chaque étape du nettoyage.

Le dossier `latest` de data.gouv.fr est mis à jour par l'éditeur : un téléchargement ultérieur peut
donner des chiffres légèrement différents de ceux de ce rendu.

## Installation et lancement

Python 3.11 ou plus récent (développé sous Python 3.13).

```bash
python -m venv .venv
# Windows : .venv\Scripts\activate    macOS / Linux : source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre sur <http://localhost:8501>.

## Structure du projet

```text
app.py                      Point d'entrée : configuration, navigation, filtres communs
requirements.txt            Dépendances aux versions figées
README.md
.streamlit/config.toml      Thème de l'application
data/
  dvf_idf_clean.parquet     Données nettoyées (lues par l'application)
  dvf_idf_clean.csv         Données nettoyées (export lisible)
  quality_report.csv        Journal des étapes de nettoyage
src/
  prepare_data.py           Nettoyage des données brutes DVF
  utils.py                  Chargement en cache, filtres, KPIs, séries, scorecard, palette, formatage
pages/
  0_Vue_ensemble.py         Comprendre — vue d'ensemble
  1_Evolution.py            Comprendre — évolution dans le temps
  2_Territoires.py          Analyser — carte, classements, benchmark
  3_Zoom_commune.py         Analyser — drill-down jusqu'à la commune, scorecard
  4_Donnees.py              Décider — qualité des données, tableau, export
  5_Aide_decision.py        Décider — constats, recommandations, limite
```

## Pages de l'application

Les filtres du menu latéral s'appliquent à toutes les pages : année de référence N (comparée à
N-1), zone (Paris, petite couronne, grande couronne), départements, type de bien, neuf / ancien,
surface habitable.

| Page | Contenu |
|---|---|
| **Vue d'ensemble** | Accroche, contexte, décideur, questions BI. Neuf indicateurs clés avec leur variation sur un an : nombre de ventes, prix médian au m², prix médian d'un bien, écart à la médiane régionale, part des appartements, part du neuf, meilleur et plus faible département, commune la plus active. Graphique de l'évolution des prix par département. |
| **Évolution** | Points bas des ventes et des prix (fenêtres glissantes de 3 mois). Séries mensuelles ou trimestrielles des ventes et du prix médian, comparaison mois par mois N vs N-1, découpage par zone et par type de bien, tableau récapitulatif. |
| **Territoires** | Carte des communes (taille = ventes, couleur = prix ou évolution). Classement des départements, benchmark Valeur / Médiane IDF / Écart / Évolution, top 10 et bottom 10 des communes. |
| **Zoom commune** | Choix département puis commune. Commune comparée à son département et à l'Île-de-France, évolution trimestrielle, distribution des prix. Scorecard « territoires à surveiller » et test de robustesse du score. |
| **Données** | Funnel du nettoyage, contrôles qualité (valeurs manquantes, bornes P1 / P99, coordonnées GPS), tableau interactif des ventes, téléchargement CSV des ventes filtrées et des agrégats par commune, hypothèses et limites. |
| **Aide à la décision** | Trois constats, deux recommandations et une limite, chacun appuyé par des chiffres recalculés et un graphique ou des indicateurs de preuve. Le constat (mesuré) y est séparé de l'interprétation (hypothèse). |

Tous les chiffres affichés, y compris dans les titres et les textes, sont calculés à partir des
données au moment de l'affichage.

## Choix de nettoyage

| Étape | Règle | Lignes ou ventes restantes |
|---|---|---|
| 1 | Chargement des 24 fichiers | 1 325 104 lignes |
| 2 | Suppression des doublons exacts | 1 178 512 lignes |
| 3 | Ventes classiques et VEFA uniquement (exclut échanges, adjudications, expropriations, terrains) | 1 164 871 lignes |
| 4 | Mutations contenant exactement un logement et aucun local commercial | 364 744 ventes |
| 5 | Prix et surface renseignés | 364 592 ventes |
| 6 | Surface d'au moins 9 m² et prix d'au moins 15 000 € | 361 314 ventes |
| 7 | Prix au m² entre le 1er et le 99e centile, par année × département × type de bien | 354 051 ventes |

Résultat : **354 051 ventes dans 1 269 communes** (Paris compté par arrondissement).

**Pourquoi l'étape 4 ?** Dans DVF, une mutation (un acte de vente) s'étale sur plusieurs lignes :
logement, cave, parking, dépendances. La valeur foncière est le prix **total** de la mutation,
répété sur chaque ligne. Calculer un prix au m² sur une mutation qui contient plusieurs logements
donnerait un résultat faux. On ne garde donc que les ventes d'un seul logement. La forte baisse à
cette étape vient surtout du passage d'une unité « ligne » à une unité « vente ».

## Indicateurs et méthode

- **Prix médian au m²** : médiane des prix au m² de chaque vente (valeur foncière / surface réelle
  bâtie). La médiane est préférée à la moyenne, trop sensible aux valeurs extrêmes.
- **Fenêtres glissantes de 3 mois** : la médiane est calculée sur toutes les ventes des 3 mois, et
  non comme la médiane de trois médianes mensuelles.
- **Seuils de fiabilité** : communes à moins de 20 ventes par an masquées sur la carte et exclues
  des classements ; points mensuels à moins de 30 ventes masqués.
- **Score « territoires à surveiller »** : 0,4 × baisse de prix + 0,4 × baisse de volume
  + 0,2 × faible liquidité, chaque composante convertie en rang percentile parmi les communes
  ayant au moins 20 ventes les deux années. **Les poids sont un choix, pas une vérité.** Un test de
  robustesse recalcule le classement sans la composante liquidité (0,5 × prix + 0,5 × volume), car
  celle-ci favorise les petites communes.

## Limites

- DVF ne couvre ni l'Alsace-Moselle ni Mayotte (sans effet sur l'Île-de-France) et ne contient
  aucune information sur les acheteurs, les vendeurs, l'état du bien, sa performance énergétique
  ni le financement (taux d'intérêt, apport).
- Les ventes de plusieurs logements (immeubles, lots groupés) sont exclues.
- La surface utilisée est la surface réelle bâtie déclarée ; la surface Carrez est très
  majoritairement vide dans DVF.
- Les seuils P1 / P99, 9 m² et 15 000 € sont des choix de l'analyste.
- Les médianes dépendent de la composition des ventes (part d'appartements, de petites surfaces,
  de Paris) : une médiane qui bouge ne signifie pas que le prix d'un même bien a bougé d'autant.
  D'où le filtre par type de bien et les découpages par zone et par type.
- Les communes peu actives ont des médianes instables ; elles sont masquées ou signalées.
- Quelques ventes n'ont pas de coordonnées GPS : elles sont exclues de la carte uniquement.
- Les données décrivent le marché sans en expliquer les causes : les interprétations proposées dans
  l'application sont des hypothèses, distinguées des constats.
