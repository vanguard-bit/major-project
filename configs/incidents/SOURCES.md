# Incident reconstruction sources

These fixtures are **researcher-constructed traces derived from public
vendor disclosures**. They are **not** original incident telemetry or vendor
logs. Synthetic paths use the `/reconstruction/...` prefix deliberately.

Primary sources were accessed on **2026-07-27** (UTC).

## CircleCI 2023 (`circleci_2023.yaml`)

Primary source: CircleCI blog post *“CircleCI incident report for January 4, 2023”*
(`https://circleci.com/blog/jan-4-2023-incident-report/`).

| Documented behavior (paraphrase) | Source passage / section identifier | Fixture mapping |
| --- | --- | --- |
| Malware on an engineer laptop enabled theft of a valid 2FA-backed SSO session; the actor escalated to a subset of production systems. | `circleci.com/blog/jan-4-2023-incident-report` § “What Happened” (laptop malware → 2FA SSO session-cookie theft → production access). Companion: `circleci.com/blog/january-4-2023-security-alert`. | Mutated-phase undeclared path `/reconstruction/excess-scope/production-secrets` → `hidden_endpoint` + `behavioral_divergence`. |
| Exfiltrated material included customer environment variables, tokens, and encryption keys. | Same incident report § customer environment variables / tokens / encryption keys (see also security-alert companion). | Response fields `environment_variable`, `access_token`, `encryption_key` as sensitive markers → `sensitive_field_access`. |

Sources:

- https://circleci.com/blog/jan-4-2023-incident-report/
- https://circleci.com/blog/january-4-2023-security-alert/

## Okta 2022 (`okta_2022.yaml`)

Primary sources: Okta company blog posts
*“Okta’s Investigation of the January 2022 Compromise”* and
*“Okta Concludes Its Investigation Into the January 2022 Compromise”*.

| Documented behavior (paraphrase) | Source passage / section identifier | Fixture mapping |
| --- | --- | --- |
| A third-party support engineer workstation with access to Okta support tooling (including SuperUser) was compromised in January 2022. | `okta.com/.../oktas-investigation-of-the-january-2022-compromise` (March 2022 investigation): Sitel support-engineer workstation → Okta Support / SuperUser tooling. | Undeclared `/reconstruction/excess-scope/superuser-tenant` → `hidden_endpoint` + `behavioral_divergence`. |
| The threat actor accessed customer tenants within the SuperUser application. | `okta.com/.../okta-concludes-its-investigation-into-the-january-2022-compromise`: actor access to customer tenants via SuperUser. | Synthetic field `customer_tenant_id` → `sensitive_field_access`. |

Sources:

- https://www.okta.com/blog/company-and-culture/oktas-investigation-of-the-january-2022-compromise/
- https://www.okta.com/blog/company-and-culture/okta-concludes-its-investigation-into-the-january-2022-compromise/

## GitHub 2022 (`github_2022.yaml`)

Primary source: GitHub Blog *“Security alert: new campaign targeting GitHub customers using Heroku and Travis CI”*
(`https://github.blog/news-insights/company-news/security-alert-stolen-oauth-user-tokens/`).
Companion: Heroku *“April 2022 Incident Review”*.

| Documented behavior (paraphrase) | Source passage / section identifier | Fixture mapping |
| --- | --- | --- |
| Stolen OAuth user tokens issued to third-party integrators (Heroku / Travis CI) were abused to download private repository data. | `github.blog/.../security-alert-stolen-oauth-user-tokens` body: stolen OAuth user tokens (Heroku/Travis CI) → private repository download. | Undeclared `/reconstruction/excess-scope/private-repo` → `hidden_endpoint` + `behavioral_divergence`. |
| An AWS API key used against npm infrastructure was obtained after private repositories were downloaded via a stolen OAuth token. | Same GitHub alert: stolen OAuth access → AWS API key discovery → use against npm infrastructure. | Synthetic field `aws_access_key_id` → `sensitive_field_access`. |

Sources:

- https://github.blog/news-insights/company-news/security-alert-stolen-oauth-user-tokens/
- https://www.heroku.com/blog/april-2022-incident-review/

## Wording for papers and reports

Prefer: “AIT was applied to researcher-constructed traces derived from public
descriptions.” Do **not** describe these fixtures as real incident logs.
