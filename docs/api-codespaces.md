# API Spectrum sur GitHub Codespaces

## Préparer la démonstration

1. Créez ou reprenez un Codespace sur la branche `master` du dépôt. La configuration installe les dépendances verrouillées et lance FastAPI sur `0.0.0.0:7860` à chaque démarrage.
2. Dans l’onglet **Ports**, ouvrez le menu du port **7860** et sélectionnez **Port Visibility → Public**. En ligne de commande, utilisez `gh codespace ports visibility 7860:public -c NOM_DU_CODESPACE`.
3. Copiez l’adresse HTTPS du port. Elle prend la forme `https://NOM_DU_CODESPACE-7860.app.github.dev`. Ouvrez `/health` et `/docs` dans une fenêtre privée pour vérifier l’accès sans session GitHub.

Avant la démonstration, assurez-vous que le Codespace tourne et que le port est public. GitHub peut remettre le port en mode privé au redémarrage. Si `/health` renvoie une erreur `502` après le démarrage, lancez l’API depuis la racine du dépôt dans le terminal du Codespace et consultez son journal.

```sh
nohup .venv/bin/python -m uvicorn app_api:app --app-dir src --host 0.0.0.0 --port 7860 \
  </dev/null >/tmp/spectrum-api.log 2>&1 &
tail /tmp/spectrum-api.log
```

## Endpoints

| Endpoint | Description |
| --- | --- |
| `GET /docs` | Documentation Swagger et exécution de requêtes depuis le navigateur. |
| `GET /openapi.json` | Schéma OpenAPI avec les champs de requête et de réponse. |
| `GET /health` | Renvoie `status: ok` et la version du modèle chargé. HTTP `503` si le modèle est indisponible. |
| `POST /predict_batch` | Prédit le sentiment d’un lot de commentaires et renvoie les résultats dans l’ordre de la requête, un récapitulatif et le temps d’inférence. |

Remplacez `NOM_DU_CODESPACE` par le nom affiché dans GitHub Codespaces, ou utilisez directement l’adresse copiée dans l’onglet **Ports**.

```sh
API_URL='https://NOM_DU_CODESPACE-7860.app.github.dev'

curl --fail-with-body "$API_URL/health"

curl --fail-with-body "$API_URL/predict_batch" \
  -H 'Content-Type: application/json' \
  -d '{"comments":[{"id":"c1","text":"I love this tutorial!"},{"id":"c2","text":"This was frustrating and awful."}]}'
```

Le lot doit contenir de 1 à 50 commentaires, chacun avec un `id` unique de 1 à 128 caractères et un `text` de 1 à 5 000 caractères, après suppression des espaces aux extrémités. Une requête invalide renvoie HTTP `422`. Les étiquettes sont `-1` (négatif), `0` (neutre) et `1` (positif). Les commentaires vidés par le prétraitement ont le statut `skipped` et sont exclus des pourcentages.

## Utiliser l’extension pendant la démonstration

Générez le ZIP avec l’adresse publique vérifiée, puis extrayez-le et chargez le dossier dans `chrome://extensions` via **Charger l’extension non empaquetée**.

```sh
uv run python scripts/package_extension.py --api-url "$API_URL"
```
