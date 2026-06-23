# Intégration Elementor — swissfirmup.com

Simulation locale dans ce repo, puis déploiement sur le site.

## 1. Installer le code WordPress

Copiez le dossier `wordpress/` dans votre hébergement :

```
wp-content/mu-plugins/firmup-payouts/
  firmup-payouts.php
  assets/
    payout-carousel.css
    payout-carousel.js
```

Créez le fichier chargeur mu-plugin :

`wp-content/mu-plugins/load-firmup-payouts.php`

```php
<?php
require WPMU_PLUGIN_DIR . '/firmup-payouts/firmup-payouts.php';
```

Vérifiez que l'API répond :

```
https://swissfirmup.com/wp-json/wp/v2/firmup_payout
```

## 2. Créer le compte de sync

1. Utilisateurs → Ajouter → `payout-bot` (rôle **Éditeur**)
2. Profil → **Mots de passe d'application** → `github-payout-sync`
3. Conservez le mot de passe (affiché une seule fois)

## 3. Simuler localement (avant prod)

```powershell
cd "c:\Users\MICHAELO\Bot Discord"
$env:WP_DRY_RUN="1"
python sync_wordpress.py
python scripts/simulate_wordpress.py
```

Ouvrez `simulation/preview.html` dans le navigateur : aperçu du carrousel page d'accueil.

## 4. Tester la connexion WordPress (staging/prod)

```powershell
$env:WP_DRY_RUN="0"
$env:API_BASE_URL="https://..."
$env:API_KEY="votre-cle"
$env:WP_USERNAME="payout-bot"
$env:WP_APP_PASSWORD="xxxx xxxx xxxx xxxx xxxx xxxx"
python sync_wordpress.py
```

## 5. Intégrer sur la page d'accueil Elementor

1. **Pages → Accueil → Modifier avec Elementor**
2. Repérez la section avec le texte d'intro (comme sur votre maquette)
3. Ajoutez un widget **Shortcode**
4. Collez :

```
[firmup_payout_carousel slides="3" autoplay="5" limit="50"]
```

5. Publiez

### Réglages recommandés

| Paramètre | Valeur | Effet |
|-----------|--------|-------|
| `slides` | `3` | 3 certificats visibles sur desktop |
| `autoplay` | `5` | défilement toutes les 5 secondes |
| `limit` | `50` | nombre max de payouts dans le carrousel |

### Style Elementor

- Section : fond noir, pleine largeur
- Widget Shortcode : largeur 100 %
- Padding section : identique à votre maquette actuelle

## 6. Secrets GitHub (quand prêt)

| Secret | Valeur |
|--------|--------|
| `WP_SITE_URL` | `https://swissfirmup.com` |
| `WP_USERNAME` | `payout-bot` |
| `WP_APP_PASSWORD` | mot de passe d'application |

Le workflow `wordpress-sync.yml` peut tourner en parallèle de Discord.

## Sécurité

- La clé API YourPropFirm reste dans **GitHub Secrets** (jamais dans WordPress)
- WordPress ne reçoit que les images déjà générées (prénom seul)
- Le carrousel affiche uniquement des images publiques
