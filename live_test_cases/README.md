# Live SaaS Test Cases

Place real live-platform scenarios here as `.yaml` files. Do not commit real tokens. The live runner reads credentials from environment variables.

## Expected Shape

Each file must define:

- `target`: normal AIT target metadata, including `base_url`, `expected_endpoints`, `expected_scopes`, and `sensitive_markers`
- `auth_env_var`: environment variable containing the token
- `requests`: explicit baseline and mutated requests to execute

## Safe Usage

- Use only accounts, workspaces, sandboxes, or tenants you control and are authorized to test.
- Prefer test data, not production user data.
- Keep request volume low and within platform rate limits.
- Review each platform's developer terms before running.

## Example

See `github_live_example.yaml.example`.
