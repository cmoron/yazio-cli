# yazio-cli

CLI pour le suivi nutritionnel Yazio, basé sur l'API non officielle reverse-engineered.

## Installation

```bash
cd ~/src/yazio-cli
uv sync
```

## Authentification

### Email / mot de passe (si tu en as un)

```bash
uv run yazio login
```

### Apple / Google Sign-In (pas de mot de passe Yazio)

Si tu t'es inscrit via "Sign in with Apple" ou Google, tu n'as pas de mot de passe Yazio. Il faut extraire le token depuis le site web :

1. Ouvre https://www.yazio.com/fr/app/account dans Firefox (ou Chrome)
2. Connecte-toi avec ton compte Apple/Google
3. Ouvre les DevTools : **F12** → onglet **Stockage** (Firefox) ou **Application** (Chrome)
4. Dans **Cookies** → `https://www.yazio.com`, copie la valeur du cookie `yz_session`
   - C'est une longue chaîne qui commence par `Fe26.2**...`
5. Lance la commande :

```bash
uv run yazio web-login --session-cookie 'Fe26.2**...'
```

Le CLI extrait les tokens API depuis la page web et les sauvegarde dans `~/.config/yazio/token.json`. Le refresh est automatique tant que le refresh token est valide.

Si le token expire et que le refresh échoue, il suffit de refaire l'étape ci-dessus.

## Commandes

```
yazio summary [DATE]       Résumé journalier (calories, macros, eau, pas)
yazio meals [DATE]         Détail des aliments consommés
yazio water [DATE]         Consommation d'eau
yazio goals [DATE]         Objectifs nutrition
yazio exercises [DATE]     Exercices du jour
yazio weight               Historique de poids (10 dernières entrées)
yazio search <query>       Chercher un aliment dans la base Yazio
yazio add <ID> --amount N --meal breakfast|lunch|dinner|snack
                           Ajouter un aliment au journal
yazio remove <ID>          Supprimer une entrée
```

`DATE` est au format `YYYY-MM-DD`, par défaut aujourd'hui.

## Notes

- API non officielle — peut cesser de fonctionner si Yazio modifie son backend
- Basé sur le travail de [juriadams/yazio](https://github.com/juriadams/yazio)
- Token stocké en clair dans `~/.config/yazio/token.json`
