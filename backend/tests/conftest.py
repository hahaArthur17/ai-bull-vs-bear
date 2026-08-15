"""Keep automated tests deterministic and isolated from local credentials."""

import os


# BaseSettings gives process environment variables precedence over the local
# .env file. Set these before test modules import app.main/get_settings so a
# developer's live configuration can never trigger network or provider usage.
os.environ["ENVIRONMENT"] = "test"
os.environ["AUTH_MODE"] = "demo"
os.environ["PERSISTENCE_MODE"] = "demo"
os.environ["ANALYSIS_PROVIDER"] = "demo"
