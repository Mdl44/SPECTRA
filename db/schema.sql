-- Drop Views
DROP VIEW IF EXISTS V_TOPOLOGY CASCADE;
DROP VIEW IF EXISTS V_IPAM_ADDRESS_SUBNET CASCADE;
DROP VIEW IF EXISTS V_ACTIVE_ALERTS CASCADE;
DROP VIEW IF EXISTS V_DEVICE_STATUS CASCADE;

DROP TABLE IF EXISTS DEVICE_TEMPLATE_VARS CASCADE;
DROP TABLE IF EXISTS INTERFACE_METRIC CASCADE;
DROP TABLE IF EXISTS DEVICE_METRIC CASCADE;
DROP TABLE IF EXISTS TOPOLOGY_LINK CASCADE;
DROP TABLE IF EXISTS DISCOVERY CASCADE;
DROP TABLE IF EXISTS SYSLOG CASCADE;
DROP TABLE IF EXISTS ALERT CASCADE;
DROP TABLE IF EXISTS JOB_TARGET CASCADE;
DROP TABLE IF EXISTS JOB CASCADE;
DROP TABLE IF EXISTS CONFIG CASCADE;
DROP TABLE IF EXISTS CREDENTIAL CASCADE;
DROP TABLE IF EXISTS DHCP_LEASE CASCADE;
DROP TABLE IF EXISTS DHCP_POOL CASCADE;
DROP TABLE IF EXISTS IPAM_ADDRESS CASCADE;
DROP TABLE IF EXISTS IPAM_SUBNET CASCADE;
DROP TABLE IF EXISTS AUDIT CASCADE;
DROP TABLE IF EXISTS APP_USER CASCADE;
DROP TABLE IF EXISTS UNREGISTERED_HOST CASCADE;
DROP TABLE IF EXISTS TEMPLATE CASCADE;
DROP TABLE IF EXISTS INTERFACE CASCADE;
DROP TABLE IF EXISTS DEVICE CASCADE;
DROP TABLE IF EXISTS VLAN CASCADE;

CREATE TABLE IF NOT EXISTS DEVICE (
    id                SERIAL PRIMARY KEY,
    hostname          VARCHAR(64) UNIQUE NOT NULL,
    management_ip     INET UNIQUE NOT NULL,
    device_type       VARCHAR(32) NOT NULL,
    vendor            VARCHAR(32) DEFAULT 'cisco',
    model             VARCHAR(64),
    serial_number     VARCHAR(64),
    os_version        VARCHAR(64),
    role              VARCHAR(32) CHECK (role IN ('core', 'distribution', 'access', 'firewall', 'router', 'server', 'unknown')),
    driver            VARCHAR(32),
    location          VARCHAR(128),
    is_active         BOOLEAN DEFAULT TRUE,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_device_role ON DEVICE(role);


CREATE TABLE IF NOT EXISTS CREDENTIAL (
    id                  SERIAL PRIMARY KEY,
    device_id           INTEGER REFERENCES DEVICE(id) ON DELETE CASCADE,
    credential_type     VARCHAR(16) DEFAULT 'ssh' CHECK (credential_type IN ('ssh', 'telnet', 'snmp', 'api')),
    username            VARCHAR(64),
    password            VARCHAR(256),
    enable_secret       VARCHAR(256),
    snmp_user           VARCHAR(64),
    snmp_auth_protocol  VARCHAR(8),
    snmp_auth_password  VARCHAR(256),
    snmp_priv_protocol  VARCHAR(8),
    snmp_priv_password  VARCHAR(256),
    auth_method         VARCHAR(16) DEFAULT 'local',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(device_id, credential_type)
);

CREATE INDEX idx_credential_device ON CREDENTIAL(device_id);
CREATE INDEX idx_credential_type ON CREDENTIAL(credential_type);

CREATE TABLE IF NOT EXISTS VLAN (
    id              SERIAL PRIMARY KEY,
    vlan_number     INTEGER NOT NULL,
    name            VARCHAR(64),
    description     VARCHAR(256),
    UNIQUE(vlan_number)
);

CREATE TABLE IF NOT EXISTS INTERFACE (
    id              SERIAL PRIMARY KEY,
    device_id       INTEGER NOT NULL REFERENCES DEVICE(id) ON DELETE CASCADE,
    name            VARCHAR(64) NOT NULL,
    description     VARCHAR(128),
    mac_address     MACADDR,
    vlan_id         INTEGER REFERENCES VLAN(id) ON DELETE SET NULL,
    is_trunk        BOOLEAN DEFAULT FALSE,
    is_up           BOOLEAN DEFAULT TRUE,
    speed           VARCHAR(16),
    duplex          VARCHAR(8) CHECK (duplex IN ('full', 'half', 'auto')),
    mtu             INTEGER DEFAULT 1500,
    last_seen       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(device_id, name)
);

CREATE INDEX idx_interface_device ON INTERFACE(device_id);
CREATE INDEX idx_interface_mac ON INTERFACE(mac_address);

CREATE TABLE IF NOT EXISTS CONFIG (
    id              SERIAL PRIMARY KEY,
    device_id       INTEGER NOT NULL REFERENCES DEVICE(id) ON DELETE RESTRICT,
    config_type     VARCHAR(16) DEFAULT 'running' CHECK (config_type IN ('running', 'startup', 'candidate')),
    config_text     TEXT NOT NULL,
    config_hash     VARCHAR(64) NOT NULL,
    collected_at    TIMESTAMPTZ DEFAULT NOW(),
    diff_text       TEXT,                               
    is_acknowledged BOOLEAN DEFAULT FALSE              
);

CREATE INDEX idx_config_device ON CONFIG(device_id);
CREATE INDEX idx_config_collected ON CONFIG(collected_at);
CREATE INDEX idx_config_hash ON CONFIG(config_hash);

CREATE TABLE IF NOT EXISTS TEMPLATE (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(128) UNIQUE NOT NULL,
    description     VARCHAR(256),
    device_type     VARCHAR(32),
    role            VARCHAR(32),
    template_text   TEXT NOT NULL,
    variables       JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS JOB (
    id              SERIAL PRIMARY KEY,
    job_type        VARCHAR(32) NOT NULL,
    status          VARCHAR(16) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    result          JSONB DEFAULT '{}',
    error_message   TEXT
);

CREATE INDEX idx_job_status ON JOB(status);
CREATE INDEX idx_job_type ON JOB(job_type);

CREATE TABLE IF NOT EXISTS JOB_TARGET (
    job_id          INTEGER NOT NULL REFERENCES JOB(id) ON DELETE CASCADE,
    device_id       INTEGER NOT NULL REFERENCES DEVICE(id) ON DELETE CASCADE,
    status          VARCHAR(16) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    PRIMARY KEY(job_id, device_id)
);

CREATE INDEX idx_job_target_job ON JOB_TARGET(job_id);

CREATE TABLE IF NOT EXISTS ALERT (
    id              SERIAL PRIMARY KEY,
    device_id       INTEGER REFERENCES DEVICE(id) ON DELETE SET NULL,
    severity        VARCHAR(16) NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    category        VARCHAR(32) NOT NULL,
    message         TEXT NOT NULL,
    is_resolved     BOOLEAN DEFAULT FALSE,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alert_device ON ALERT(device_id);
CREATE INDEX idx_alert_severity ON ALERT(severity);
CREATE INDEX idx_alert_resolved ON ALERT(is_resolved);

CREATE TABLE IF NOT EXISTS SYSLOG (
    id              SERIAL PRIMARY KEY,
    device_id       INTEGER REFERENCES DEVICE(id) ON DELETE SET NULL,
    source_ip       INET,
    facility        VARCHAR(16),
    severity        INTEGER CHECK (severity BETWEEN 0 AND 7),
    message         TEXT NOT NULL,
    raw_message     TEXT,
    received_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_syslog_device ON SYSLOG(device_id);
CREATE INDEX idx_syslog_received ON SYSLOG(received_at);
CREATE INDEX idx_syslog_severity ON SYSLOG(severity);

CREATE TABLE IF NOT EXISTS IPAM_SUBNET (
    id              SERIAL PRIMARY KEY,
    network         CIDR NOT NULL UNIQUE,
    name            VARCHAR(64),
    gateway         INET,
    vlan_id         INTEGER REFERENCES VLAN(id) ON DELETE SET NULL,
    description     VARCHAR(256)
);

CREATE TABLE IF NOT EXISTS IPAM_ADDRESS (
    id              SERIAL PRIMARY KEY,
    subnet_id       INTEGER NOT NULL REFERENCES IPAM_SUBNET(id) ON DELETE CASCADE,
    ip_address      INET NOT NULL UNIQUE,
    hostname        VARCHAR(64),
    mac_address     MACADDR,
    interface_id    INTEGER REFERENCES INTERFACE(id) ON DELETE SET NULL,
    status          VARCHAR(16) DEFAULT 'active' CHECK (status IN ('active', 'reserved', 'inactive')),
    last_seen       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ipam_addr_subnet ON IPAM_ADDRESS(subnet_id);
CREATE INDEX idx_ipam_addr_ip ON IPAM_ADDRESS(ip_address);

CREATE TABLE IF NOT EXISTS APP_USER (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(64) UNIQUE NOT NULL,
    password_hash   VARCHAR(256) NOT NULL,
    email           VARCHAR(128),
    role            VARCHAR(16) DEFAULT 'viewer' CHECK (role IN ('admin', 'operator', 'viewer')),
    is_active       BOOLEAN DEFAULT TRUE,
    last_login      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS AUDIT (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES APP_USER(id) ON DELETE SET NULL,
    action          VARCHAR(64) NOT NULL,
    target_type     VARCHAR(32),
    target_id       INTEGER,
    details         JSONB DEFAULT '{}',
    ip_address      INET,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON AUDIT(user_id);
CREATE INDEX idx_audit_action ON AUDIT(action);
CREATE INDEX idx_audit_created ON AUDIT(created_at);

CREATE TABLE IF NOT EXISTS DISCOVERY (
    id              SERIAL PRIMARY KEY,
    seed_device_id  INTEGER REFERENCES DEVICE(id) ON DELETE SET NULL,
    method          VARCHAR(16) NOT NULL CHECK (method IN ('cdp', 'lldp', 'snmp', 'manual')),
    status          VARCHAR(16) DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    devices_found   INTEGER DEFAULT 0,
    devices_new     INTEGER DEFAULT 0,
    devices_known   INTEGER DEFAULT 0,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    log             TEXT
);

CREATE INDEX idx_discovery_status ON DISCOVERY(status);

CREATE TABLE IF NOT EXISTS TOPOLOGY_LINK (
    id              SERIAL PRIMARY KEY,
    interface_a_id  INTEGER NOT NULL REFERENCES INTERFACE(id) ON DELETE CASCADE,
    interface_b_id  INTEGER NOT NULL REFERENCES INTERFACE(id) ON DELETE CASCADE,
    link_type       VARCHAR(16) CHECK (link_type IN ('ethernet', 'etherchannel', 'trunk', 'wan')),
    discovered_by   VARCHAR(16) CHECK (discovered_by IN ('cdp', 'lldp', 'snmp', 'manual')),
    is_active       BOOLEAN DEFAULT TRUE,
    bandwidth       VARCHAR(16),
    last_seen       TIMESTAMPTZ DEFAULT NOW(),
    CHECK (interface_a_id < interface_b_id),
    UNIQUE(interface_a_id, interface_b_id)
);

CREATE INDEX idx_topology_interface_a ON TOPOLOGY_LINK(interface_a_id);
CREATE INDEX idx_topology_interface_b ON TOPOLOGY_LINK(interface_b_id);

CREATE TABLE IF NOT EXISTS DHCP_POOL (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(64) NOT NULL,
    network         CIDR NOT NULL,
    range_start     INET NOT NULL,
    range_end       INET NOT NULL,
    gateway         INET,
    dns_server      INET,
    lease_time      INTEGER DEFAULT 86400,
    vlan_id         INTEGER REFERENCES VLAN(id),
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS DHCP_LEASE (
    id              SERIAL PRIMARY KEY,
    pool_id         INTEGER NOT NULL REFERENCES DHCP_POOL(id) ON DELETE CASCADE,
    ip_address      INET NOT NULL,
    mac_address     MACADDR NOT NULL,
    hostname        VARCHAR(64),
    lease_start     TIMESTAMPTZ DEFAULT NOW(),
    lease_end       TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_dhcp_leases_pool ON DHCP_LEASE(pool_id);
CREATE INDEX idx_dhcp_leases_ip ON DHCP_LEASE(ip_address);
CREATE INDEX idx_dhcp_leases_mac ON DHCP_LEASE(mac_address);
CREATE UNIQUE INDEX idx_dhcp_leases_active_ip ON DHCP_LEASE(pool_id, ip_address) WHERE is_active = TRUE;

CREATE TABLE IF NOT EXISTS UNREGISTERED_HOST (
    id                SERIAL PRIMARY KEY,
    ip_address        INET NOT NULL UNIQUE,
    mac_address       MACADDR,
    hostname          VARCHAR(255),
    discovered_by     VARCHAR(32),
    first_seen        TIMESTAMPTZ DEFAULT NOW(),
    last_seen         TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS DEVICE_METRIC (
    id              SERIAL PRIMARY KEY,
    device_id       INTEGER NOT NULL REFERENCES DEVICE(id) ON DELETE CASCADE,
    cpu_percent     NUMERIC(5,2),
    memory_percent  NUMERIC(5,2),
    collected_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS INTERFACE_METRIC (
    id              SERIAL PRIMARY KEY,
    interface_id    INTEGER NOT NULL REFERENCES INTERFACE(id) ON DELETE CASCADE,
    in_bps          BIGINT,
    out_bps         BIGINT,
    utilization_pct NUMERIC(5,2),
    errors_in       BIGINT DEFAULT 0,
    errors_out      BIGINT DEFAULT 0,
    collected_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_devmetric_device_time ON DEVICE_METRIC(device_id, collected_at);
CREATE INDEX idx_ifmetric_iface_time ON INTERFACE_METRIC(interface_id, collected_at);

CREATE TABLE IF NOT EXISTS DEVICE_TEMPLATE_VARS (
    device_id       INTEGER NOT NULL REFERENCES DEVICE(id) ON DELETE CASCADE,
    template_id     INTEGER NOT NULL REFERENCES TEMPLATE(id) ON DELETE CASCADE,
    variables       JSONB DEFAULT '{}',
    rendered_at     TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY(device_id, template_id)
);

CREATE OR REPLACE VIEW V_DEVICE_STATUS AS
SELECT 
    d.id,
    d.hostname,
    d.management_ip,
    d.device_type,
    d.vendor,
    d.model,
    d.role,
    d.is_active,
    c.collected_at AS last_backup,
    c.config_hash AS current_hash
FROM DEVICE d
LEFT JOIN LATERAL (
    SELECT collected_at, config_hash
    FROM CONFIG
    WHERE device_id = d.id
    ORDER BY collected_at DESC
    LIMIT 1
) c ON true;

CREATE OR REPLACE VIEW V_ACTIVE_ALERTS AS
SELECT
    a.id,
    a.severity,
    a.category,
    a.message,
    d.hostname,
    d.management_ip,
    a.created_at
FROM ALERT a
LEFT JOIN DEVICE d ON d.id = a.device_id
WHERE a.is_resolved = FALSE
ORDER BY
    CASE a.severity
        WHEN 'critical' THEN 1
        WHEN 'warning' THEN 2
        WHEN 'info' THEN 3
    END,
    a.created_at DESC;

CREATE OR REPLACE VIEW V_TOPOLOGY AS
SELECT
    tl.id AS link_id,
    da.hostname AS device_a,
    ia.name AS interface_a,
    db.hostname AS device_b,
    ib.name AS interface_b,
    tl.link_type,
    tl.bandwidth,
    tl.is_active,
    tl.last_seen
FROM TOPOLOGY_LINK tl
JOIN INTERFACE ia ON ia.id = tl.interface_a_id
JOIN DEVICE da ON da.id = ia.device_id
JOIN INTERFACE ib ON ib.id = tl.interface_b_id
JOIN DEVICE db ON db.id = ib.device_id;