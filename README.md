# Synology Hyper Backup pour Home Assistant

Ce dépôt est un fork de
[`JurajNyiri/ha-synology-hyper-backup`](https://github.com/JurajNyiri/ha-synology-hyper-backup),
une intégration personnalisée Home Assistant permettant de surveiller les
tâches Synology Hyper Backup depuis un NAS DSM.

L’intégration d’origine ouvrait une seconde session DSM à partir du nom
d’utilisateur et du mot de passe récupérés dans Home Assistant. Cette méthode
ne réutilisait pas la validation MFA/2FA de l’intégration DSM officielle et ne
fonctionnait donc pas avec les comptes soumis à la double authentification.

Ce fork remplace cette seconde connexion par la session déjà authentifiée de
l’intégration Synology DSM officielle et par son jeton d’appareil MFA. Il ajoute
également un ensemble réduit de capteurs, les traductions françaises et
anglaises, ainsi qu’une gestion asynchrone des appels Hyper Backup.

Elle complète l’intégration officielle
[Synology DSM](https://www.home-assistant.io/integrations/synology_dsm/) et
rattache ses entités au même appareil dans Home Assistant.

## Fonctionnalités

L’intégration découvre automatiquement les tâches Hyper Backup et crée onze
capteurs par tâche :

| Capteur | Description |
| --- | --- |
| État de la sauvegarde | Dernier résultat : `done`, `failed`, `running`, etc. |
| Progression | Pourcentage d’avancement pendant une sauvegarde |
| Dernière sauvegarde réussie | Date de la dernière exécution réussie |
| Prochaine sauvegarde | Date de la prochaine exécution programmée |
| Vérification d’intégrité | Date de la dernière vérification réussie |
| Taille de la source | Taille des données sauvegardées dans la dernière version |
| Taille sur la destination | Espace occupé par la sauvegarde sur la destination |
| Croissance de la dernière version | Différence de taille sur la destination par rapport à la version précédente |
| Nouveaux fichiers | Fichiers ajoutés dans la dernière version |
| Fichiers modifiés | Fichiers modifiés dans la dernière version |
| Fichiers supprimés | Fichiers supprimés dans la dernière version |

Les statistiques de version proviennent de la même API que la fenêtre
« Statistiques » de Hyper Backup. Elles ne sont relues qu’après une nouvelle
exécution, pas à chaque rafraîchissement. Les attributs `version_time` et
`previous_version_time` indiquent les versions comparées.

Le capteur d’état contient également des attributs techniques utiles : message
et code d’erreur, identifiant de tâche, destination, type de transfert et état
du chiffrement.

La progression affiche `Inconnu` lorsque la tâche est au repos. C’est un
comportement normal.

## Authentification et 2FA

Cette version ne crée pas de deuxième connexion au NAS et ne relit pas le mot
de passe DSM.

Elle réutilise directement la session authentifiée de l’intégration officielle
Synology DSM, y compris son jeton d’appareil. La double authentification est
donc prise en charge par le flux OTP natif de Home Assistant.

En cas d’expiration de session, l’intégration tente une reconnexion avec le
jeton géré par Synology DSM.

## Prérequis

- Home Assistant 2025.8.3 ou plus récent ;
- HACS 2.0.5 ou plus récent pour l’installation HACS ;
- un NAS Synology accessible depuis Home Assistant ;
- Hyper Backup installé sur le NAS ;
- au moins une tâche Hyper Backup configurée ;
- l’intégration officielle Synology DSM configurée, chargée et fonctionnelle.

Configurez d’abord Synology DSM, y compris l’étape OTP si la 2FA est activée.

## Installation avec HACS

Ce dépôt doit être ajouté comme dépôt personnalisé :

1. Ouvrir **HACS** dans Home Assistant.
2. Ouvrir le menu **⋮** en haut à droite.
3. Sélectionner **Dépôts personnalisés**.
4. Ajouter l’adresse de ce dépôt.
5. Choisir la catégorie **Integration**.
6. Rechercher **Synology Hyper Backup** dans HACS.
7. Télécharger l’intégration.
8. Redémarrer Home Assistant.

## Configuration

Après le redémarrage :

1. Ouvrir **Paramètres → Appareils et services**.
2. Cliquer sur **Ajouter une intégration**.
3. Rechercher **Synology Hyper Backup**.
4. Sélectionner l’instance Synology DSM déjà authentifiée.

Une seule configuration Hyper Backup peut être associée à chaque entrée DSM.

## Installation manuelle

Copier le dossier :

```text
custom_components/synology_hyper_backup
```

dans le dossier `custom_components` de la configuration Home Assistant, puis
redémarrer Home Assistant.

## Exemple de carte native

Les identifiants d’entités dépendent du nom du NAS et des tâches. Remplacez les
valeurs `sensor.REMPLACER_*` par les identifiants affichés dans Home Assistant.

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: >-
      {% set entity = 'sensor.REMPLACER_ETAT' %}
      {% set result = states(entity) %}
      ## Sauvegarde Hyper Backup

      {% if result in ['done', 'success', 'ok'] %}
        🟢 **Sauvegarde réussie**
      {% elif result in ['failed', 'error'] %}
        🔴 **Échec de la sauvegarde**
      {% elif result in ['running', 'backingup', 'preparing', 'starting'] %}
        🔵 **Sauvegarde en cours**
      {% else %}
        ⚪ **État : {{ result }}**
      {% endif %}

      {% set error = state_attr(entity, 'error') %}
      {% set code = state_attr(entity, 'error_code') %}
      {% if result in ['failed', 'error'] and (error or code) %}
        **Erreur :** {{ error or 'Erreur DSM' }}{% if code %} ({{ code }}){% endif %}
      {% endif %}
  - type: entities
    show_header_toggle: false
    entities:
      - entity: sensor.REMPLACER_DERNIERE_REUSSITE
        name: Dernière réussite
        icon: mdi:clock-check-outline
      - entity: sensor.REMPLACER_PROCHAINE_SAUVEGARDE
        name: Prochaine sauvegarde
        icon: mdi:clock-outline
      - entity: sensor.REMPLACER_INTEGRITE
        name: Vérification d’intégrité
        icon: mdi:shield-check-outline
      - entity: sensor.REMPLACER_PROGRESSION
        name: Progression
        icon: mdi:progress-clock
```

Cette carte utilise uniquement les cartes natives de Home Assistant.

## Mise à niveau depuis les versions 0.1 ou 0.2

Les anciennes versions créaient une entité pour presque chaque champ brut de
l’API. Depuis la version 0.3, seules les cinq entités utiles sont créées.

Après la mise à niveau, les anciennes entités non retenues deviennent
indisponibles. Vérifiez qu’aucune automatisation ou carte ne les utilise, puis
supprimez-les depuis **Paramètres → Appareils et services → Entités**.

## Dépannage

### L’intégration DSM n’apparaît pas dans la liste

Vérifiez que l’intégration officielle Synology DSM est chargée. Rechargez-la si
nécessaire avant d’ajouter Synology Hyper Backup.

### Toutes les entités sont indisponibles

Rechargez d’abord les deux intégrations. Si le problème persiste, consultez
**Paramètres → Système → Journaux** et recherchez `synology_hyper_backup`.

### La progression est inconnue

C’est normal lorsqu’aucune sauvegarde n’est active. Une valeur numérique est
affichée pendant une exécution lorsque DSM fournit une progression.

### Une tâche est en échec

Ouvrez le capteur **État de la sauvegarde** et consultez ses attributs `error`
et `error_code`. Les messages proviennent directement de l’API DSM.

## Limites

- Les API Hyper Backup utilisées ne sont pas officiellement documentées et
  peuvent évoluer avec DSM ou le paquet Hyper Backup.
- La recherche de vérification d’intégrité repose actuellement sur le message
  anglais produit par Hyper Backup.
- Le rafraîchissement interroge localement le NAS toutes les 60 secondes.
- La taille sur la destination ne comprend pas les instantanés que le
  fournisseur de stockage conserve de son côté.
- L’intégration fournit uniquement de la supervision ; elle ne lance, suspend
  ou supprime aucune sauvegarde.

## Confidentialité et sécurité

Toutes les communications restent locales entre Home Assistant et le NAS.
L’intégration ne transmet aucun identifiant à un service externe et ne stocke
ni mot de passe ni code OTP supplémentaire.

## Crédits

Le code et le concept d’origine proviennent de
[JurajNyiri/ha-synology-hyper-backup](https://github.com/JurajNyiri/ha-synology-hyper-backup).

Comme indiqué par son auteur, cette intégration était elle-même partiellement
basée sur
[bbckr/ha-synology-tasks](https://github.com/bbckr/ha-synology-tasks), dans sa
version consultée le 28 décembre 2025. Ce projet poursuit un objectif similaire
pour la supervision des tâches Synology dans Home Assistant.

La chaîne de filiation du code est donc :

```text
bbckr/ha-synology-tasks
  └── JurajNyiri/ha-synology-hyper-backup
        └── scaput69/ha-synology-hyper-backup-2fa
```

Ce fork conserve la licence MIT et l’attribution au projet original. Les
modifications propres à ce dépôt concernent principalement la compatibilité
MFA/2FA, l’utilisation de la session DSM partagée, le modèle d’entités et la
documentation.

Licence MIT. Ce projet communautaire n’est affilié ni à Synology ni à Home
Assistant.
