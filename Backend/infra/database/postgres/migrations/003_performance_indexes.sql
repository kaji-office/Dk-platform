-- P9-S-02: Performance indexes for high-frequency lookups
-- api_keys.key_hash — every authenticated API key request does this lookup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_keys_key_hash
    ON api_keys(key_hash)
    WHERE is_active = true;

-- users.verification_token — email verification flow
CREATE INDEX IF NOT EXISTS idx_users_verification_token
    ON users(verification_token)
    WHERE verification_token IS NOT NULL;

-- users.reset_token — password reset flow
CREATE INDEX IF NOT EXISTS idx_users_reset_token
    ON users(reset_token)
    WHERE reset_token IS NOT NULL;
