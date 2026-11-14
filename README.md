# EarthScope

Poste de travail d’observation de la Terre : globe Google plein écran, zones et variables fournies par le backend, temps, assistant.

Le blueprint d’implémentation est dans [docs/earthscope-specification.md](docs/earthscope-specification.md).

## Lancer l’interface

```bash
npm install
cp .env.example .env
npm run dev
```

Renseigner `VITE_GOOGLE_MAPS_API_KEY` dans `.env` avec une clé Map Tiles API restreinte par referrer. Sans cette clé, le fond étoilé reste visible et un message indique que le globe Google Earth ne peut pas être chargé. Aucune imagerie de remplacement n’est affichée.

Le serveur de développement expose un jeu d’essai sur `/api/v1` (villes, séries linéaires). La barre d’état affiche alors « Jeu d'essai ». Ces valeurs ne sont pas des mesures.

```bash
npm test
npm run build
```
