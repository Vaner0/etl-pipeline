# Pipeline météo ETL/ELT — Cotonou

Démo portfolio d’un pipeline de données complet : extraction de la météo horaire via Open-Meteo, chargement idempotent dans PostgreSQL, transformations dbt et tests de qualité.

**Démo interactive (URL après activation de GitHub Pages) :** [https://vaner0.github.io/etl-pipeline/](https://vaner0.github.io/etl-pipeline/)

**Code source :** [Vaner0/etl-pipeline](https://github.com/Vaner0/etl-pipeline)

> Le tableau de bord est interactif et interroge une API en lecture seule hébergée sur Render, connectée à Neon. Le navigateur n’accède jamais directement à la base. Le pipeline met les données à jour chaque jour ; en cas d’indisponibilité de l’API, la démo peut afficher le dernier instantané publié. L’API, Neon et GitHub Pages restent à déployer/configurer avant que le lien public soit opérationnel.

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
- **Restitution :** `site/`, publiée sur GitHub Pages après activation de Pages dans les paramètres du dépôt

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

Le workflow `.github/workflows/pages.yml` publie le contenu de `site/` sur les changements de `master` ou `main`. Dans **Settings → Pages**, choisir **GitHub Actions** comme source. Après fusion du code sur la branche par défaut et réussite du workflow, l’URL sera `https://vaner0.github.io/etl-pipeline/`.

Créer le service Render à partir du `render.yaml` à la racine du dépôt. Ajouter le secret `DATABASE_URL` avec la chaîne Neon, puis déployer. Une fois l’URL `onrender.com` connue, la renseigner dans `site/config.js` (`window.WEATHER_API_BASE_URL`) et publier le site. L’API est en lecture seule, limite CORS à l’origine du tableau de bord, et ne renvoie pas la chaîne de connexion. La route `/health` sert au contrôle de disponibilité ; `/api/weather/monthly` renvoie les données.

Le service Render gratuit peut se mettre en veille après une période d’inactivité ; le premier appel peut donc être plus lent. Le tableau de bord bascule alors explicitement sur l’instantané publié, sans le présenter comme une réponse de l’API.

### Exécution quotidienne

Le workflow `.github/workflows/daily-weather-pipeline.yml` est planifié à 06:00 UTC et peut également être lancé manuellement. Avant son premier succès, définir dans les paramètres GitHub **Settings → Secrets and variables → Actions** le secret de dépôt `DATABASE_URL` avec une chaîne PostgreSQL valide pour Neon. Le workflow échoue clairement si ce secret manque ; il ne retombe pas silencieusement sur une base locale. Après l’extraction et le build dbt, il exporte un instantané de secours et republie le tableau de bord. L’API Render lit directement dans Neon le mart ainsi actualisé.

### Démo Airflow

Le Codespace est réservé à la démonstration de l’orchestration ; il ne remplace pas un ordonnanceur toujours actif. Configurer aussi le secret Codespaces `DATABASE_URL` avant de déclencher le DAG `weather_cotonou_etl`. Les identifiants générés par Airflow ne doivent pas être publiés.

## Statut

- ✅ Extraction réelle vers PostgreSQL local, relançable sans doublons.
- ✅ Modèles staging / intermédiaire journalier / mart mensuel ; 13 tests dbt validés localement.
- ✅ Tableau de bord interactif, API FastAPI en lecture seule et instantané de secours définis ; validation locale API et déploiements Render/GitHub Pages à effectuer.
- ✅ Workflows CI, publication Pages et pipeline quotidien définis dans le dépôt.
- ✅ Neon : connexion validée depuis Codespaces ; le secret GitHub Actions et le secret Render restent à configurer.
- ⏳ Déployer l’API Render, ajouter son URL dans `site/config.js`, activer GitHub Pages et vérifier les URL publiques.
- ⏳ Activer GitHub Pages, fusionner les workflows sur la branche par défaut et vérifier les URL publiées.
- ⏳ Démarrer ensuite l’extension BigQuery / NYC Taxi prévue au cahier des charges.

## Sources

- [Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api)
- [Documentation dbt](https://docs.getdbt.com/)
- [Apache Airflow](https://airflow.apache.org/docs/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Render](https://render.com/docs/deploy-fastapi)
