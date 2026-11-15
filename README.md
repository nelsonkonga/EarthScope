# EarthScope

Poste de travail d’observation de la Terre : globe Google plein écran, zones et variables fournies par le backend, temps, assistant.

Le blueprint d’implémentation est dans [docs/earthscope-specification.md](docs/earthscope-specification.md). La spécification de l’interface livrée est dans [docs/earthscope-frontend.md](docs/earthscope-frontend.md).

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
