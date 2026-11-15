# EarthScope — Spécification frontend

Document courant de l’interface. Il décrit le frontend tel qu’il est livré. Il prévaut sur le blueprint `docs/earthscope-specification.md` partout où les deux divergent, en particulier le fond de globe.

Le contrat HTTP reste celui du blueprint, livrable 5. Ce document ne le réécrit pas. Il dit seulement ce que l’écran en fait.

Légende :

- **[Décision]** choix fermé par l’implémentation.
- **[Écart]** point où ce document remplace une décision du blueprint.

Langue visible : français, catalogue `src/config/strings.fr.ts`. Identifiants, JSON et code : anglais.

---

## 1. Rôle de l’écran

EarthScope est un poste de travail. Le globe occupe toute la fenêtre. L’utilisateur explore la planète, choisit des zones publiées par le backend, active des variables, lit une date unique, et peut confier ces manipulations à un assistant.

Le frontend n’invente ni zone, ni variable, ni valeur, ni tendance. Il n’appelle aucun modèle de langage. Il ne sert pas la clé Google. Il ne dérive aucune mesure de l’imagerie.

Une seule date, `selectedDate` au format `YYYY-MM-DD`, pilote les symboles, la fiche, la frise, le repère des graphiques et le contexte envoyé à l’assistant. Aucun composant ne garde sa propre date.

---

## 2. Fond de globe

**[Décision D-BASEMAP]** **[Écart]** Le renderer est CesiumJS 1.125, encapsulé dans `src/features/globe/globeRenderer.ts`. C’est le seul fichier qui importe `cesium`. Pas de Resium.

`selectBasemap` dans `src/config/globe.ts` choisit le fond :

| Condition | Fond | Comportement |
|---|---|---|
| `VITE_GOOGLE_MAPS_API_KEY` non vide après trim | `google` | Tuiles 3D photoréalistes `https://tile.googleapis.com/v1/3dtiles/root.json`. Ellipsoïde masqué (`globe: false`). Atmosphère créée puis affichée seulement après le chargement du tileset, pour éviter un disque blanc. `RequestScheduler.requestsByServer["tile.googleapis.com:443"] = 18`. Crédits Google visibles (`showCreditsOnScreen: true`). |
| Clé absente ou blanche | `ion` | Cesium World Imagery (`ImageryLayer.fromWorldImagery`) et Cesium World Terrain (`Terrain.fromWorldTerrain`). Ellipsoïde et atmosphère Cesium restent. Jeton : `VITE_CESIUM_ION_TOKEN` s’il est renseigné, sinon le jeton livré avec CesiumJS. |

Les deux chemins restent dans l’application. Renseigner la clé et reconstruire suffit à revenir aux tuiles Google. La retirer suffit à revenir à Cesium ion. Aucun autre fond n’existe (pas de style cartoon, pas d’image fixe, pas de Sentinel).

La barre d’état affiche « Fond : Google · Données : EarthScope » ou « Fond : Cesium ion · Données : EarthScope ». Si `datasetVersion` commence par `fixture`, elle préfixe « Jeu d'essai ».

Hors des tuiles, et inchangé :

- Le ciel est celui de Cesium. Les positions d’étoiles ne sont pas celles d’Earth Web.
- Nuages animés et terminateur jour/nuit sont absents.
- Aucun label de pays ou de ville n’est réinjecté. Les seuls noms sur le globe sont les zones EarthScope.
- Aucune donnée EarthScope n’est calculée depuis le mesh ou l’imagerie.
- Pas de proxy ni de cache applicatif des tuiles au-delà des en-têtes HTTP du fournisseur.

Widgets Cesium natifs désactivés : animation, timeline, sélecteur de fond, géocodeur, bouton home, mode de scène, aide, plein écran, infobox, indicateur de sélection. `baseLayer: false`. `requestRenderMode: true`. Les crédits vont dans un conteneur dédié, visible, au-dessus de la barre d’état.

Si `navigator.deviceMemory` est indiqué et vaut 4 Go ou moins : `resolutionScale = 0.75` et FXAA coupé. Le fond ne change pas.

---

## 3. Technologies

| Rôle | Choix |
|---|---|
| UI | React 18, TypeScript strict, Vite 6 |
| Globe | CesiumJS 1.125, `vite-plugin-cesium` |
| Session | Zustand, un store |
| Cache serveur | TanStack Query v5 |
| Graphiques | SVG maison, `TrendChart` et `ComparisonChart` |
| Dialogues | élément `dialog` natif (`src/ui/Modal.tsx`) |
| HTTP | `fetch` + `AbortSignal`, base `VITE_API_BASE` ou même origine |
| Tests | Vitest sur le domaine pur et sur `selectBasemap` |

**[Écart]** Pas de Radix, pas de MSW, pas de Playwright dans le dépôt livré. Les tests couvrent le temps, le validateur d’actions et le choix de fond.

---

## 4. Découpage

1. **Coque** — `EarthScopeApp` monte les providers. `MainWorkspace` assemble les régions, les raccourcis et la géométrie.
2. **Session** — identifiants seulement. Jamais les séries, jamais la caméra.
3. **Cache** — catalogues, séries, couches, classements, comparaisons, session d’assistant.
4. **Globe impératif** — reçoit des symboles et des vols, émet les clics et l’échantillon caméra.
5. **Validateur** — `reduceAssistantActions`. Les clics passent par les actions du store, qui écrivent le même état.
6. **Clients** — `src/api/resources.ts` et `src/api/queries.ts`.

```text
src/
  main.tsx
  app/EarthScopeApp.tsx
  app/providers.tsx
  app/MainWorkspace.tsx
  config/globe.ts
  config/globe.test.ts
  config/strings.fr.ts
  domain/types.ts
  domain/actions.ts
  domain/actions.test.ts
  domain/time.ts
  domain/time.test.ts
  domain/markers.ts
  domain/colorScale.ts
  domain/format.ts
  state/workspaceStore.ts
  api/http.ts
  api/resources.ts
  api/queries.ts
  features/globe/GlobeViewport.tsx
  features/globe/globeRenderer.ts
  features/globe/globeApi.ts
  features/globe/cameraBridge.ts
  features/globe/GlobeControls.tsx
  features/zones/ZoneSearch.tsx
  features/zones/SelectedZonePanel.tsx
  features/variables/VariablePanel.tsx
  features/variables/VariableItem.tsx
  features/variables/ActiveVariableList.tsx
  features/variables/VariableLegend.tsx
  features/time/Timeline.tsx
  features/charts/TrendChart.tsx
  features/assistant/AIChatPanel.tsx
  features/assistant/ChatMessage.tsx
  features/workspace/LeftToolbar.tsx
  features/workspace/StatusBar.tsx
  ui/IconButton.tsx
  ui/icons.tsx
  ui/Modal.tsx
  styles/tokens.css
  styles/workspace.css
```

`app` n’importe pas Cesium et ne fetch pas. `config` ne contient ni ville ni mesure. `domain` est pur. `api` n’écrit pas le store.

**[Écart]** Le blueprint prévoyait des fichiers séparés (`zoneMarkers.ts`, `camera.ts`, un client par ressource, `SidePanel`, `ZoneList`, `BottomSheet`, `applyAssistantTurn.ts`). Le livré regroupe les symboles dans le renderer, la recherche et la liste dans `ZoneSearch`, le panneau dans `MainWorkspace`, et l’application des actions dans le store.

---

## 5. Arbre visible

```text
EarthScopeApp
  MainWorkspace
    GlobeViewport
      canvas focusable
      crédits Cesium
      bannière de chargement ou alerte + Réessayer
    ActiveVariableList
    LeftToolbar
    side-panel (un seul : variables | zones | assistant)
    SelectedZonePanel
      sections de séries, TrendChart
      classement ou comparaison
    GlobeControls
    VariableLegend
    Timeline
    StatusBar
    Modal d’aide ou de graphique agrandi
```

---

## 6. État de session

```ts
type WorkspaceState = {
  selectedZoneId: string | null
  activeVariableIds: string[]
  primaryVariableId: string | null
  selectedDate: string | null
  playback: "paused" | "playing"
  playbackSpeed: 1 | 2 | 4
  activePanel: "variables" | "zones" | "assistant" | null
  zoneCardOpen: boolean
  comparison: null | {
    variableId: string
    zoneIds: string[]
    mode: "rank" | "compare"
    metric: "changePerDecade" | "changeOverPeriod"
  }
  expandedChartVariableId: string | null
  notice: string | null
  assistantSessionId: string | null
  selectionNonce: number
}
```

`selectionNonce` augmente à chaque sélection de zone, y compris si l’identifiant ne change pas, pour relancer le vol.

Local, hors store : texte de recherche, brouillon du chat, survol d’un graphique, plein écran, aide ouverte, statut du fond, largeur étroite.

Dérivé, jamais stocké :

- secondaires = actives sauf la primaire ;
- étendue de la frise = union des `availableDateRange` ;
- pas = `defaultResolution` de la primaire, sinon de la première variable du catalogue ;
- valeur courante = observation de la série dont la date égale `selectedDate`.

Cache Query :

| Clé | Durée de fraîcheur |
|---|---|
| `['zones']` ou `['zones', q]` si recherche distante | 5 min |
| `['variables']` | 5 min |
| `['timeseries', zoneId, variableId, resolution, datasetVersion]` | infini |
| `['layer', variableId, date, datasetVersion]` | infini, `keepPreviousData` |
| `['ranking', variableId, metric]` | infini |
| `['comparison', variableId, zoneIds]` | infini |
| `['assistant', sessionId]` | défaut Query, `retry: false` |

### Activer ou retirer une variable

La variable entre en queue. La première active devient primaire. Si la primaire est retirée, la suivante prend sa place. `playback` passe à `paused`. La couche demandée est celle de la primaire à la date courante. Les secondaires ne demandent pas de couche globale. Une série part pour chaque variable active disponible sur la zone ouverte.

### Changer de zone

`zoneCardOpen` passe à vrai. `comparison` est conservée. La caméra vole vers la zone. Les séries de la zone précédente ne sont plus affichées. La couche globale ne dépend pas de la zone et n’est pas rechargée.

Fermer la fiche laisse la zone sélectionnée.

### Changer de date

Les séries déjà chargées ne sont pas redemandées. La couche est demandée après 150 ms hors lecture. Pendant la lecture, chaque pas part tout de suite et la couche précédente reste affichée (`updating`) jusqu’à l’arrivée de la suivante. Le pas suivant est préchargé.

### Tour d’assistant

Au plus dix actions. Le validateur rejette les types inconnus, les identifiants absents du catalogue chargé, une primaire qui n’est pas active, une date hors plage de la primaire, une comparaison hors de 2 à 6 zones. `SET_DATE` est accroché au pas de la primaire, puis appliqué. Le lot est écrit une fois. Le vol ne part que si la zone sélectionnée a changé.

---

## 7. Chargement

Au démarrage, `GET /api/v1/zones` et `GET /api/v1/variables` partent en parallèle du fond. La date initiale est le maximum des `availableDateRange.end`. Catalogue vide : la frise est désactivée.

| Moment | Appel |
|---|---|
| Variable primaire et date | `GET /layers?variableId&date` |
| Fiche ouverte | `GET /timeseries` par variable active disponible sur la zone |
| Lecture | préchargement de la couche du pas suivant |
| Catalogue incomplet | `GET /zones?q=` avec debounce 200 ms |
| Catalogue complet | filtre local, accent-insensible, sur nom, pays et alias |
| Classement | `GET /rankings` |
| Comparaison | `GET /comparisons` |
| Assistant | `POST /assistant/sessions`, puis `POST .../messages` avec le contexte, `GET` pour relire |

Une erreur d’API n’efface pas le dernier jeu affiché. Le panneau concerné montre la phrase française et Réessayer. Aucun code HTTP n’est montré. Une couche en échec laisse les symboles précédents et affiche « Mise à jour impossible. »

Le mode `raster-tiles` est refusé à l’écran : « Couche non prise en charge. » Les symboles ne sont pas inventés à la place.

---

## 8. Caméra et gestes

Vue initiale : longitude 0, latitude 0, hauteur 16 000 km, nord en haut. La boussole y revient. Ce n’est pas un simple redressement de cap.

| Constante | Valeur |
|---|---|
| Zoom minimum | 80 m |
| Zoom maximum | 40 000 km |
| Vol vers une zone | 80 km, inclinaison −45°, 0,8 s |
| Noms visibles | hauteur caméra &lt; 2 500 km, ou zone sélectionnée |
| Disque au sol | hauteur caméra &lt; 400 km, rayon 40 km |

Gestes : glisser gauche pour tourner, glisser droit ou Ctrl+glisser pour incliner, molette et pincement pour zoomer vers le curseur. Double-clic : zoom d’environ 35 % de la hauteur, sans sélectionner. Clic sur un marqueur : sélection. Clic ailleurs : la sélection ne change pas, et la barre d’état montre quatre secondes « Cet endroit n’est pas une zone du prototype. »

`prefers-reduced-motion` : vol de durée 0, retour initial immédiat. La lecture temporelle continue.

La caméra n’est pas une donnée serveur. Aucune action d’assistant ne vole vers une coordonnée libre.

Le pont caméra (`cameraBridge`) est local au module globe. La barre d’état lit les coordonnées sous le curseur, sinon le point visé, l’altitude (km au-dessus de 10 km, mètres en dessous) et une échelle arrondie à 1, 2 ou 5 × 10ⁿ. Un mouvement de caméra ne rerend pas la fiche ni le chat.

---

## 9. Symboles

Toutes les zones du catalogue ont un marqueur, y compris hors données. Les marqueurs sont une `BillboardCollection` plus une `LabelCollection`, pas un composant React par ville. L’image est un canvas 64×64.

Sans observation exploitable, le disque est blanc. Avec une valeur mesurée ou estimée sur la primaire, le remplissage vient de `colorScale` de la variable, ramené à `displayScale` de la couche. Une valeur manquante ne colore pas le marqueur et n’est pas interpolée.

Les secondaires sont des anneaux concentriques dans `variable.color`. Une valeur estimée a un contour pointillé. La zone sélectionnée a un anneau `--accent` (`#8eabc4`).

Si une comparaison ou un classement est actif, les zones hors liste sont atténuées et les zones listées sont accentuées.

Le disque au sol n’apparaît que pour une observation colorable, sous 400 km. Sur Google il est `CLAMP_TO_3D_TILE` / `CESIUM_3D_TILE`. Sur Cesium ion il est `CLAMP_TO_GROUND` / `TERRAIN`. La légende dit : « Le disque localise la zone. Il ne représente pas l’étendue du phénomène. » et « Couleur = valeur au point de la zone, pas un champ continu. »

---

## 10. Disposition

Le globe est le fond, bord à bord. Le chrome flotte. Fond de panneau `--panel` à 88 % (`rgba(10, 14, 18, 0.88)`), texte `--ink` `#ebe7df`, secondaire `--muted`, filet `--line` blanc à 12 %, accent unique `--accent`. Les couleurs de variables viennent du backend. `--zone-1` à `--zone-6` ne servent que dans le graphique de comparaison.

Rayon 8 px. Icônes en traits, 20 px. Focus : anneau 2 px accent. Pas d’ombre portée large. Police : Segoe UI, Helvetica Neue, Arial, 14 px.

| Élément | ≥ 1280 px | 1024–1279 px | ≤ 1023 px |
|---|---|---|---|
| Barre d’outils | 48 px, verticale, marge 16, haut gauche | identique | horizontale, pleine largeur, au-dessus de la barre d’état |
| Panneau | 360 × fluide, à droite de la barre | 320 | feuille entre les pastilles et la frise ; la fiche ouverte le masque |
| Fiche | 340, haut droite | 320 | même feuille |
| Contrôles globe | colonne, bord droit | identique | rangée, bas droite |
| Frise | centrée, au-dessus de la barre d’état | identique | à gauche des contrôles |
| Légende | 240 px, bas gauche ; décalée si un panneau est ouvert | identique | au-dessus de la frise |
| Pastilles | haut centre | identique | sous le bord haut, défilables |
| Barre d’état | 32 px | 32 | altitude masquée |

**[Écart]** Le blueprint décrivait deux feuilles (70 % et 85 %) et une légende repliée sous 768 px. Le livré a un seul seuil, 1023 px. Les panneaux ne se redimensionnent pas à la souris.

Plein écran : l’élément `.workspace`. Sont masqués la barre d’outils, le panneau, la fiche, la frise, les pastilles et la légende. Restent le globe, les contrôles et la barre d’état. L’état est conservé au retour.

Une ligne de 2 px en haut signale le chargement des catalogues.

---

## 11. Panneaux

**Variables.** Titre « Variables ». « Tout effacer » est désactivé si rien n’est actif. Thèmes triés par `order`, puis « Autres ». Chaque ligne : case, pastille, nom, unité. Si la zone ouverte ne couvre pas la variable, la ligne reste cochable et porte « Pas de données ici ». La description est en texte secondaire.

**Zones.** Champ « Rechercher une zone ». Liste nom et pays. La zone courante a `aria-current`. Vide : « Aucune zone du prototype ne correspond. » Catalogue vide : « Aucune zone n'est publiée pour le moment. » La recherche ne propose jamais un lieu hors catalogue. `/` ouvre ce panneau et focalise le champ.

**Pastilles.** Une par variable active, dans l’ordre d’activation. Clic : la rendre primaire. Croix : la retirer. La dernière retirée rend le globe neutre.

**Légende.** Visible seulement avec une primaire. Rampe, minimum, maximum, unité, mention de point. Les secondaires sont rappelés par leur pastille et leur nom. « Mise à jour… » pendant un refetch. « Mise à jour impossible. » en erreur.

**Fiche.** Nom, pays, coordonnées `3,867° N, 11,517° E` (hémisphères N/S/E/O, six décimales au plus, virgule, zéros inutiles retirés). Mention « Valeurs du jeu d'essai, pas des mesures. » quand le catalogue est un jeu d’essai. Sans variable : « Choisissez une variable pour voir son évolution. » Sans couverture : « Pas de données de {variable} pour {zone}. » Sans série : phrase et Réessayer, pas de graphique vide.

Pour chaque variable disponible : valeur formatée `fr-FR` et unité, statut mesurée, estimée ou indisponible, phrase de tendance, courbe. « Indisponible » si la valeur est nulle. « Tendance non calculée » si la direction est `insufficient`.

**Graphique.** Trait de 1,5 px dans la couleur de la variable. Trou pour une observation manquante, jamais un zéro. Point creux pour une estimation. Tendance en pointillés seulement si le serveur fournit une direction autre que `insufficient`. Verticale d’accent sur `selectedDate`. Survol : date, valeur, statut. « Agrandir » ouvre le même graphique dans un dialogue, sans recalculer la tendance.

**Classement et comparaison.** Affichés dans la fiche, pas sur un second globe. Le classement reprend l’ordre et les variations du serveur, de la plus forte à la plus faible. La comparaison trace jusqu’à six séries, couleurs `--zone-1` à `--zone-6`. « Effacer la comparaison » vide cet état. Les surbrillances de marqueurs suivent les zones du classement ou de la comparaison.

**Frise.** Libellé de date. Curseur sur les pas de la résolution. Lecture, pause, pas arrière, pas avant. Vitesses 1×, 2×, 4× : un pas toutes les 800, 400 ou 200 ms. Butées désactivées. Arrivée en fin de période : pause. Espace lance ou arrête, sauf depuis un bouton.

**Assistant.** Vide : « Posez une question sur les zones et les variables du prototype. » puis les amorces renvoyées par la session, ou les cinq phrases de repli du catalogue. Un envoi à la fois. En cours : « Analyse en cours », saisie bloquée. Erreur : « L'assistant n'a pas pu répondre. » et Réessayer, qui renvoie le même texte. Session expirée : « Conversation expirée. » et « Nouvelle conversation ».

Sous une réponse, « J'ai sélectionné : {noms}. » est construit depuis les actions appliquées (zones et variables activées), pas depuis la prose. Les rejets sont en texte secondaire : « Ignoré : zone inconnue. », et de même pour action inconnue, trop d’actions, variable inconnue, date hors couverture, aucune variable active, variable non active, comparaison de 2 à 6 zones.

L’identifiant de session est gardé dans `sessionStorage` (`earthscope.assistantSession`). Le contexte envoyé est la zone, les variables actives, la primaire et la date.

---

## 12. Clavier

| Touche | Effet |
|---|---|
| 1, 2, 3 | Ouvrir ou fermer Variables, Zones, Assistant |
| Échap | Aide, puis graphique agrandi, puis panneau, puis fiche |
| / | Recherche de zone |
| Espace | Lecture ou pause |
| Flèches | Déplacer le globe |
| Maj + gauche ou droite | Tourner |
| + et − | Zoom |
| ? | Raccourcis |

Les touches de navigation du globe ne partent pas quand le focus est dans un champ, un panneau, la fiche, la frise ou un dialogue. Le titre accessible de la page est « EarthScope ». Le canvas a pour nom « Globe ».

---

## 13. Échecs du globe

| Cas | Phrase |
|---|---|
| WebGL absent | « EarthScope a besoin de WebGL 2 pour afficher le globe. » Pas de bouton Réessayer. |
| Fond ion en erreur | « Le fond Cesium ion n'a pas pu être chargé. » Réessayer recrée le viewer. |
| Tuiles Google en erreur | « Le globe Google Earth n'a pas pu être chargé. » Réessayer. |
| Clé absente alors que le chemin Google est pris | « La clé Map Tiles API est absente. Le globe Google Earth ne peut pas être chargé. » |

Le chemin normal sans clé ne prend pas cette dernière phrase : il charge Cesium ion. Le catalogue et les panneaux restent utilisables si le globe échoue, et l’inverse.

---

## 14. Configuration

| Variable | Effet |
|---|---|
| `VITE_GOOGLE_MAPS_API_KEY` | Non vide : tuiles Google. Vide : Cesium ion. |
| `VITE_CESIUM_ION_TOKEN` | Facultatif. Ignoré si la clé Google est présente. |
| `VITE_API_BASE` | Préfixe des appels. Vide : même origine, `/api/v1`. |

Ces variables sont compilées dans le JavaScript du navigateur. Ce ne sont pas des secrets de serveur.

---

## 15. Hors de cette interface

Street View, imagerie historique Google, géocodage mondial, labels Earth Web, nuages, terminateur, second globe, couche raster tant que le serveur n’en envoie pas une que l’écran sache afficher, action « voler vers une coordonnée arbitraire ».
