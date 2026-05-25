-- College Canteen Food Pre-Order Management System
-- Database Schema

CREATE DATABASE IF NOT EXISTS canteen_db;
USE canteen_db;

-- Admins table
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Menu Items table
CREATE TABLE IF NOT EXISTS menu_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    category ENUM('Breakfast','Lunch','Snacks','Beverages') NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    description TEXT,
    available_quantity INT DEFAULT 0,
    available_from TIME,
    available_to TIME,
    status ENUM('available','unavailable') DEFAULT 'available',
    created_date DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Students table
CREATE TABLE IF NOT EXISTS students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    roll_number VARCHAR(50) UNIQUE NOT NULL,
    branch VARCHAR(100),
    year INT,
    phone VARCHAR(20),
    email VARCHAR(150),
    prepaid_balance DECIMAL(10,2) DEFAULT 0.00,
    created_date DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    order_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    pickup_time VARCHAR(50),
    total_amount DECIMAL(10,2) DEFAULT 0.00,
    payment_method ENUM('cash','prepaid') DEFAULT 'cash',
    payment_status ENUM('paid','pending') DEFAULT 'pending',
    order_status ENUM('pending','preparing','ready','delivered') DEFAULT 'pending',
    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);

-- Order Items table
CREATE TABLE IF NOT EXISTS order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    menu_item_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE CASCADE
);

-- Payments table
CREATE TABLE IF NOT EXISTS payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    student_id INT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    payment_method ENUM('cash','prepaid') DEFAULT 'cash',
    payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('paid','pending') DEFAULT 'pending',
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);

-- Notices table
CREATE TABLE IF NOT EXISTS notices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    posted_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    admin_id INT NOT NULL,
    FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE CASCADE
);

-- Settings table
CREATE TABLE IF NOT EXISTS settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    `key` VARCHAR(100) UNIQUE NOT NULL,
    value TEXT
);

-- Default admin: admin@canteen.com / admin123
-- Password hash generated with werkzeug pbkdf2:sha256
INSERT INTO admins (name, email, password_hash) VALUES
('Admin', 'admin@canteen.com', 'pbkdf2:sha256:600000$rJ8kL2mN$a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2')
ON DUPLICATE KEY UPDATE email=email;

-- Default settings
INSERT INTO settings (`key`, value) VALUES
('canteen_name', 'College Canteen'),
('college_name', 'Engineering College'),
('opening_time', '08:00'),
('closing_time', '20:00')
ON DUPLICATE KEY UPDATE `key`=`key`;

-- Sample menu items
INSERT INTO menu_items (name, category, price, description, available_quantity, available_from, available_to, status) VALUES
('Idli Sambar', 'Breakfast', 30.00, 'Soft idlis with sambar and chutney', 50, '08:00', '11:00', 'available'),
('Poha', 'Breakfast', 25.00, 'Flattened rice with spices', 40, '08:00', '11:00', 'available'),
('Veg Thali', 'Lunch', 80.00, 'Full meal with rice, dal, sabzi, roti', 30, '12:00', '15:00', 'available'),
('Chicken Biryani', 'Lunch', 120.00, 'Aromatic basmati rice with chicken', 20, '12:00', '15:00', 'available'),
('Samosa', 'Snacks', 15.00, 'Crispy fried pastry with potato filling', 60, '10:00', '18:00', 'available'),
('Vada Pav', 'Snacks', 20.00, 'Mumbai style vada pav', 50, '10:00', '18:00', 'available'),
('Tea', 'Beverages', 10.00, 'Hot masala tea', 100, '08:00', '20:00', 'available'),
('Cold Coffee', 'Beverages', 40.00, 'Chilled coffee with milk', 30, '10:00', '20:00', 'available'),
('Paneer Sandwich', 'Snacks', 45.00, 'Grilled paneer sandwich', 25, '09:00', '18:00', 'available'),
('Lassi', 'Beverages', 35.00, 'Sweet or salted yogurt drink', 20, '10:00', '18:00', 'available');

-- Sample students
INSERT INTO students (name, roll_number, branch, year, phone, email, prepaid_balance) VALUES
('Priya Sharma', 'AM2201', 'Computer Science', 2, '9876543210', 'priya@college.edu', 200.00),
('Rahul Verma', 'AM2202', 'Electronics', 2, '9876543211', 'rahul@college.edu', 150.00),
('Sneha Patel', 'AM2203', 'Mechanical', 3, '9876543212', 'sneha@college.edu', 0.00),
('Amit Kumar', 'AM2204', 'Civil', 1, '9876543213', 'amit@college.edu', 500.00),
('Tanuja Kale', 'AM2207', 'Computer Science', 2, '9876543214', 'tanuja@college.edu', 300.00);
