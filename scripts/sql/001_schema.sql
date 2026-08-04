CREATE DATABASE IF NOT EXISTS nebula_shop CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE nebula_shop;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(64) NOT NULL UNIQUE,
  email VARCHAR(255) NOT NULL,
  status VARCHAR(20) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  last_login_at DATETIME(6) NULL
);
CREATE TABLE IF NOT EXISTS orders (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  order_no VARCHAR(32) NOT NULL UNIQUE,
  amount DECIMAL(12,2) NOT NULL,
  status VARCHAR(20) NOT NULL,
  error_code VARCHAR(32) NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  version INT NOT NULL DEFAULT 1,
  note TEXT NULL,
  cancel_reason VARCHAR(500) NULL,
  created_by VARCHAR(36) NULL,
  updated_by VARCHAR(36) NULL,
  INDEX idx_orders_status_created (status, created_at),
  CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS test_runs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  request_id VARCHAR(64) NOT NULL,
  test_target VARCHAR(255) NOT NULL,
  total_count INT NOT NULL,
  passed_count INT NOT NULL,
  failed_count INT NOT NULL,
  output TEXT,
  created_at DATETIME(6) NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_traces (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  request_id VARCHAR(64) NOT NULL,
  step_index INT NOT NULL,
  node_name VARCHAR(64) NOT NULL,
  tool_name VARCHAR(64),
  tool_arguments JSON,
  tool_result JSON,
  status VARCHAR(20) NOT NULL,
  error_message TEXT,
  started_at DATETIME(6) NOT NULL,
  finished_at DATETIME(6) NOT NULL,
  duration_ms INT NOT NULL,
  INDEX idx_trace_request (request_id, step_index)
);
