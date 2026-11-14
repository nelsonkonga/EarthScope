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

## Déployer sur Vercel

Le frontend est le build Vite (`dist`). L’API d’essai `/api/v1` est une fonction Vercel (`api/index.ts`) : le middleware Vite ne tourne pas en production. Les sessions de l’assistant portent un identifiant autonome, donc une autre instance peut répondre sans mémoire partagée. L’historique d’une conversation n’est pas conservé après rechargement.

Dans le projet Vercel, ajouter la variable de **build** `VITE_GOOGLE_MAPS_API_KEY` (clé Map Tiles API). Les referrers autorisés doivent inclure le domaine du déploiement. Sans cette variable, le fond étoilé reste visible et le globe indique qu’il ne peut pas être chargé.

```bash
npx vercel deploy --prod
```
