# Pipeline météo ETL/ELT — Cotonou

Projet de pipeline de données complet : extraction de la météo horaire via Open-Meteo, chargement idempotent dans PostgreSQL, transformations dbt et tests de qualité.

**Tableau de bord interactif :** [https://vaner0.github.io/etl-pipeline/](https://vaner0.github.io/etl-pipeline/)

**API météo en lecture seule :** [https://etl-pipeline-weather-api.onrender.com/api/weather/monthly](https://etl-pipeline-weather-api.onrender.com/api/weather/monthly)

**Code source :** [Vaner0/etl-pipeline](https://github.com/Vaner0/etl-pipeline)

> Le tableau de bord public interroge l’API en lecture seule hébergée sur Render, connectée à Neon. Le navigateur n’accède jamais directement à la base. En cas d’indisponibilité de l’API, le site affiche le dernier instantané publié. L’exécution quotidienne GitHub Actions nécessite encore la configuration du secret `DATABASE_URL`.

## Architecture

```text
Open-Meteo Archive API
        │ observations horaires de la veille
        ▼
Python ── validation + retry + upsert idempotent
        ▼
PostgreSQL (schéma source et staging)
        │
        ▼
dbt ── staging → daily intermediate → monthly mart
        │ tests de qualité
        ▼
Mart mensuel dbt dans Neon
        ▼
API FastAPI en lecture seule (Render)
        ▼
Tableau de bord interactif (GitHub Pages)
```

- **Extraction / chargement :** `extraction/extract_weather_cotonou.py`
- **Transformation et tests :** `dbt/models/` et `dbt/tests/`
- **Orchestration de démonstration :** Airflow dans GitHub Codespaces, `dags/weather_cotonou_etl.py`
- **Exécution planifiée :** GitHub Actions, chaque jour à 06:00 UTC (07:00 à Cotonou)
- **API publique en lecture seule :** `api/main.py`, hébergée sur Render, avec CORS limité
- **Restitution :** `site/`, publiée sur GitHub Pages à chaque changement de la branche `master`

## Résultats vérifiés

À la dernière validation locale : les tests Python, **3 modèles dbt** et **13 tests dbt** réussissent. Le fichier `.env` de développement pointe sur PostgreSQL local. En parallèle, la connexion Neon et l’exécution complète du DAG Airflow (extraction puis dbt) ont été validées dans Codespaces le 2 octobre 2026.

Le jeu de démonstration local est un instantané produit depuis le mart. Les valeurs mensuelles ne couvrent que les jours effectivement chargés ; ce ne sont pas des statistiques complètes des mois concernés.

## Exécuter en local

Prérequis : Python 3.12 et PostgreSQL accessible.

1. Installer les dépendances :

   ```powershell
   python -m venv venv
   .\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-api.txt
   ```

2. Copier `.env.example` vers `.env` et définir `DATABASE_URL` vers une base de développement. `ETL_SCHEMA` est facultatif et vaut `etl_pipeline` par défaut. Ne jamais committer `.env`.

3. Lancer l’extraction puis dbt :

   ```powershell
   .\venv\Scripts\python.exe extraction\extract_weather_cotonou.py
   .\venv\Scripts\python.exe scripts\run_dbt.py debug
   .\venv\Scripts\python.exe scripts\run_dbt.py build
   ```

4. Regénérer l’instantané destiné au tableau de bord :

   ```powershell
   .\venv\Scripts\python.exe scripts\export_portfolio_data.py
   ```

   Cette commande lit le mart mensuel, puis écrit `site/data/weather-monthly.json`, utilisé comme instantané de secours. Le JSON ne contient ni URL de connexion ni identifiant.

5. Lancer l’API et le site dans deux terminaux :

   ```powershell
   .\venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000
   .\venv\Scripts\python.exe -m http.server 8001 --directory site
   ```

   Pour l’essai local, ajouter `http://localhost:8001` à `CORS_ORIGINS` dans `.env`, puis ouvrir `http://localhost:8001`. L’API utilise `DATABASE_URL` pour lire le mart et expose sa documentation interactive sur `http://localhost:8000/docs`.

6. Vérifier les tests :

   ```powershell
   .\venv\Scripts\python.exe -m unittest discover -s tests -v
   ```

## Hébergement et secrets

### Tableau de bord GitHub Pages et API Render

Le workflow `.github/workflows/pages.yml` publie le contenu de `site/` sur les changements de `master` ou `main`. GitHub Pages est activé avec **GitHub Actions** comme source ; le site est publié à `https://vaner0.github.io/etl-pipeline/`.

L’API `etl-pipeline-weather-api` est déployée sur Render depuis le `render.yaml` et lit le mart dans Neon. Son URL est configurée dans `site/config.js` (`window.WEATHER_API_BASE_URL`). L’API est en lecture seule, limite CORS à l’origine du tableau de bord et ne renvoie pas la chaîne de connexion. La route `/health` sert au contrôle de disponibilité ; `/api/weather/monthly` renvoie les données. Le parcours public tableau de bord → API Render → Neon a été vérifié le 5 octobre 2026.

Le service Render gratuit peut se mettre en veille après une période d’inactivité ; le premier appel peut donc être plus lent. Le tableau de bord bascule alors explicitement sur l’instantané publié, sans le présenter comme une réponse de l’API.

### Exécution quotidienne

Le workflow `.github/workflows/daily-weather-pipeline.yml` est planifié à 06:00 UTC et peut également être lancé manuellement. Le secret de dépôt `DATABASE_URL` est configuré dans GitHub Actions ; le workflow échoue clairement s’il manque et ne retombe pas silencieusement sur une base locale. La première exécution manuelle a réussi le 5 octobre 2026 : extraction et chargement dans Neon, build et tests dbt, export d’un instantané de secours et republication du tableau de bord. L’API Render lit directement dans Neon le mart ainsi actualisé.

### Démo Airflow

Le Codespace est réservé à la démonstration de l’orchestration ; il ne remplace pas un ordonnanceur toujours actif. Configurer aussi le secret Codespaces `DATABASE_URL` avant de déclencher le DAG `weather_cotonou_etl`. Les identifiants générés par Airflow ne doivent pas être publiés.

## Statut

- ✅ Extraction réelle vers PostgreSQL local, relançable sans doublons.
- ✅ Modèles staging / intermédiaire journalier / mart mensuel ; 13 tests dbt validés localement.
- ✅ Tableau de bord interactif publié, API FastAPI déployée sur Render et connectée à Neon ; API, affichage live et instantané de secours vérifiés.
- ✅ Workflows CI, publication Pages et pipeline quotidien définis dans le dépôt.
- ✅ GitHub Pages activé et site public vérifié ; CI et workflow de publication réussis sur `master`.
- ✅ Secrets `DATABASE_URL` configurés sur Render et GitHub Actions ; première exécution complète du pipeline quotidien réussie.
- ✅ Pipeline quotidien planifié et tableau de bord republie après l’exécution.
- ⏳ Démarrer ensuite l’extension BigQuery / NYC Taxi prévue au cahier des charges.

## Sources

- [Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api)
- [Documentation dbt](https://docs.getdbt.com/)
- [Apache Airflow](https://airflow.apache.org/docs/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Render](https://render.com/docs/deploy-fastapi)
