# Security Configuration

## Environment Variables

This project uses environment variables to manage sensitive configuration data. All secrets are stored in the `.env` file, which is **NOT** committed to version control.

### Setup Instructions

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and update the following secrets with secure values:

   - **SECRET_KEY**: Flask session secret key
     - Generate a secure key with: `python -c "import secrets; print(secrets.token_hex(32))"`
   
   - **UPDATE_SECRET**: Docker update authentication secret
     - Use a strong, random password

3. Ensure `.env` is listed in `.gitignore` (already configured)

### Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `REST_ENDPOINT` | REST API endpoint URL | Yes |
| `ENABLE_PROXY_DETECTION` | Enable proxy detection | No |
| `ENABLE_PROXIED_SECURIY_KEY` | Proxy security key | No |
| `HTPASSWD` | Path to htpasswd file | Yes |
| `SECRET_KEY` | Flask secret key for sessions | Yes |
| `UPDATE_SECRET` | Docker update authentication | Yes |
| `TIMEZONE` | Application timezone | Yes |

### Security Best Practices

- **Never commit `.env`** to version control
- Use strong, randomly generated secrets
- Rotate secrets regularly
- Use different secrets for development and production
- Keep `.env.example` updated with new variables (but without real values)

### Docker Compose

The `docker-compose.yml` file automatically loads environment variables from `.env` using the `env_file` directive. All secrets are now managed through this file instead of being hardcoded.
