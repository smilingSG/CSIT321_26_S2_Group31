DROP DATABASE IF EXISTS lazarus_db;

CREATE DATABASE lazarus_db;
USE lazarus_db;

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('user', 'user_admin', 'system_admin') DEFAULT 'user',
    account_status ENUM('active', 'suspended', 'deleted') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE storage_nodes (
    node_id INT AUTO_INCREMENT PRIMARY KEY,
    node_name VARCHAR(50) NOT NULL,
    node_path VARCHAR(255) NOT NULL,
    node_status ENUM('active', 'inactive') DEFAULT 'active'
);

CREATE TABLE files (
    file_id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL,

    file_name VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,

    file_size BIGINT NOT NULL,
    file_type VARCHAR(100),

    temp_upload_path VARCHAR(255) NULL,
    encrypted_temp_path VARCHAR(255) NULL,

    nonce VARBINARY(12) NULL,
    encrypted_file_key VARBINARY(512) NULL,
    encrypted_size BIGINT NULL,

    total_fragments INT NULL,
    required_fragments INT NULL,

    file_status ENUM(
        'pending_confirmation',
        'pending_processing',
        'encrypted',
        'processed',
        'cancelled',
        'deleted',
        'failed'
    ) DEFAULT 'pending_confirmation',

    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (owner_id) REFERENCES users(user_id)
);

CREATE TABLE upload_sessions (
    upload_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    file_id INT NULL,

    file_name VARCHAR(255) NOT NULL,
    temp_upload_path VARCHAR(255) NOT NULL,

    total_size BIGINT NOT NULL,
    bytes_uploaded BIGINT DEFAULT 0,

    upload_status ENUM(
        'paused',
        'uploading',
        'completed',
        'cancelled',
        'failed'
    ) DEFAULT 'paused',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (file_id) REFERENCES files(file_id),

    UNIQUE (file_id)
);

CREATE TABLE fragments (
    fragment_id INT AUTO_INCREMENT PRIMARY KEY,
    file_id INT NOT NULL,
    node_id INT NOT NULL,
    fragment_number INT NOT NULL,
    fragment_path VARCHAR(255) NOT NULL,
    fragment_status ENUM('available', 'missing', 'deleted') DEFAULT 'available',

    FOREIGN KEY (file_id) REFERENCES files(file_id),
    FOREIGN KEY (node_id) REFERENCES storage_nodes(node_id),

    UNIQUE (file_id, fragment_number)
);

CREATE TABLE share_links (
    share_id INT AUTO_INCREMENT PRIMARY KEY,
    file_id INT NOT NULL,
    created_by INT NOT NULL,
    recipient_id INT NOT NULL,

    share_token VARCHAR(255) NOT NULL UNIQUE,
    is_one_time BOOLEAN DEFAULT FALSE,
    expiry_datetime DATETIME NULL,
    link_status ENUM('active', 'expired', 'revoked', 'used') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (file_id) REFERENCES files(file_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    FOREIGN KEY (recipient_id) REFERENCES users(user_id)
);

CREATE TABLE system_settings (
    setting_id INT AUTO_INCREMENT PRIMARY KEY,
    setting_name VARCHAR(100) NOT NULL UNIQUE,
    setting_value VARCHAR(255) NOT NULL,
    updated_by INT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (updated_by) REFERENCES users(user_id)
);

INSERT INTO users
(username, email, password_hash, role, account_status)
VALUES
('demo', 'demo@example.com', 'temporary_hash', 'user', 'active'),
('johnsmith', 'john@example.com', 'temporary_hash', 'user', 'active'),
('admin', 'admin@example.com', 'temporary_hash', 'user_admin', 'active'),
('sysadmin', 'sysadmin@example.com', 'temporary_hash', 'system_admin', 'active');

INSERT INTO storage_nodes
(node_name, node_path, node_status)
VALUES
('Node 1', 'storage_nodes/node1/', 'active'),
('Node 2', 'storage_nodes/node2/', 'active'),
('Node 3', 'storage_nodes/node3/', 'active'),
('Node 4', 'storage_nodes/node4/', 'active'),
('Node 5', 'storage_nodes/node5/', 'active');

INSERT INTO system_settings
(setting_name, setting_value, updated_by)
VALUES
('max_link_expiry_hours', '72', 4),
('min_password_length', '8', 4),
('require_password_special_character', 'true', 4),
('min_username_length', '4', 4),
('max_login_attempts', '5', 4);