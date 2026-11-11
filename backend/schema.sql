CREATE DATABASE IF NOT EXISTS shopdb CHARACTER SET utf8mb4;
USE shopdb;

CREATE TABLE IF NOT EXISTS products (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  description VARCHAR(500) NOT NULL DEFAULT '',
  price DECIMAL(10,2) NOT NULL,
  stock INT NOT NULL DEFAULT 0,
  emoji VARCHAR(8) NOT NULL DEFAULT '📦',
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CHECK (price >= 0), CHECK (stock >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_name VARCHAR(120) NOT NULL,
  customer_email VARCHAR(200) NOT NULL,
  total DECIMAL(10,2) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'PLACED',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  product_id INT NOT NULL,
  quantity INT NOT NULL,
  unit_price DECIMAL(10,2) NOT NULL,
  FOREIGN KEY (order_id) REFERENCES orders(id),
  FOREIGN KEY (product_id) REFERENCES products(id)
);

INSERT INTO products (name, description, price, stock, emoji) VALUES
 ('Wireless Mouse', 'Compact 2.4GHz mouse', 599.00, 25, '🖱️'),
 ('Mechanical Keyboard', 'Blue-switch keyboard', 2499.00, 10, '⌨️'),
 ('USB-C Hub', '6-in-1 hub with HDMI', 1799.00, 15, '🔌');
