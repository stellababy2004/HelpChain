# HelpChain – Operating Model

## Purpose

Defines how HelpChain operates across backend, frontend, and analytics components.

## Roles

- **Stella Barbarella** – Lead SOC Analyst, Architect, and DevOps.
- **Contributors** – Volunteer developers and AI assistants (Copilot, MCP context).
- **Automation** – CI/CD pipelines, Dependabot, Site24x7 monitoring, email alerts.

## Workflow

1. Code is developed on feature branches.
2. Every change goes through Pull Request → Review → Merge to `main`.
3. Automated checks: CodeQL, Trivy, Ruff, unit tests.
4. Deployments via GitHub Actions.

## Communication

- **GitHub Issues** → Tasks & bugs
- **Discussions** → Planning
- **Notes** → Documentation and standards
