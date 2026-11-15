# Terra Sense — Documentation de la plateforme

> Document tiré directement du code du dépôt `nelsonkonga/EarthScope` (branche principale, novembre 2026).
> Chaque affirmation renvoie au fichier qui l'implémente. Les chiffres de la section 6 sont ceux que renvoie l'API sur les données livrées.

---

## 1. En une phrase

**Terra Sense** est une plateforme web qui affiche sur un globe 3D des séries d'observation de la Terre de la NASA (humidité et température du sol, évaporation, ruissellement, aérosols). Elle les trace dans le temps et **teste statistiquement si leurs évolutions sont de vraies tendances ou du hasard**. Un assistant conversationnel les explique en langage courant.

## 2. Contexte du projet

- **Événement :** NASA Space Apps Challenge 2026, défi *« Be An Earth System Trend Detective! »*. Il demande d'aider un utilisateur à trouver des variables du système Terre, à les obtenir pour une région, à voir comment elles changent et à décider si le changement est significatif (énoncé repris dans `karis/detective/__init__.py`).
- **Concept de l'équipe :** *Soil Trend Detective*, appliqué au sol. L'humidité du sol relie la pluie, la végétation, les cultures et la recharge des nappes. Une baisse durable a des conséquences agricoles et écologiques, mais elle est difficile à distinguer des variations saisonnières. Terra Sense fait cette distinction avec des tests statistiques adaptés.
- **Zone d'étude :** Yaoundé (Cameroun), dessinée avec son contour administratif réel, de juillet 2002 à novembre 2014, au pas mensuel.
- **Marque :** le produit s'appelle *Terra Sense*. *Soil Trend Detective* est le concept, NASA Space Apps Challenge l'attribution. La plateforme n'est ni affiliée à la NASA ni approuvée par elle.

## 3. Architecture

```
                 NASA Giovanni (export CSV)                  geoBoundaries (contour)
                           │                                          │
                           ▼                                          ▼
 backend/data/fusion-Yaounde.csv                    backend/data/yaounde_boundary.geojson
                           │                                          │
                           └──────────────┬───────────────────────────┘
                                          ▼
                Backend Python (FastAPI) — backend/app/
                ├─ ingestion.py        lecture du CSV, conversions d'unités, trous
                ├─ catalog.py          zones, variables, échelles de couleur
                ├─ statistics.py       Theil-Sen, Mann-Kendall, climatologie, corrélations
                ├─ mann_kendall.py     Mann-Kendall avec correction de Hamed et Rao
                ├─ assistant.py        moteur de réponses + actions sur le globe
                ├─ variable_selector.py   choix des variables à partir d'une question
                └─ llm.py              rédaction des réponses par Gemini (facultatif)
                                          │  API REST /api/v1
                                          ▼
                Frontend React + TypeScript (Vite) — src/
                ├─ features/landing/   page d'accueil (/)
                └─ app/MainWorkspace   espace de visualisation (/app)
                   ├─ globe Cesium (zone colorée, frise temporelle)
                   ├─ panneaux Variables, Zones, Assistant
                   └─ fiche de zone avec graphiques et analyses
```

- Les statistiques sont **calculées à chaque requête** à partir des observations brutes. Rien n'est précalculé ni stocké (`backend/app/services/statistics.py`).
- Le globe (Cesium) n'est téléchargé qu'à l'entrée dans `/app`. La page d'accueil reste légère (`src/app/EarthScopeApp.tsx`).

## 4. Les données : d'où elles viennent, comment elles sont prises

### 4.1 Sources

| Variable | Produit NASA | Identifiant | Nature |
|---|---|---|---|
| Humidité du sol 0–10 cm | GLDAS Noah 0,25° mensuel v2.0 | `GLDAS_NOAH025_M_2.0` · `SoilMoi0_10cm_inst` | modèle de surface (estimation) |
| Humidité du sol 10–40 cm | GLDAS Noah 0,25° mensuel v2.0 | `SoilMoi10_40cm_inst` | modèle |
| Température du sol 0–10 cm | GLDAS Noah 0,25° mensuel v2.0 | `SoilTMP0_10cm_inst` | modèle |
| Température du sol 10–40 cm | GLDAS Noah 0,25° mensuel v2.1 | `GLDAS_NOAH025_M_2.1` · `SoilTMP10_40cm_inst` | modèle |
| Évaporation | GLDAS Noah 0,25° mensuel v2.1 | `Evap_tavg` | modèle |
| Ruissellement de surface | GLDAS Noah 0,25° mensuel v2.1 | `Qs_acc` | modèle |
| Épaisseur optique des aérosols | MODIS Aqua niveau 3 mensuel, collection 6.1 | `MYD08_M3` · `Deep_Blue_Aerosol_Optical_Depth_550_Land_Mean_Mean` | mesure satellitaire (maille 1°) |

- **Outil d'extraction :** NASA Giovanni, séries temporelles moyennées sur la zone (`g4.areaAvgTimeSeries`), sur le rectangle 11,4–11,65 °E, 3,75–3,98 °N, exportées dans un seul CSV : `backend/data/fusion-Yaounde.csv`.
- **Contour de la ville :** geoBoundaries gbOpen, Cameroun, niveau ADM3. C'est l'union des sept arrondissements Yaoundé I à VII, sous licence CC BY 4.0 (`backend/data/yaounde_boundary.geojson`). Il sert uniquement au dessin : les valeurs restent celles du rectangle Giovanni.

### 4.2 Lecture et préparation (`backend/app/services/ingestion.py`)

1. Chaque ligne datée du CSV est lue. Les 7 colonnes de mesures deviennent 7 séries mensuelles pour la zone `zone_yaounde`.
2. **Conversions d'unités :**
   - températures : kelvin → °C (− 273,15) ;
   - évaporation : kg m⁻² s⁻¹ → mm/jour (× 86 400) ;
   - humidité et ruissellement : laissés en kg/m².
3. **Trous :** la valeur sentinelle `−9999` et les cases vides deviennent des valeurs manquantes. Elles ne sont **jamais remplacées par zéro ni interpolées**. Les graphiques montrent un vide.
4. Le catalogue (`catalog.py`) expose zones et variables, avec pour chacune son unité, sa couleur, sa période disponible et une échelle d'affichage. Les bornes de cette échelle sont le minimum et le maximum observés, pas un modèle ajusté.

## 5. Détection des tendances (le cœur « Trend Detective »)

Le problème : une série mensuelle de sol a un **cycle saisonnier très fort** (saison des pluies, saison sèche). Un test naïf confond ce cycle avec une tendance, ou le cache. Terra Sense utilise donc des méthodes **saisonnières** et **robustes**.

### 5.1 Méthodes (`backend/app/services/statistics.py`, `mann_kendall.py`)

| Question | Méthode | Détail d'implémentation |
|---|---|---|
| La série monte-t-elle ou descend-elle de façon régulière, ou est-ce du hasard ? | **Mann-Kendall saisonnier** | Le test de Mann-Kendall est appliqué séparément à chaque mois de l'année (tous les janvier, tous les février…). Les statistiques S et leurs variances sont ensuite additionnées. Seuil : p < 0,05. Il faut au moins 8 observations (`MIN_SAMPLES`). Bibliothèque : `pymannkendall`. |
| À quelle vitesse ? | **Pente de Theil-Sen saisonnière** | Médiane des pentes entre toutes les paires d'années pour un même mois, convertie en variation par an puis par décennie. Elle est robuste aux valeurs extrêmes. |
| Séries annuelles | Mann-Kendall et Theil-Sen classiques | Utilisés quand la résolution n'est pas mensuelle. |
| Variante de l'assistant | Mann-Kendall avec **correction de Hamed et Rao** | Elle corrige l'autocorrélation entre mois successifs ; implémentée dans `mann_kendall.py`. |

Pour chaque série, la réponse de l'API (`GET /api/v1/analytics`) contient :

- la pente (par an et par décennie) ;
- la valeur p ;
- le sens : `up`, `down`, `flat` ou `insufficient` ;
- les valeurs de début et de fin de la droite de tendance, que les graphiques tracent en pointillé ;
- le nombre d'observations et de mois manquants ;
- une **climatologie mensuelle** (minimum, quartiles, médiane, maximum pour chaque mois). Elle alimente le graphique « cycle saisonnier ».

### 5.2 Relations entre variables (`GET /api/v1/analytics/multivariable`)

- **Corrélation de Pearson** entre deux à six variables, sur les dates communes, avec sa valeur p et une phrase d'interprétation (forte, modérée, faible, négligeable ; positive ou négative).
- **Recherche du meilleur décalage**, jusqu'à ±12 mois pour une série mensuelle. Elle est faite **sur les anomalies saisonnières**, pour qu'un cycle annuel commun ne soit pas pris pour un délai entre deux variables.
- **Indices normalisés (z-scores)**, pour superposer des variables d'unités différentes.

### 5.3 Ce que les tests ne disent pas

- Une tendance significative ne prouve **aucune cause**.
- GLDAS est un **modèle** forcé par des observations, pas une mesure directe du sol.
- L'humidité du sol décrit les couches supérieures : ce **n'est pas une mesure des nappes**.

## 6. Résultats actuels sur Yaoundé (2002-07 → 2014-11)

Valeurs renvoyées par l'API, méthode saisonnière, seuil p < 0,05 :

| Variable | Mois valides / 149 | Verdict | Valeur p | Pente de Theil-Sen |
|---|---|---|---|---|
| Humidité du sol 10–40 cm | 149 | **baisse significative** | 0,0002 | −2,14 kg/m² par décennie |
| Humidité du sol 0–10 cm | 149 | **baisse significative** | 0,0002 | −0,78 kg/m² par décennie |
| Température du sol 0–10 cm | 149 | **hausse significative** | < 0,001 | +0,38 °C par décennie |
| Température du sol 10–40 cm | 149 | **hausse significative** | < 0,001 | +0,49 °C par décennie |
| Évaporation | 149 | **hausse significative** | < 0,001 | +0,59 mm/jour par décennie |
| Ruissellement de surface | 149 | pas de tendance significative | 0,955 | ≈ 0 |
| Épaisseur optique des aérosols | 69 (80 mois manquants) | pas de tendance significative | 0,060 | −0,034 par décennie |

**Lecture :** sur cette période, le sol de la zone de Yaoundé devient plus sec en surface comme en profondeur, plus chaud, et l'évaporation augmente. Ces signaux sont cohérents entre eux, mais les tests ne prouvent pas de cause. La période s'arrête en 2014 parce que GLDAS 2.0 s'arrête cette année-là.

**Incohérence connue :** pour l'humidité 0–10 cm, l'assistant utilise Mann-Kendall avec correction de Hamed et Rao sur la série brute et conclut « pas de tendance significative » (p = 0,303). Le panneau d'analyse utilise la version saisonnière et conclut à une baisse (p = 0,0002). Pour des données aussi saisonnières, la **version saisonnière est la référence**. Il faut aligner l'assistant dessus.

## 7. La visualisation (`/app`)

- **Globe 3D (CesiumJS)** (`src/features/globe/`) :
  - fond Cesium World Imagery, ou tuiles 3D photoréalistes Google si une clé `VITE_GOOGLE_MAPS_API_KEY` est fournie ;
  - la ville est dessinée avec son **contour réel**, pas un rectangle.
- **Couleur de la zone** (`fieldPainter.ts`, `domain/fieldView.ts`, `domain/colorScale.ts`) :
  - la valeur du mois choisi est placée sur une rampe propre à chaque variable : du sec au saturé pour l'humidité, du froid au chaud pour la température, du ciel clair à la poussière pour les aérosols ;
  - une seule couleur par mois, car la donnée est une moyenne de zone. Un mois sans mesure laisse la zone grise ;
  - plusieurs variables s'empilent : variable principale en remplissage, secondaires en halo, particules pour l'évaporation ou les aérosols ;
  - d'un mois à l'autre, **la couleur glisse progressivement** de l'ancienne teinte vers la nouvelle. Le rendu est assuré à chaque image par un `CallbackProperty` Cesium, ce qui évite de reconstruire le polygone. Aucune valeur n'est inventée entre deux dates : seule la couleur affichée est interpolée.
- **Frise temporelle** (`features/time/Timeline.tsx`) :
  - lecture automatique à 1×, 2× ou 4×, pas à pas, curseur ;
  - les valeurs des mois suivants sont préchargées pour une lecture fluide.
- **Fiche de zone et analyses** (`features/zones/`, `features/analytics/`) :
  - valeur du mois, tendance par décennie ;
  - courbe interactive : clic pour choisir une date, glisser pour zoomer, droite de Theil-Sen en pointillé ;
  - cycle saisonnier en boîtes à moustaches ;
  - modes « variable unique », « double axe » et « indice normalisé » ;
  - carte de corrélation avec le meilleur décalage.
  - **Tous les graphiques s'agrandissent** d'un clic.
- **Raccourcis clavier** : 1, 2, 3 pour les panneaux ; espace pour la lecture ; flèches pour le globe ; `?` pour l'aide.

## 8. L'assistant conversationnel

Fonctionnement hybride (`backend/app/services/assistant.py`, `llm.py`, `src/features/assistant/`) :

1. **Comprendre la question** (`variable_selector.py`) :
   - il détecte la ville citée et ignore les négations (« sans la pluie ») ;
   - il classe les variables du catalogue par proximité sémantique. Il utilise un modèle *sentence-transformers* local (`models/modele_terrasense_final`) s'il est installé, sinon des vecteurs lexicaux ;
   - il fonctionne en français et en anglais.
2. **Calculer** : le moteur sélectionne la zone et jusqu'à trois variables, lance les tests de tendance et rédige une réponse chiffrée. Pour une question de méthode (« explique Mann-Kendall », « GLDAS ou MERRA-2 ? »), il donne une explication sans ouvrir de séries sans rapport.
3. **Agir sur l'interface** : la réponse contient des **actions** (sélectionner la zone, activer les variables, choisir le mode d'affichage) que le frontend applique au globe et aux graphiques (`src/domain/actions.ts`).
4. **Rédiger (facultatif)** : si `GEMINI_API_KEY` est défini côté backend, Gemini reformule le résultat en langage naturel. Il a pour consignes de n'utiliser que les chiffres calculés, de citer la source et de dire quand il ne sait pas. Sans clé ou en cas d'erreur, la réponse du moteur est conservée.

**Garde-fous :**
- l'assistant ne fabrique aucune mesure ;
- une ville absente du catalogue (Douala, Paris…) est signalée au lieu d'être remplacée par Yaoundé ;
- la conversation est partagée entre la page d'accueil et l'espace de visualisation.

## 9. La page d'accueil (`/`)

- Code dans `src/features/landing/`, textes dans `src/i18n/translations/en.json` et `fr.json`.
- Parcours : le problème (agriculture, écosystèmes, cycle de l'eau) → l'approche (observer, identifier les tendances, comprendre) → la méthode, avec **le vrai graphique de tendance** issu de l'API → accès au laboratoire.
- Les chiffres affichés (zones, variables, période) sont **lus en direct dans le catalogue**. Si l'API ne répond pas, la page le dit au lieu d'afficher un chiffre.
- Anglais américain par défaut, français disponible ; thèmes clair, sombre et tamisé.
- Photographies d'illustration locales (`public/images/`, provenance dans `PEXELS-SOURCES.md`). Ce sont des illustrations, pas des données.

## 10. API REST (`/api/v1`)

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/zones`, `/zones/{id}` | zones publiées, avec coordonnées et contour |
| GET | `/variables` | catalogue des variables (unité, couleur, période, échelle) |
| GET | `/layers?variableId&date` | valeur de chaque zone pour une variable et un mois (coloration du globe) |
| GET | `/timeseries?zoneId&variableId` | série complète d'une variable sur une zone, avec sa tendance |
| GET | `/analytics?zoneId&variableId[&start&end]` | Theil-Sen, Mann-Kendall, climatologie |
| GET | `/analytics/multivariable?zoneId&variableIds` | corrélations, décalages, séries alignées et normalisées |
| GET | `/rankings`, `/comparisons` | classement et comparaison de zones (prêts pour plusieurs zones) |
| POST | `/assistant/sessions` puis `/assistant/sessions/{id}/messages` | conversation avec l'assistant |

## 11. Technologies

- **Backend :**
  - Python 3.10+, FastAPI, Uvicorn ;
  - NumPy, SciPy, pymannkendall pour les statistiques ;
  - httpx pour l'appel à Gemini.
- **Frontend :**
  - React 18, TypeScript, Vite ;
  - CesiumJS pour le globe ;
  - TanStack Query pour les requêtes, Zustand pour l'état de l'espace de visualisation ;
  - CSS natif et SVG faits main (aucune bibliothèque de graphiques) ;
  - Vitest pour les tests.
- **Tests :**
  - 24 tests backend : statistiques, ingestion, assistant, repli sans Gemini ;
  - 18 tests frontend : actions de l'assistant, rendu des couches, parité des traductions.

## 12. Limites actuelles

- **Couverture :** une seule zone, Yaoundé, de 2002 à 2014. Les mailles GLDAS (0,25°) et MODIS (1°) sont plus grandes que la ville : elles décrivent une moyenne régionale.
- **Nature des données :** GLDAS est un modèle, pas une observation directe. Les aérosols ont 80 mois manquants sur 149.
- **Statistiques :** l'assistant et le panneau d'analyse utilisent deux variantes de Mann-Kendall qui peuvent diverger (section 6).
- **SHAP :** prévu mais non implémenté ; aucun modèle prédictif n'est publié.
- **Mise à jour :** pas de date dans les métadonnées. Les données sont un export Giovanni figé, pas un flux en direct.

## 13. Lancer la plateforme

```bash
pip install -r backend/requirements.txt
cd backend && PYTHONPATH=. python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Dans un second terminal, à la racine du dépôt :

```bash
npm install
npm run dev
```

Ouvrir `http://localhost:5173` pour l'accueil, `http://localhost:5173/app` pour le laboratoire.

Facultatif :
- `export GEMINI_API_KEY=...` côté backend, pour l'assistant rédigé par Gemini ;
- `VITE_GOOGLE_MAPS_API_KEY` dans `.env`, pour les tuiles 3D Google.

## 14. Captures d'écran suggérées pour le rapport

1. Accueil : le héro avec la coupe de sol.
2. Accueil : le graphique « Read a trend, not just a value » avec son verdict.
3. Laboratoire : Yaoundé colorée avec son contour réel, variable humidité du sol.
4. Laboratoire : la fiche de zone avec la courbe, la droite de Theil-Sen et le cycle saisonnier.
5. Laboratoire : un graphique agrandi.
6. Laboratoire : deux variables en double axe, avec la carte de corrélation.
7. L'assistant répondant à « How is soil moisture changing in Yaoundé? », la zone et les variables s'activant sur le globe.
8. La frise temporelle en lecture, montrant le glissement des couleurs (capture au milieu d'une transition).
