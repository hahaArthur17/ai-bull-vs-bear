"""Keep automated tests deterministic and isolated from local credentials."""

import os


# BaseSettings gives process environment variables precedence over the local
# .env file. Set these before test modules import app.main/get_settings so a
# developer's live configuration can never trigger network or provider usage.
os.environ["ENVIRONMENT"] = "test"
os.environ["AUTH_MODE"] = "demo"
os.environ["PERSISTENCE_MODE"] = "demo"
os.environ["ANALYSIS_PROVIDER"] = "demo"
os.environ["DEBATE_WORKFLOW_V2"] = "false"
os.environ["DEBATE_STREAMING_PROVIDER"] = "deterministic"
os.environ["REDIS_ENABLED"] = "false"
os.environ["DEBATE_RATE_LIMIT_PER_WINDOW"] = "3"
os.environ["DEBATE_RATE_LIMIT_WINDOW_SECONDS"] = "3600"
os.environ["DEBATE_ACTIVE_TTL_SECONDS"] = "1200"
