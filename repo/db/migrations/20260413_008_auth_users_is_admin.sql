ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE auth_users SET is_admin = TRUE WHERE email = 'admin';
