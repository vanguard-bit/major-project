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
| Malware on an engineer laptop enabled theft of a valid 2FA-backed SSO session; the actor escalated to a subset of production systems. | Section **“What Happened”** — laptop malware, session cookie theft after 2FA SSO, and subsequent production access. Companion alert: *“January 4th, 2023 Security Alert”*. | Mutated-phase undeclared path `/reconstruction/excess-scope/production-secrets` → `hidden_endpoint` + `behavioral_divergence`. |
| Exfiltrated material included customer environment variables, tokens, and encryption keys. | Same incident report sections describing **customer environment variables**, **tokens**, and **encryption keys** among accessed/exfiltrated material (see also the security-alert companion post). | Response fields `environment_variable`, `access_token`, `encryption_key` as sensitive markers → `sensitive_field_access`. |

Sources:

- https://circleci.com/blog/jan-4-2023-incident-report/
- https://circleci.com/blog/january-4-2023-security-alert/

## Okta 2022 (`okta_2022.yaml`)

Primary sources: Okta company blog posts  
*“Okta’s Investigation of the January 2022 Compromise”* and  
*“Okta Concludes Its Investigation Into the January 2022 Compromise”*.

| Documented behavior (paraphrase) | Source passage / section identifier | Fixture mapping |
| --- | --- | --- |
| A third-party support engineer workstation with access to Okta support tooling (including SuperUser) was compromised in January 2022. | Investigation blog (March 2022): narrative covering the **Sitel** support-engineer workstation compromise and access to Okta **Support** / **SuperUser** tooling. | Undeclared `/reconstruction/excess-scope/superuser-tenant` → `hidden_endpoint` + `behavioral_divergence`. |
| The threat actor accessed customer tenants within the SuperUser application. | Concluding investigation blog: findings on actor access to **customer tenants** via the **SuperUser** application. | Synthetic field `customer_tenant_id` → `sensitive_field_access`. |

Sources:

- https://www.okta.com/blog/company-and-culture/oktas-investigation-of-the-january-2022-compromise/
- https://www.okta.com/blog/company-and-culture/okta-concludes-its-investigation-into-the-january-2022-compromise/

## GitHub 2022 (`github_2022.yaml`)

Primary source: GitHub Blog *“Security alert: new campaign targeting GitHub customers using Heroku and Travis CI”*  
(`https://github.blog/news-insights/company-news/security-alert-stolen-oauth-user-tokens/`).  
Companion: Heroku *“April 2022 Incident Review”*.

| Documented behavior (paraphrase) | Source passage / section identifier | Fixture mapping |
| --- | --- | --- |
| Stolen OAuth user tokens issued to third-party integrators (Heroku / Travis CI) were abused to download private repository data. | GitHub security alert body describing **stolen OAuth user tokens** for Heroku/Travis CI integrators and download of **private repository** data. | Undeclared `/reconstruction/excess-scope/private-repo` → `hidden_endpoint` + `behavioral_divergence`. |
| An AWS API key used against npm infrastructure was obtained after private repositories were downloaded via a stolen OAuth token. | Same GitHub alert narrative linking stolen OAuth access to discovery of an **AWS API key** later used against **npm** infrastructure. | Synthetic field `aws_access_key_id` → `sensitive_field_access`. |

Sources:

- https://github.blog/news-insights/company-news/security-alert-stolen-oauth-user-tokens/
- https://www.heroku.com/blog/april-2022-incident-review/

## Wording for papers and reports

Prefer: “AIT was applied to researcher-constructed traces derived from public
descriptions.” Do **not** describe these fixtures as real incident logs.
