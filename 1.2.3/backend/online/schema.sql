CREATE TABLE IF NOT EXISTS rooms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_code TEXT NOT NULL UNIQUE,
  room_name TEXT NOT NULL,
  status TEXT NOT NULL,
  host_token TEXT NOT NULL,
  guest_token TEXT,
  host_user_id TEXT,
  guest_user_id TEXT,
  host_name TEXT NOT NULL,
  guest_name TEXT,
  host_avatar TEXT NOT NULL DEFAULT '',
  guest_avatar TEXT,
  host_connected INTEGER NOT NULL DEFAULT 1,
  guest_connected INTEGER NOT NULL DEFAULT 0,
  host_ready INTEGER NOT NULL DEFAULT 0,
  guest_ready INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status);
CREATE INDEX IF NOT EXISTS idx_rooms_expires_at ON rooms(expires_at);
