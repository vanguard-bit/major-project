# Incident reconstruction sources

These fixtures are **researcher-constructed traces derived from public
vendor disclosures**. They are **not** original incident telemetry or vendor
logs. Synthetic paths use the `/reconstruction/...` prefix deliberately.

Primary sources were accessed on **2026-07-27** (UTC).

## CircleCI 2023 (`circleci_2023.yaml`)

| Documented behavior (paraphrase) | Source passage / location | Fixture mapping |
| --- | --- | --- |
| Malware on an engineer laptop enabled theft of a valid 2FA-backed SSO session; the actor escalated to a subset of production systems. | CircleCI incident report, “What happened” narrative (session cookie theft and production access). | Mutated-phase undeclared path `/reconstruction/excess-scope/production-secrets` → `hidden_endpoint` + `behavioral_divergence`. |
| Exfiltrated material included customer environment variables, tokens, and encryption keys. | Same report, description of exfiltrated data classes. | Response fields `environment_variable`, `access_token`, `encryption_key` as sensitive markers → `sensitive_field_access`. |

Sources:

- https://circleci.com/blog/jan-4-2023-incident-report/
- https://circleci.com/blog/january-4-2023-security-alert/

## Okta 2022 (`okta_2022.yaml`)

| Documented behavior (paraphrase) | Source passage / location | Fixture mapping |
| --- | --- | --- |
| A third-party support engineer workstation with access to Okta support tooling (including SuperUser) was compromised in January 2022. | Okta investigation blog (March 2022), description of Sitel support engineer access and SuperUser. | Undeclared `/reconstruction/excess-scope/superuser-tenant` → `hidden_endpoint` + `behavioral_divergence`. |
| The threat actor accessed customer tenants within the SuperUser application. | Okta concluding investigation blog; SuperUser customer-tenant access finding. | Synthetic field `customer_tenant_id` → `sensitive_field_access`. |

Sources:

- https://www.okta.com/blog/company-and-culture/oktas-investigation-of-the-january-2022-compromise/
- https://www.okta.com/blog/company-and-culture/okta-concludes-its-investigation-into-the-january-2022-compromise/

## GitHub 2022 (`github_2022.yaml`)

| Documented behavior (paraphrase) | Source passage / location | Fixture mapping |
| --- | --- | --- |
| Stolen OAuth user tokens issued to third-party integrators (Heroku / Travis CI) were abused to download private repository data. | GitHub security alert on stolen OAuth user tokens (April 2022). | Undeclared `/reconstruction/excess-scope/private-repo` → `hidden_endpoint` + `behavioral_divergence`. |
| An AWS API key used against npm infrastructure was obtained after private repositories were downloaded via a stolen OAuth token. | Same GitHub alert, npm / AWS key narrative. | Synthetic field `aws_access_key_id` → `sensitive_field_access`. |

Sources:

- https://github.blog/news-insights/company-news/security-alert-stolen-oauth-user-tokens/
- https://www.heroku.com/blog/april-2022-incident-review/

## Wording for papers and reports

Prefer: “AIT was applied to researcher-constructed traces derived from public
descriptions.” Do **not** describe these fixtures as real incident logs.
