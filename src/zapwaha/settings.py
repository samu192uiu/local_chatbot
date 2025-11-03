# src/zapwaha/settings.py
# Futuro: carregar defaults + .env + tenants/<slug>/config.yml
# Dica: pydantic-settings ou dynaconf
DEFAULTS = {
    "timezone": "America/Sao_Paulo",
    "currency": "BRL",
}
