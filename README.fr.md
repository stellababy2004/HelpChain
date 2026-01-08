# [![CI](https://github.com/stellababy2004/HelpChain.bg/actions/workflows/ci.yml/badge.svg)](https://github.com/stellababy2004/HelpChain.bg/actions/workflows/ci.yml)
# HelpChain – Plateforme de soutien social et sanitaire

🌍 Langues : [English](README.md) | [Български](README.bg.md) | [Français](README.fr.md)

**HelpChain** est une plateforme web développée avec Flask, destinée à mettre en relation des personnes en situation de besoin avec des bénévoles et des professionnels capables d’apporter une aide concrète.

Le projet est conçu pour un usage institutionnel, associatif et public.

---

## 🌐 Site en ligne

➡️ **https://helpchain.live**

---

## 🎯 Objectifs du projet

- Centralisation des demandes d’aide sociale et sanitaire
- Coordination des bénévoles et des missions
- Administration sécurisée avec contrôle des rôles et 2FA
- Communication multilingue et accessible
- Garanties techniques de stabilité et de conformité

---

## ✨ Fonctionnalités principales

### Pour les usagers
- Dépôt structuré de demandes d’aide
- Interface multilingue (FR / EN / BG)
- Accessibilité et compatibilité mobile
- Sécurité des formulaires (CSRF)

### Pour les bénévoles
- Authentification sans mot de passe (email)
- Tableau de bord des missions
- Géolocalisation
- Notifications par email

### Pour les administrateurs
- Interface d’administration dédiée
- Gestion des bénévoles et des demandes
- Statistiques et journaux d’audit
- Système de rôles et permissions

---

## 🛠 Technologies

- Flask (Python)
- SQLAlchemy
- Flask-Babel
- Flask-Login
- GitHub Actions (CI)
- Déploiement ASGI (Uvicorn / Render)

---

## 🧪 Fiabilité et contrôles

La plateforme intègre :
- une vérification automatique des écarts de schéma (ORM ↔ base)
- des tests CRUD avec rollback
- un pipeline CI bloquant toute incohérence

Cela garantit une exploitation fiable en environnement institutionnel.

---

## 📄 Licence

Licence MIT

---

**Développé par :** Stella Barbarella  
**Site web :** https://helpchain.live
