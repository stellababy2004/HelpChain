# HelpChain — Infrastructure numérique de coordination pour le secteur social

**HelpChain** est une infrastructure numérique de coordination opérationnelle destinée aux organisations du secteur social, aux réseaux associatifs et aux services publics locaux en France.

Son ambition est de faciliter la coopération entre structures autonomes, de clarifier les responsabilités et de rendre les échanges et les actions traçables, sans remplacer les organisations, leurs décisions métier ou leurs outils existants.

> **Positionnement :** une infrastructure de coordination inter-organisationnelle, et non une place de marché publique de l'aide ou un simple logiciel de gestion de dossiers.

[Site web](https://helpchain.live) · [English](README.md) · [Български](README.bg.md) · [Sécurité](SECURITY.md) · [Documentation](docs/README.md)

## À qui s'adresse HelpChain ?

- **CCAS et CIAS :** coordination opérationnelle et continuité du suivi avec les partenaires habilités.
- **Fédérations et réseaux associatifs :** cadre commun de coopération entre structures qui conservent leur autonomie.
- **Associations et centres sociaux :** organisation des demandes, clarification des responsabilités et suivi des actions.
- **Collectivités et services territoriaux :** visibilité sur les circuits de coordination dans un périmètre défini.

## Le problème traité

Les situations nécessitant l'intervention de plusieurs acteurs peuvent donner lieu à des échanges dispersés, des responsabilités peu lisibles et des difficultés de suivi. HelpChain vise à fournir un cadre opérationnel commun, fondé sur des droits d'accès explicites et une traçabilité des actions.

## Capacités du produit

| Domaine | Rôle |
| --- | --- |
| Demandes et situations | Structurer la réception, l'attribution et le suivi opérationnel |
| Coordination inter-structures | Encadrer les orientations et transmissions entre organisations autorisées |
| Responsabilités | Identifier les acteurs habilités et les actions attendues |
| Traçabilité | Conserver un historique des événements et actions pertinents |
| Cloisonnement des données | Appliquer des périmètres d'accès par structure et par rôle |
| Suivi opérationnel | Faciliter le pilotage des demandes, échéances et interventions |

Les fonctionnalités disponibles, les scénarios validés et la préparation au déploiement doivent être distingués : l'existence du code et la réussite de tests automatisés ne constituent pas, à elles seules, une validation en conditions réelles.

## Modèle opérationnel

Le socle applicatif actuel repose sur le parcours :

```text
Demande → Situation (Case) → Attribution → Suivi et historique
                                  ↓
                     Orientation encadrée vers un partenaire
```

Les échanges entre structures sont limités aux informations et droits explicitement autorisés. HelpChain ne donne pas un accès général aux dossiers internes d'une autre organisation.

## Architecture et sécurité

- Application Python / Flask avec SQLAlchemy et Alembic.
- Base PostgreSQL en production ; SQLite pour certains usages locaux.
- Authentification, contrôle des rôles (RBAC), périmètres par structure et MFA pour l'administration.
- Journaux d'audit et tests de non-régression ciblés sur les frontières d'accès.
- Intégration et vérifications automatisées via GitHub Actions.
- Déploiement applicatif sur Render.

Ces éléments décrivent l'architecture et les mécanismes présents dans le dépôt ; ils ne constituent ni une certification de sécurité, ni une attestation de conformité RGPD.

Pour les détails techniques : [architecture](docs/02-architecture/system-architecture.md), [modèle des structures](docs/02-architecture/tenant-model.md), [orientations inter-organisations](docs/02-architecture/inter-organization-referrals.md) et [politique de sécurité](SECURITY.md).

## État du projet

**MVP en développement actif et en phase de vérification fonctionnelle.** La préparation à un pilote nécessite la validation des parcours de bout en bout, des rôles, du cloisonnement entre structures et des conditions opérationnelles. Aucun déploiement pilote ni partenariat commercial n'est revendiqué ici sans preuve vérifiable.

**Marché prioritaire :** France — CCAS/CIAS, fédérations, réseaux associatifs et collectivités.

## Licence et propriété intellectuelle

**Logiciel propriétaire — tous droits réservés.** Le code source n'est pas publié sous licence open source. Sa consultation publique ne confère aucun droit de copie, modification, distribution, hébergement ou exploitation. Voir le fichier [LICENSE](LICENSE) pour les conditions applicables.

---

**HelpChain** — Une coordination inter-organisationnelle structurée et traçable.  
**Site :** https://helpchain.live
