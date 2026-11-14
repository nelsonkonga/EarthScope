# EarthScope

Poste de travail d’observation de la Terre : globe Google plein écran, zones et variables fournies par le backend, temps, assistant.

Le blueprint d’implémentation est dans [docs/earthscope-specification.md](docs/earthscope-specification.md).

## Lancer l’interface

```bash
npm install
cp .env.example .env
npm run dev
```

Sans `VITE_GOOGLE_MAPS_API_KEY`, le globe affiche Cesium World Terrain et l’imagerie mondiale Cesium ion (jeton livré avec CesiumJS, ou `VITE_CESIUM_ION_TOKEN`). Renseigner la clé Map Tiles API, restreinte par referrer, recharge les tuiles 3D photoréalistes Google à la place. Le code Google reste dans l’application.

Le serveur de développement expose un jeu d’essai sur `/api/v1` (villes, séries linéaires). La barre d’état affiche alors « Jeu d'essai ». Ces valeurs ne sont pas des mesures.

```bash
npm test
npm run build
```
