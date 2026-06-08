DROP DATABASE IF EXISTS lazarus_db;

CREATE DATABASE lazarus_db;
USE lazarus_db;

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
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
    node_status ENUM('active', 'inactive') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE files (
    file_id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    file_type VARCHAR(100),
    total_fragments INT NOT NULL,
    required_fragments INT NOT NULL,
    file_status ENUM('uploaded', 'pending_processing', 'processed', 'deleted') DEFAULT 'uploaded',
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(user_id)
);

CREATE TABLE fragments (
    fragment_id INT AUTO_INCREMENT PRIMARY KEY,
    file_id INT NOT NULL,
    node_id INT NOT NULL,
    fragment_number INT NOT NULL,
    fragment_path VARCHAR(255) NOT NULL,
    fragment_status ENUM('available', 'missing', 'deleted') DEFAULT 'available',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files(file_id),
    FOREIGN KEY (node_id) REFERENCES storage_nodes(node_id)
);

CREATE TABLE share_links (
    share_id INT AUTO_INCREMENT PRIMARY KEY,
    file_id INT NOT NULL,
    created_by INT NOT NULL,
    recipient_id INT NULL,
    share_token VARCHAR(255) NOT NULL UNIQUE,
    is_one_time BOOLEAN DEFAULT FALSE,
    expiry_datetime DATETIME NULL,
    link_status ENUM('active', 'expired', 'revoked', 'used') DEFAULT 'active',
    used_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files(file_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    FOREIGN KEY (recipient_id) REFERENCES users(user_id)
);

INSERT INTO users
(full_name, username, email, password_hash, role, account_status)
VALUES
('Demo User', 'demo', 'demo@example.com', 'temporary_hash', 'user', 'active'),
('John Smith', 'johnsmith', 'john@example.com', 'temporary_hash', 'user', 'active'),
('Admin User', 'admin', 'admin@example.com', 'temporary_hash', 'user_admin', 'active'),
('System Administrator', 'sysadmin', 'sysadmin@example.com', 'temporary_hash', 'system_admin', 'active');

INSERT INTO storage_nodes
(node_name, node_path, node_status)
VALUES
('Node 1', 'storage_nodes/node1/', 'active'),
('Node 2', 'storage_nodes/node2/', 'active'),
('Node 3', 'storage_nodes/node3/', 'active'),
('Node 4', 'storage_nodes/node4/', 'active'),
('Node 5', 'storage_nodes/node5/', 'active');

SELECT * FROM users;
SELECT * FROM storage_nodes;