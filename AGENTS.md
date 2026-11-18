# Instructions du projet LoL Tracker Bot

- Utiliser Git Flow : `main`, `develop`, `feature/`, `release/`, `hotfix/` et préfixe de tag `v`. Initialisation : `git config gitflow.branch.master main`, `git flow init -d`, puis `git config gitflow.prefix.versiontag v`.
- Développer sur une branche feature via les commandes natives Git Flow. Ne pas publier sans autorisation. Faire tester chaque release candidate avant finalisation vers main.
- Lire le Makefile et lancer `make check` : construction Docker, Ruff, Mypy strict et tests sans réseau. Ne jamais utiliser le `.venv` historique.
- Utiliser `docker-compose.yml` pour le développement ; `docker-compose.prod.yml` est autonome et consomme exclusivement l'image GHCR versionnée.
- Ne jamais incorporer `.env` ou des secrets dans Git ou dans une image.
- Le bot est une instance unique permanente : aucun Sablier, aucun port entrant et aucun rollout à deux instances. Préserver le volume d'état lors des mises à jour.
- Le répertoire VPS est `/srv/hosting/projects/lol-tracker-bot`, le dépôt GitHub et le paquet GHCR sont `lol-tracker-bot`. L'ancienne racine `/projects` est supprimée.
- Le déployeur commun utilise `DEPLOYMENT_MODE=replace` dans le `.env` VPS pour préserver une seule instance. Il est dans `/srv/hosting/infrastructure/webhooks` ; son `PROJECTS_ROOT` vaut `/srv/hosting/projects`.
- Ne pas envoyer de message Discord ou appeler Riot pour les tests ; employer des simulacres.
