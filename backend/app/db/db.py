"""DB 接続管理とスキーマ初期化モジュール。"""

import os
from contextlib import contextmanager
from typing import Any, Dict, Generator

import pymysql


def _mysql_config() -> Dict[str, Any]:
    config = {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "canon_milc_info"),
        "charset": "utf8mb4",
        "autocommit": False,
        "cursorclass": pymysql.cursors.DictCursor,
    }
    # Azure Database for MySQL は SSL 接続を要求する
    if os.getenv("MYSQL_SSL", "").lower() == "true":
        config["ssl"] = {"ca": "/etc/ssl/certs/ca-certificates.crt"}
    return config


@contextmanager
def mysql_connection() -> Generator[pymysql.connections.Connection, None, None]:
    conn = pymysql.connect(**_mysql_config())
    try:
        yield conn
    finally:
        conn.close()


def ensure_schema() -> None:
    queries = [
        """
        CREATE TABLE IF NOT EXISTS `groups` (
          group_id INT AUTO_INCREMENT PRIMARY KEY,
          group_name VARCHAR(50) NOT NULL,
          UNIQUE KEY uq_group_name (group_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS `users` (
          group_id INT NOT NULL,
          user_name VARCHAR(50) NOT NULL,
          password_hash VARCHAR(255) NOT NULL,
          PRIMARY KEY (group_id, user_name),
          CONSTRAINT fk_users_group
            FOREIGN KEY (group_id)
            REFERENCES `groups`(group_id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS `payments` (
          payment_id INT AUTO_INCREMENT PRIMARY KEY,
          group_id INT NOT NULL,
          paid_by_user_name VARCHAR(50) NOT NULL,
          title VARCHAR(100) NOT NULL,
          amount_total DECIMAL(12,2) NOT NULL,
          currency_code CHAR(3) NOT NULL,
          exchange_rate DECIMAL(10,4) NOT NULL,
          payment_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT fk_payments_group
            FOREIGN KEY (group_id)
            REFERENCES `groups`(group_id)
            ON DELETE CASCADE,
          CONSTRAINT fk_payments_paid_by
            FOREIGN KEY (group_id, paid_by_user_name)
            REFERENCES `users`(group_id, user_name)
            ON DELETE CASCADE
            ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS `payment_splits` (
          payment_id INT NOT NULL,
          group_id INT NOT NULL,
          beneficiary_user_name VARCHAR(50) NOT NULL,
          amount DECIMAL(12,2) NOT NULL,
          approved BOOLEAN NOT NULL DEFAULT FALSE,
          PRIMARY KEY (payment_id, beneficiary_user_name),
          CONSTRAINT fk_splits_payment
            FOREIGN KEY (payment_id)
            REFERENCES `payments`(payment_id)
            ON DELETE CASCADE,
          CONSTRAINT fk_splits_beneficiary
            FOREIGN KEY (group_id, beneficiary_user_name)
            REFERENCES `users`(group_id, user_name)
            ON DELETE CASCADE
            ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
    ]
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            for q in queries:
                cur.execute(q)
        conn.commit()