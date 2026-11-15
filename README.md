# EarthScope

Poste de travail d’observation de la Terre : globe Google plein écran, zones et variables fournies par le backend, temps, assistant.

Le blueprint d’implémentation est dans [docs/earthscope-specification.md](docs/earthscope-specification.md). La spécification de l’interface livrée est dans [docs/earthscope-frontend.md](docs/earthscope-frontend.md).

## Pages

- `/` : page d’accueil **Terra Sense** (module `src/features/landing`, issu du brief Pexels). Anglais américain par défaut, français via le sélecteur ; thèmes clair, sombre et tamisé ; À propos ; assistant (même session que l’espace de visualisation). Textes dans `src/i18n/translations/{en,fr}.json`, parité vérifiée par `src/features/landing/translation-parity.test.ts`. Photos Pexels locales dans `public/images/`, déclarées dans `src/features/landing/photos.ts` et `public/images/PEXELS-SOURCES.md`.
- `/app` : le poste de travail (globe, variables, graphiques). Tous les graphiques s’agrandissent d’un clic.

Yaoundé est dessinée selon son contour réel : union des arrondissements Yaoundé I à VII (geoBoundaries gbOpen CMR ADM3, CC BY 4.0), dans `backend/data/yaounde_boundary.geojson`. La couleur reste la moyenne Giovanni de la maille ; elle glisse d’une valeur à l’autre sans inventer de mesure intermédiaire.

## Assistant et Gemini

L’assistant est hybride. Le moteur intégré choisit la zone et les variables, pilote le globe et calcule les tendances (Mann-Kendall, Theil-Sen). Si `GEMINI_API_KEY` est défini dans l’environnement du backend, Gemini (prompt repris de la branche `nasser`) rédige la réponse à partir de ces seuls résultats et cite ses sources. Sans clé, ou en cas d’erreur, la réponse du moteur intégré est conservée.

```bash
export GEMINI_API_KEY=...        # facultatif
export GEMINI_MODEL=gemini-2.5-flash   # facultatif
```

## Lancer l’interface

Le frontend lit `/api/v1` sur le backend Python. Les statistiques (Theil-Sen, Mann-Kendall, corrélations) sont calculées à chaque requête à partir des observations de `backend/data/`.

```bash
pip install -r backend/requirements.txt
cd backend && PYTHONPATH=. python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Dans un second terminal :

```bash
npm install
cp .env.example .env
npm run dev
```

Sans `VITE_GOOGLE_MAPS_API_KEY`, le globe affiche Cesium World Terrain et l’imagerie mondiale Cesium ion (jeton livré avec CesiumJS, ou `VITE_CESIUM_ION_TOKEN`). Renseigner la clé Map Tiles API, restreinte par referrer, recharge les tuiles 3D photoréalistes Google à la place. Le code Google reste dans l’application.

Le serveur de développement proxifie `/api/v1` vers `http://127.0.0.1:8000`. Yaoundé vient du CSV Giovanni (GLDAS/MODIS). Les autres zones sont des moyennes annuelles régionales.

```bash
npm test
npm run build
```

---

## Module IA : Sélection Intelligente des Variables (`src/variable_selector.py`)

Ce module agit comme le moteur sémantique de l'assistant. Il analyse les requêtes en langage naturel (Français et Anglais), détecte automatiquement la ville ou région du Cameroun concernée, filtre les négations et sélectionne jusqu'à **5 variables pertinentes** parmi les 11 disponibles (**Climat 2003–2026**, **SoilGrids 0–200 cm**, et **NASA Giovanni**).

### 1. Installation des dépendances IA
Si ce n'est pas déjà inclus dans `backend/requirements.txt`, installez les bibliothèques requises :
```bash
pip install -r requirements.txt
```

### 2. Installation du modèle neuronal entraîné (Hors-ligne)
Le poids du modèle entraîné dépasse la limite de 100 Mo de GitHub et est partagé séparément via Drive/Telegram (`modele_terrasense_final.zip`) :
1. Téléchargez et décompressez `modele_terrasense_final.zip`.
2. Placez le dossier obtenu dans `models/modele_terrasense_final/` à la racine du projet.
*(Note : Si ce dossier est absent, le script téléchargera automatiquement le modèle multilingue de base en ligne lors du premier lancement).*

### 3. Tester le sélecteur et l'intégrer au backend
Pour exécuter un test autonome en terminal :
```bash
python src/variable_selector.py
```

Exemple d'appel depuis le backend Python (`FastAPI`) :
```python
from src.variable_selector import analyser_requete

resultat = analyser_requete(
    "Analyser le risque d'inondation et l'argile à Bonabéri Douala", 
    top_k=5
)

print("Ville détectée :", resultat["localisation"]["ville"])
print("Fichiers CSV :", resultat["localisation"]["fichiers"])
print("Variables retenues :", resultat["variables_retenues"])
```
