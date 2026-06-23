# Bot Discord — Payouts FirmUp



Publie automatiquement les nouveaux certificats de payout sur Discord et WordPress (image générée depuis le template FirmUp, prénom uniquement).



## Fonctionnement



1. Récupère les nouveaux payouts via `GET /client/v2/payouts`

2. Génère l'image depuis `assets/template-payout.png` + données API

3. Publie l'image sur Discord (webhook) et/ou WordPress (REST API)



## Documentation API



- [YourPropFirm Client API (Stoplight)](https://hypestacksypf.stoplight.io/docs/yourpropfirm-client-api)

- [List Payouts (v2)](https://hypestacksypf.stoplight.io/docs/yourpropfirm-client-api/sss1h30tkfw16-list-payouts)

- Auth : header `X-Client-Key`



## Structure du projet



| Fichier | Rôle |

|---------|------|

| `assets/template-payout.png` | Template visuel FirmUp |

| `fonts/` | Roboto Regular, Medium, Black |

| `certificate.py` | Génération de l'image |

| `sync.py` | Sync API → Discord |

| `sync_wordpress.py` | Sync API → WordPress |

| `wordpress_client.py` | Client REST WordPress (mode dry-run inclus) |

| `wordpress/` | mu-plugin PHP + carrousel Swiper pour Elementor |
| `dist/firmup-payouts.zip` | Plugin prêt à téléverser dans wp-admin |

| `scripts/simulate_wordpress.py` | Aperçu HTML local du carrousel |

| `config.json` | Positions texte, statuts payout, config WordPress |



## Secrets GitHub



Dans **Settings → Secrets and variables → Actions** :



| Secret | Exemple |

|--------|---------|

| `API_BASE_URL` | `https://bqsyp740n4.execute-api.ap-southeast-1.amazonaws.com` |

| `API_KEY` | votre clé `X-Client-Key` |

| `DISCORD_WEBHOOK_URL` | `https://discord.com/api/webhooks/...` |

| `WP_USERNAME` | `payout-bot` |

| `WP_APP_PASSWORD` | mot de passe d'application WordPress |



## Simulation WordPress (avant prod)



Simule l'intégration pour **swissfirmup.com** sans toucher au site :



```powershell

cd "c:\Users\MICHAELO\Bot Discord"

$env:WP_DRY_RUN="1"

python sync_wordpress.py

python scripts/simulate_wordpress.py

```



Ouvrez `simulation/preview.html` dans le navigateur.

Fichiers générés :

- `simulation/certificates/` — images PNG comme sur le site

- `simulation/wordpress-export.json` — payloads REST qui seraient envoyés

- `simulation/preview.html` — carrousel 3 slides (page d'accueil Elementor)

Guide Elementor : `wordpress/ELEMENTOR.md`



## Configuration (`config.json`)



- `payout_states` — statuts à publier (ex. `["Approved"]`)

- `certificate.design_size` — dimensions du canvas Figma (`1500×1075`)
- `assets/template-payout.png` — template redimensionné à cette taille

- `certificate.privacy` — `first_name_only` masque le nom de famille (affiche uniquement le prénom)

- `certificate.fields` — police, taille, couleur et position de chaque champ



### Ajuster le positionnement

Les coordonnées sont dans `certificate.fields.*.position` `[x, y]` pour un canvas **1500×1075**.

**Outil de mesure intégré** (recommandé) :

```powershell
python scripts/measure_positions.py
```

1. Cliquez au **centre** de chaque zone dans l'ordre : montant → programme → prénom → date
2. Les coordonnées `[x, y]` s'affichent en direct sous la souris
3. Bouton **« Copier config JSON »** → collez les valeurs dans `config.json`

Vous pouvez charger `assets/template-payout.png` ou `test-certificate.png` via « Changer d'image ».

**Autres outils possibles :**
- **Figma** — sélectionnez un calque, panneau Design → position X/Y (origine en haut à gauche)
- **Photopea** / GIMP — règle + info curseur en pixels

Test visuel :

```powershell
python certificate.py
```

Génère `test-certificate.png` avec des données d'exemple.



## Test du flux complet



```powershell

$env:API_BASE_URL="https://bqsyp740n4.execute-api.ap-southeast-1.amazonaws.com"

$env:API_KEY="votre-cle"

$env:DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."

python sync.py

```



## Test WordPress (prod)



```powershell

$env:WP_DRY_RUN="0"

$env:API_BASE_URL="https://bqsyp740n4.execute-api.ap-southeast-1.amazonaws.com"

$env:API_KEY="votre-cle"

$env:WP_USERNAME="payout-bot"

$env:WP_APP_PASSWORD="xxxx xxxx xxxx xxxx xxxx xxxx"

python sync_wordpress.py

```



## Fréquence



Par défaut : toutes les **15 minutes** (`.github/workflows/discord-sync.yml` et `wordpress-sync.yml`).


