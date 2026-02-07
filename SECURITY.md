# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public issue
2. Email: arthurmgraf@hotmail.com
3. Include a detailed description of the vulnerability
4. Allow reasonable time for a fix before public disclosure

## Security Practices

- All API keys and secrets are managed via environment variables
- Input validation on all API endpoints (Pydantic)
- NeMo Guardrails for LLM safety
- Rate limiting on all endpoints
- CORS configuration with explicit origins
