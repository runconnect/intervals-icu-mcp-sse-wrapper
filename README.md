# Intervals.icu MCP HTTP Wrapper

Serveur **FastAPI + MCP** pour exposer des outils Intervals.icu à des assistants compatibles MCP via une URL distante, avec endpoints HTTP de debug, outils analytiques orientés endurance, et sécurisation optionnelle par clé API sur `/mcp`.

Ce projet s'appuie sur l'API ouverte d'Intervals.icu, qui permet l'accès aux activités, données wellness, workouts planifiés et autres ressources via API key ou OAuth 2.0. L'exposition automatique d'endpoints FastAPI comme outils MCP repose sur `fastapi_mcp`, qui monte un serveur MCP HTTP sur un chemin tel que `/mcp`. [intervals](https://www.intervals.icu/features/open-api/)

## Fonctionnalités

- Expose des endpoints FastAPI comme **tools MCP** via `FastApiMCP`. [raw.githubusercontent](https://raw.githubusercontent.com/tadata-org/fastapi_mcp/main/README.md)
- Fournit des routes HTTP exploitables en direct pour le debug et les tests locaux.
- Centralise l'accès à Intervals.icu avec des réponses plus structurées que le JSON brut.
- Ajoute des outils analytiques utiles pour la course à pied et le cyclisme, comme les histogrammes, les best efforts, les intervalles, les streams et le volume hebdomadaire.
- Permet de protéger l'accès distant au serveur MCP avec une clé API HTTP côté reverse proxy/app.

## Cas d'usage

Ce wrapper est adapté à un usage avec Perplexity, Claude Desktop, Cursor, Cline, ou tout client capable de consommer une URL MCP distante. Le pattern FastAPI-MCP consiste à monter le serveur MCP directement sur l'application FastAPI, généralement sur `/mcp`. [medium](https://medium.com/@miki_45906/how-to-build-mcp-server-in-python-using-fastapi-d3efbcb3da3a)

Exemples de besoins couverts :

- Interroger les activités récentes et leur résumé structuré.
- Récupérer les données wellness et les métriques de charge/forme.
- Explorer les intervals, streams et best efforts d'une activité.
- Consolider le volume de course par semaine.
- Donner à un assistant IA un accès contrôlé à un compte Intervals.icu personnel.

## Architecture

La base du projet repose sur une application FastAPI classique enrichie par `FastApiMCP`, qui transforme certains endpoints sélectionnés en outils MCP disponibles à distance. Le serveur MCP est ensuite monté sur `/mcp`, ce qui correspond au mode d'intégration recommandé par la documentation FastAPI-MCP. [raw.githubusercontent](https://raw.githubusercontent.com/tadata-org/fastapi_mcp/main/README.md)

Structure type :

```text
app/
├── wrapper_server.py
├── core/
│   ├── client.py
│   └── utils.py
└── routes/
    ├── activities.py
    ├── athlete.py
    ├── plans.py
    └── wellness.py
```

### Organisation logique

- `core/client.py` : appels HTTP vers l'API Intervals.icu.
- `core/utils.py` : fonctions utilitaires de parsing, filtrage et calculs.
- `routes/activities.py` : activités, détails, recherche locale, événements.
- `routes/athlete.py` : profil athlète, résumé fitness.
- `routes/plans.py` : workouts planifiés et filtres.
- `routes/wellness.py` : wellness journalier et période.
- `wrapper_server.py` : assemblage FastAPI, sécurité, exposition MCP.

## Outils exposés

Les noms exacts peuvent évoluer, mais l'instance MCP expose typiquement les opérations suivantes lorsque `include_operations` les référence dans `FastApiMCP` :

| Domaine | Outils typiques |
|---|---|
| Athlete | `get_athlete_profile`, `get_fitness_summary` |
| Activities | `get_activities`, `get_activity_details`, `search_activities_local` |
| Wellness | `get_wellness`, `get_wellness_for_date` |
| Plans | `get_plan_workouts_filtered` |
| Analyse | `get_activity_streams`, `get_activity_intervals`, `get_best_efforts`, `get_best_efforts_debug`, `get_power_histogram`, `get_hr_histogram`, `get_pace_histogram`, `get_running_volume_by_week` |
| Calendrier | `get_events` |

## Prérequis

- Python 3.11+ recommandé.
- Un compte Intervals.icu avec API key personnelle, car l'API supporte l'authentification par clé API pour les appels personnels. [intervals](https://www.intervals.icu/features/open-api/)
- Un identifiant athlète Intervals.icu.
- Un client MCP ou un reverse proxy HTTPS si exposition distante.

## Variables d'environnement

Exemple minimal :

```env
INTERVALS_API_KEY=your_intervals_api_key
INTERVALS_ATHLETE_ID=your_athlete_id
MCP_API_KEY=your_remote_mcp_api_key
```

### Variables principales

| Variable | Rôle |
|---|---|
| `INTERVALS_API_KEY` | Clé API Intervals.icu utilisée par le wrapper pour appeler l'API. |
| `INTERVALS_ATHLETE_ID` | Identifiant de l'athlète cible sur Intervals.icu. |
| `MCP_API_KEY` | Clé API attendue par ton serveur pour autoriser l'accès au endpoint MCP distant. |

## Installation

```bash
git clone <your-repo-url>
cd <your-repo>
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Lancement local

Exemple avec Uvicorn :

```bash
uvicorn wrapper_server:app --host 0.0.0.0 --port 8000
```

Si ton fichier est dans `app/`, adapte la commande selon ton point d'entrée réel, par exemple :

```bash
uvicorn app.wrapper_server:app --host 0.0.0.0 --port 8000
```

Une fois démarré, le serveur MCP est généralement disponible sur :

```text
http://localhost:8000/mcp
```

Le montage d'un serveur MCP sur `/mcp` correspond au comportement standard documenté par `fastapi_mcp`. [medium](https://medium.com/@miki_45906/how-to-build-mcp-server-in-python-using-fastapi-d3efbcb3da3a)

## Sécurisation de l'accès distant

Le projet peut protéger `/mcp` par clé API HTTP côté application FastAPI. Cette approche consiste à exiger un header tel que `X-API-Key` ou un bearer token avant d'autoriser les requêtes entrantes vers le endpoint MCP.

Exemple de principe :

- Le serveur lit `MCP_API_KEY` depuis l'environnement.
- Le client MCP distant envoie une clé API dans le header HTTP.
- Toute requête sans clé valide reçoit `401 Unauthorized`.

Cela est particulièrement utile lorsqu'un connecteur distant Perplexity est configuré sur une URL publique telle que `https://mcp.runconnect.me/mcp`.

## Exemple Docker Compose

```yaml
services:
  intervals-icu-mcp:
    build: .
    ports:
      - "8000:8000"
    environment:
      INTERVALS_API_KEY: "${INTERVALS_API_KEY}"
      INTERVALS_ATHLETE_ID: "${INTERVALS_ATHLETE_ID}"
      MCP_API_KEY: "${MCP_API_KEY}"
```

Docker Compose utilise l'interpolation de variables avec la syntaxe `${VAR}` plutôt que `{VAR}`. [docs.docker](https://docs.docker.com/reference/compose-file/interpolation/)

## Exemple de test HTTP

### Test du healthcheck

```bash
curl http://localhost:8000/health
```

### Test d'initialisation MCP sans authentification

```bash
curl -i -X POST "http://localhost:8000/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {
        "name": "curl",
        "version": "1.0"
      }
    }
  }'
```

### Test d'initialisation MCP avec clé API

```bash
curl -i -X POST "https://mcp.runconnect.me/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: ${MCP_API_KEY}" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {
        "name": "curl",
        "version": "1.0"
      }
    }
  }'
```

Si l'authentification est correcte, la réponse doit être `200 OK` avec un payload JSON-RPC `initialize` valide.

## Intégration Perplexity

Perplexity permet l'ajout de connecteurs MCP distants avec authentification configurée côté connecteur. Dans ce projet, la configuration cible est généralement la suivante : [perplexity](https://www.perplexity.ai/help-center/en/articles/13915507-adding-custom-remote-connectors)

- URL du serveur : `https://mcp.runconnect.me/mcp`
- Type d'auth : API Key
- Header attendu par le serveur : `X-API-Key` ou, selon la stratégie retenue, `Authorization: Bearer <clé>`
- Valeur : la même clé que `MCP_API_KEY`

Une stratégie robuste côté serveur consiste à accepter à la fois `X-API-Key` et `Authorization: Bearer`, afin de rester compatible avec les différences d'implémentation entre clients MCP distants.

## Endpoints HTTP utiles

En plus de `/mcp`, le projet expose généralement :

- `/` : informations racine
- `/health` : vérification de disponibilité
- `/activities`
- `/activities/details`
- `/activities/search`
- `/events`
- `/athlete/profile`
- `/athlete/fitness`
- `/wellness`
- `/plan-workouts/filtered`
- `/activity-streams`
- `/activity-intervals`
- `/best-efforts`
- `/power-histogram`
- `/hr-histogram`
- `/pace-histogram`
- `/running-volume-by-week`

## Différences avec le projet d'eddmann

Le projet d'eddmann propose un serveur MCP Intervals.icu riche en outils, orienté intégration MCP native. Cette implémentation suit une approche différente : [lobehub](https://lobehub.com/mcp/eddmann-intervals-icu-mcp?activeTab=score)

- elle s'appuie sur **FastAPI** pour garder des endpoints HTTP testables directement ;
- elle utilise **FastApiMCP** pour exposer ces endpoints comme tools MCP ;
- elle privilégie des réponses structurées adaptées à des usages personnels course/cyclisme ;
- elle facilite le debug opérationnel via des routes HTTP explicites.

## Débogage

### Le endpoint `/mcp` renvoie 500

Cause fréquente : `MCP_API_KEY` absente dans le conteneur. Vérifier avec :

```bash
docker exec -it <container_name> printenv MCP_API_KEY
```

### Le endpoint `/mcp` renvoie 401

Causes fréquentes :

- clé différente entre le client et le serveur ;
- variable Docker incorrecte ;
- valeur injectée littéralement comme `{MCP_API_KEY}` au lieu de `${MCP_API_KEY}` ou de la vraie valeur. [docs.docker](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)

### L'authentification fonctionne avec curl mais pas avec Perplexity

Cause probable : différence de format d'auth transmis par le connecteur distant. Dans ce cas, il est recommandé d'accepter `X-API-Key` et `Authorization: Bearer` côté middleware.

## Feuille de route possible

- Ajouter plus d'outils analytiques Intervals.icu.
- Enrichir les réponses `athlete` et `wellness`.
- Ajouter des tests automatisés pour les endpoints critiques.
- Générer une documentation OpenAPI/MCP plus détaillée.
- Ajouter une authentification plus fine par chemin ou par rôle.

## Références

- FastAPI-MCP : exposition automatique des endpoints FastAPI comme outils MCP. [raw.githubusercontent](https://raw.githubusercontent.com/tadata-org/fastapi_mcp/main/README.md)
- Documentation d'intégration MCP distante Perplexity. [perplexity](https://www.perplexity.ai/help-center/en/articles/13915507-adding-custom-remote-connectors)
- API ouverte Intervals.icu avec support API key et OAuth 2.0. [intervals](https://www.intervals.icu/features/open-api/)