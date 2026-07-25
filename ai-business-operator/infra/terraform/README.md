# Terraform

Infrastructure as code for staging and production. **Not yet written — Phase 7.**

Provisioning is deliberately deferred: the Kubernetes manifests in `../k8s/` run on
any cluster, and committing half-finished Terraform tends to produce state files
nobody trusts.

## What this will provision

| Resource | Notes |
|---|---|
| Managed Postgres | 16 with the `vector` extension enabled |
| Managed Redis | 7, single node is sufficient at this scale |
| Kubernetes cluster | Or a container service — the workloads are ordinary containers |
| Secrets manager | Holds `JWT_SECRET`, `ANTHROPIC_API_KEY`, `SYSTEMEIO_*` |
| Container registry | Four images: backend, worker, browser-agent, frontend |
| Object storage | Product artifacts and Playwright traces |

## Before writing it

- **State goes in a remote backend with locking**, from the first commit. A local
  `terraform.tfstate` in a repo is how two people destroy each other's databases.
- **No secret values in `.tf` files or `.tfvars`.** Provision the secrets manager
  itself here; populate it out of band.
- **The MCP key expires within 90 days** and cannot be automated away. Whatever this
  provisions, key rotation stays a documented human procedure — see
  `docs/systemeio_integration.md`.
