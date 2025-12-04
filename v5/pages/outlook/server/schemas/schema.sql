-- server/schema.sql

PRAGMA encoding = 'UTF-8';
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;
PRAGMA busy_timeout = 5000;

BEGIN;

-- accounts
CREATE TABLE IF NOT EXISTS account (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  email        TEXT NOT NULL COLLATE NOCASE UNIQUE,
  password     TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT '未登录' CHECK (status IN ('未登录','登录成功','登录失败')),
  username     TEXT,
  birthday     TEXT,
  version      INTEGER NOT NULL DEFAULT 1,
  created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now','utc')),
  updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now','utc'))
);
CREATE INDEX IF NOT EXISTS idx_account_status ON account(status);
--辅助邮箱
CREATE TABLE IF NOT EXISTS account_recovery_email (
  account_id   INTEGER NOT NULL REFERENCES account(id) ON DELETE CASCADE,
  email        TEXT NOT NULL,
  PRIMARY KEY (account_id, email)
);
CREATE INDEX IF NOT EXISTS idx_recovery_email_email ON account_recovery_email(email);
--辅助电话
CREATE TABLE IF NOT EXISTS account_recovery_phone (
  account_id   INTEGER NOT NULL REFERENCES account(id) ON DELETE CASCADE,
  phone        TEXT NOT NULL,
  PRIMARY KEY (account_id, phone)
);
CREATE INDEX IF NOT EXISTS idx_recovery_phone_phone ON account_recovery_phone(phone);
--别名表
CREATE TABLE IF NOT EXISTS account_alias (
  account_id INTEGER NOT NULL REFERENCES account(id) ON DELETE CASCADE,
  alias      TEXT NOT NULL COLLATE NOCASE CHECK (alias = lower(alias)),
  PRIMARY KEY (account_id, alias)
);
CREATE INDEX IF NOT EXISTS idx_account_alias_alias ON account_alias(alias);

--msal cache key表
CREATE TABLE IF NOT EXISTS account_token_cache (
  account_id   INTEGER NOT NULL REFERENCES account(id) ON DELETE CASCADE,
  uuid        TEXT NOT NULL COLLATE NOCASE CHECK (uuid = lower(uuid)),
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now','utc')),
  PRIMARY KEY (account_id, uuid)
);
CREATE INDEX IF NOT EXISTS idx_token_cache_uuid ON account_token_cache(uuid);

CREATE TABLE IF NOT EXISTS account_version (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id           INTEGER NOT NULL REFERENCES account(id) ON DELETE CASCADE,
  version              INTEGER NOT NULL,
  email                TEXT NOT NULL,
  password             TEXT NOT NULL,
  status               TEXT NOT NULL,
  username             TEXT,
  birthday             TEXT,
  recovery_emails_json TEXT NOT NULL,
  recovery_phones_json TEXT NOT NULL,
  aliases_json         TEXT NOT NULL,
  note                 TEXT,
  created_by           TEXT,
  created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now','utc')),
  UNIQUE(account_id, version)
);
CREATE INDEX IF NOT EXISTS idx_accver_accid_ver ON account_version(account_id, version DESC);

-- mails
CREATE TABLE IF NOT EXISTS mail_message (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id         INTEGER NOT NULL REFERENCES account(id) ON DELETE CASCADE,

  msg_uid            TEXT,
  msg_id             TEXT,

  subject            TEXT NOT NULL DEFAULT '',
  subject_lc         TEXT GENERATED ALWAYS AS (lower(subject)) STORED,

  from_addr          TEXT NOT NULL DEFAULT '',
  from_addr_lc       TEXT GENERATED ALWAYS AS (lower(from_addr)) STORED,

  to_joined          TEXT NOT NULL DEFAULT '',
  to_joined_lc       TEXT GENERATED ALWAYS AS (lower(to_joined)) STORED,

  folder             TEXT NOT NULL DEFAULT 'INBOX',
  folder_lc          TEXT GENERATED ALWAYS AS (lower(folder)) STORED,

  labels_joined      TEXT NOT NULL DEFAULT '',
  labels_joined_lc   TEXT GENERATED ALWAYS AS (lower(labels_joined)) STORED,

  sent_at            TEXT,
  received_at        TEXT,
  size_bytes         INTEGER,
  attachments_count  INTEGER NOT NULL DEFAULT 0,
  flags              INTEGER NOT NULL DEFAULT 0,
  snippet            TEXT,

  created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now','utc')),
  updated_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now','utc')),

  UNIQUE(account_id, msg_uid)
);

CREATE INDEX IF NOT EXISTS idx_mail_acc_recv
  ON mail_message(account_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_mail_acc_from
  ON mail_message(account_id, from_addr_lc, id);
CREATE INDEX IF NOT EXISTS idx_mail_acc_subject
  ON mail_message(account_id, subject_lc, id);
CREATE INDEX IF NOT EXISTS idx_mail_acc_to_lc
  ON mail_message(account_id, to_joined_lc, id);
--收件人
CREATE TABLE IF NOT EXISTS mail_recipient (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id   INTEGER NOT NULL REFERENCES mail_message(id) ON DELETE CASCADE,
  account_id   INTEGER NOT NULL REFERENCES account(id) ON DELETE CASCADE,
  kind         TEXT NOT NULL DEFAULT 'to',
  addr         TEXT NOT NULL,
  addr_lc      TEXT GENERATED ALWAYS AS (lower(addr)) STORED,
  CHECK (kind IN ('to','cc','bcc'))
);
CREATE INDEX IF NOT EXISTS idx_rec_acc_addr
  ON mail_recipient(account_id, addr_lc, message_id);
CREATE INDEX IF NOT EXISTS idx_rec_msg
  ON mail_recipient(message_id);

--邮箱内容
CREATE TABLE IF NOT EXISTS mail_body (
  message_id   INTEGER PRIMARY KEY REFERENCES mail_message(id) ON DELETE CASCADE,
  headers      TEXT,
  body_plain   TEXT,
  body_html    TEXT
);
--邮箱附件
CREATE TABLE IF NOT EXISTS mail_attachment (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id     INTEGER NOT NULL REFERENCES mail_message(id) ON DELETE CASCADE,
  account_id     INTEGER NOT NULL REFERENCES account(id) ON DELETE CASCADE,
  storage_url    TEXT NOT NULL,
  created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now','utc'))
);
CREATE INDEX IF NOT EXISTS idx_attach_msg ON mail_attachment(message_id);
CREATE INDEX IF NOT EXISTS idx_attach_acc ON mail_attachment(account_id, id);

--邮箱文件夹
CREATE TABLE IF NOT EXISTS mail_folder (
    id TEXT NOT NULL,                       -- Graph API的文件夹ID
    account_id INTEGER NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,             -- 显示名称（如"收件箱"、"Inbox"）
    well_known_name TEXT,                   -- 标准名称（inbox, sent, drafts, deleted, junk, archive）
    parent_folder_id TEXT,                  -- 父文件夹ID
    PRIMARY KEY (id, account_id)
);

CREATE INDEX IF NOT EXISTS idx_folder_account ON mail_folder(account_id);
CREATE INDEX IF NOT EXISTS idx_folder_well_known ON mail_folder(account_id, well_known_name);

--邮箱同步状态
CREATE TABLE IF NOT EXISTS mail_sync_state (
    account_id INTEGER PRIMARY KEY REFERENCES account(id) ON DELETE CASCADE,
    last_sync_time TEXT,
    last_msg_uid TEXT,
    delta_link TEXT,  -- Microsoft Graph的deltaLink
    skip_token TEXT,   -- 分页token
    total_synced INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now','utc'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mail_unique ON mail_message(account_id, msg_uid);-- 确保邮件唯一性（已有）
CREATE INDEX IF NOT EXISTS idx_mail_received ON mail_message(account_id, received_at DESC);-- 添加时间索引用于快速查询

COMMIT;
PRAGMA user_version = 5;
