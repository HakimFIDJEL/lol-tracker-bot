# LoL Tracker Bot

Surveille toutes les minutes le dernier match d'un joueur Riot et publie un résumé sur Discord. Le bot tourne en permanence, sans port entrant et sans Sablier.

## Développement local

Copier `.env.example` vers `.env`, puis renseigner les accès Riot et Discord et les identifiants du joueur et du salon. Le Compose local force `ENVIRONMENT=testing` : il se connecte aux services mais journalise les rapports sans les envoyer. Aucun fichier `.env` n'est chargé implicitement par Python.

```sh
make up
make logs
make down
```

Le code est monté dans le conteneur ; le redémarrer après modification. `make check` construit une image de développement et lance Ruff, Mypy strict et les tests sans réseau ni accès réels. Cette commande ne nécessite pas de `.env`.

## Git Flow et CI

`main` porte la production et `develop` l'intégration. Initialiser Git Flow comme décrit dans `AGENTS.md`. Utiliser `git flow feature start <nom>` pour développer ; intégrer ensuite dans `develop` selon le parcours validé. Créer une release candidate avec `git flow release start <version>`, la tester avant finalisation explicite vers `main` et création du tag `vX.Y.Z`.

La CI vérifie les branches feature, develop, release, hotfix, main et les PR vers develop/main. Les tags stables `vX.Y.Z` ne publient sur GHCR qu'après validation et vérification que leur commit appartient à main. Les builds de branches ne publient aucune image. L'authentification GHCR utilise `GITHUB_TOKEN`, sans clé SSH du VPS.

## Production

Le VPS conserve `/projects/lol-tracker-bot/docker-compose.yaml` (copie du Compose prod), un `.env` en mode `0600`, et un volume Docker pour l'état. Aucun source Python ni outil de compilation n'est nécessaire sur le VPS.

Configurer `APP_VERSION` avec un tag effectivement publié, jamais un exemple non publié. Le paquet est `ghcr.io/hakimfidjel/discord-bot`, même si le dossier VPS s'appelle `lol-tracker-bot`. Pour un paquet privé, le serveur doit être authentifié à GHCR avec une permission de lecture seule.

Depuis le répertoire de production, après validation du Compose et du `.env` :

```sh
docker compose -f docker-compose.yaml config --quiet
docker compose -f docker-compose.yaml pull bot
docker compose -f docker-compose.yaml stop bot
docker compose -f docker-compose.yaml up -d --no-deps --wait --wait-timeout 360 bot
docker compose -f docker-compose.yaml logs --tail 100 bot
```

Ce remplacement impose une brève interruption et garantit qu'une seule instance surveille les matchs. Ne pas utiliser `docker rollout`. Conserver le même nom de projet Compose pour réutiliser le volume. Ne jamais utiliser `down --volumes` lors d'une mise à jour. Pour revenir en arrière, remettre la version précédente dans `APP_VERSION` et répéter ces commandes ; ne pas purger immédiatement son image.

La CI prépare et publie l'image ; elle ne déclenche pas encore le webhook partagé. Son adaptation doit gérer le nom de dépôt distinct et le remplacement d'une instance unique, puis être validée séparément sur le VPS.

## Fiabilité et état

Les requêtes Riot sont asynchrones avec un délai maximal de 15 secondes. Les erreurs réseau, HTTP et Discord sont journalisées sans exposer les jetons et sont retentées au cycle suivant. Un match est mémorisé seulement après envoi réussi, dans un fichier remplacé atomiquement sur le volume. Un verrou exclusif empêche deux instances de partager cet état. Le score utilise la durée réelle du match.

Le premier démarrage publie le dernier match disponible, comme la version initiale. Seul le dernier match est surveillé : une longue interruption peut laisser des matchs intermédiaires non publiés. Une interruption entre l'envoi Discord et l'écriture de l'état peut exceptionnellement produire un doublon ; ce mécanisme ne garantit pas un envoi exactement une fois.

Le contrôle de santé vérifie qu'un cycle a réussi récemment ; un refus Riot persistant, une connexion Discord perdue ou une boucle bloquée rend le conteneur unhealthy. Docker ne redémarre pas automatiquement un conteneur sur ce seul état. Une erreur interne fatale arrête le processus et la politique `unless-stopped` le relance. Surveiller les journaux et renouveler la clé Riot si le service la refuse.
