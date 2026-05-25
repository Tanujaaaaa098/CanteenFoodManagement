"""
Run this script ONCE to set up the database and create the default admin.
Usage: python setup_db.py
"""
import os
try:
    import MySQLdb
except ImportError:
    import pymysql
    pymysql.install_as_MySQLdb()
    import MySQLdb
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv('MYSQL_HOST', 'localhost')
USER = os.getenv('MYSQL_USER', 'root')
PASSWORD = os.getenv('MYSQL_PASSWORD', '')
DB = os.getenv('MYSQL_DB', 'canteen_db')

print(f"Connecting to MySQL at {HOST} as {USER}...")

# Connect without DB first to create it
conn = MySQLdb.connect(host=HOST, user=USER, passwd=PASSWORD)
cur = conn.cursor()
cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
conn.commit()
cur.close()
conn.close()
print(f"Database '{DB}' ready.")

# Now connect to the DB and run schema
conn = MySQLdb.connect(host=HOST, user=USER, passwd=PASSWORD, db=DB)
cur = conn.cursor()

# Create tables
tables = [
    """CREATE TABLE IF NOT EXISTS admins (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(150) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS menu_items (
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
    )""",
    """CREATE TABLE IF NOT EXISTS students (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        roll_number VARCHAR(50) UNIQUE NOT NULL,
        branch VARCHAR(100),
        year INT,
        phone VARCHAR(20),
        email VARCHAR(150),
        prepaid_balance DECIMAL(10,2) DEFAULT 0.00,
        created_date DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS orders (
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
    )""",
    """CREATE TABLE IF NOT EXISTS order_items (
        id INT AUTO_INCREMENT PRIMARY KEY,
        order_id INT NOT NULL,
        menu_item_id INT NOT NULL,
        quantity INT NOT NULL,
        unit_price DECIMAL(10,2) NOT NULL,
        subtotal DECIMAL(10,2) NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS payments (
        id INT AUTO_INCREMENT PRIMARY KEY,
        order_id INT NOT NULL,
        student_id INT NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        payment_method ENUM('cash','prepaid') DEFAULT 'cash',
        payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        status ENUM('paid','pending') DEFAULT 'pending',
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS notices (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(200) NOT NULL,
        message TEXT NOT NULL,
        posted_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        admin_id INT NOT NULL,
        FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS settings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        `key` VARCHAR(100) UNIQUE NOT NULL,
        value TEXT
    )"""
]

for sql in tables:
    cur.execute(sql)
    print(f"  Table created/verified.")

conn.commit()

# Insert default admin
pw_hash = generate_password_hash('admin123')
cur.execute("SELECT id FROM admins WHERE email='admin@canteen.com'")
if not cur.fetchone():
    cur.execute("INSERT INTO admins (name, email, password_hash) VALUES (%s, %s, %s)",
                ('Admin', 'admin@canteen.com', pw_hash))
    print("Default admin created: admin@canteen.com / admin123")
else:
    cur.execute("UPDATE admins SET password_hash=%s WHERE email='admin@canteen.com'", (pw_hash,))
    print("Default admin password reset to: admin123")

# Default settings
settings_data = [
    ('canteen_name', 'College Canteen'),
    ('college_name', 'Engineering College'),
    ('opening_time', '08:00'),
    ('closing_time', '20:00'),
]
for k, v in settings_data:
    cur.execute("INSERT INTO settings (`key`, value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `key`=`key`", (k, v))

# Sample menu items
cur.execute("SELECT COUNT(*) as cnt FROM menu_items")
if cur.fetchone()[0] == 0:
    menu_data = [
        ('Idli Sambar', 'Breakfast', 30.00, 'Soft idlis with sambar and chutney', 50, '08:00', '11:00'),
        ('Poha', 'Breakfast', 25.00, 'Flattened rice with spices', 40, '08:00', '11:00'),
        ('Veg Thali', 'Lunch', 80.00, 'Full meal with rice, dal, sabzi, roti', 30, '12:00', '15:00'),
        ('Chicken Biryani', 'Lunch', 120.00, 'Aromatic basmati rice with chicken', 20, '12:00', '15:00'),
        ('Samosa', 'Snacks', 15.00, 'Crispy fried pastry with potato filling', 60, '10:00', '18:00'),
        ('Vada Pav', 'Snacks', 20.00, 'Mumbai style vada pav', 50, '10:00', '18:00'),
        ('Tea', 'Beverages', 10.00, 'Hot masala tea', 100, '08:00', '20:00'),
        ('Cold Coffee', 'Beverages', 40.00, 'Chilled coffee with milk', 30, '10:00', '20:00'),
        ('Paneer Sandwich', 'Snacks', 45.00, 'Grilled paneer sandwich', 25, '09:00', '18:00'),
        ('Lassi', 'Beverages', 35.00, 'Sweet or salted yogurt drink', 20, '10:00', '18:00'),
    ]
    for item in menu_data:
        cur.execute("""INSERT INTO menu_items (name,category,price,description,available_quantity,available_from,available_to)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""", item)
    print(f"Inserted {len(menu_data)} sample menu items.")

# Sample students
cur.execute("SELECT COUNT(*) as cnt FROM students")
if cur.fetchone()[0] == 0:
    students_data = [
        ('Priya Sharma', 'AM2201', 'Computer Science', 2, '9876543210', 'priya@college.edu', 200.00),
        ('Rahul Verma', 'AM2202', 'Electronics', 2, '9876543211', 'rahul@college.edu', 150.00),
        ('Sneha Patel', 'AM2203', 'Mechanical', 3, '9876543212', 'sneha@college.edu', 0.00),
        ('Amit Kumar', 'AM2204', 'Civil', 1, '9876543213', 'amit@college.edu', 500.00),
        ('Tanuja Kale', 'AM2207', 'Computer Science', 2, '9876543214', 'tanuja@college.edu', 300.00),
    ]
    for s in students_data:
        cur.execute("""INSERT INTO students (name,roll_number,branch,year,phone,email,prepaid_balance)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""", s)
    print(f"Inserted {len(students_data)} sample students.")

conn.commit()
cur.close()
conn.close()
print("\n✅ Setup complete! Run: python app.py")
print("   Login: admin@canteen.com / admin123")
