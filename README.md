# College Canteen Food Pre-Order Management System

A complete web-based canteen management system built with **Python Flask** and **MySQL**.

## Features

- **Admin Login** with secure password hashing (werkzeug)
- **Dashboard** with live stats, today's orders, revenue chart, low stock alerts
- **Menu Management** — add/edit/delete items, toggle availability, category filter
- **Student Management** — full profiles, order history, prepaid balance
- **Order Management** — place orders, track status (pending → preparing → ready → delivered)
- **Payments** — mark as paid, monthly filter, revenue summary
- **Reports** — category-wise sales, top items, top students, date range filter
- **Notices** — post and manage canteen notices
- **Settings** — change password, canteen name, opening/closing times

## Quick Start

### 1. Install dependencies
```
pip install -r requirements.txt
```

### 2. Configure database
Copy `.env.example` to `.env` and fill in your MySQL credentials:
```
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=yourpassword
MYSQL_DB=canteen_db
SECRET_KEY=your-secret-key
```

### 3. Set up the database
```
python setup_db.py
```

### 4. Run the app
```
python app.py
```

Open http://localhost:5000 in your browser.

## Default Login
- **Email:** admin@canteen.com
- **Password:** admin123

## File Structure
```
app.py              — Main Flask application
setup_db.py         — Database setup script (run once)
schema.sql          — SQL schema reference
requirements.txt    — Python dependencies
.env                — Environment variables (not committed)
templates/          — Jinja2 HTML templates
static/css/         — Custom CSS
static/js/          — JavaScript
```

## Tech Stack
- **Backend:** Python 3, Flask, Flask-Login, Flask-MySQLdb
- **Database:** MySQL
- **Frontend:** Bootstrap 5, Bootstrap Icons
- **Security:** Werkzeug password hashing, parameterized SQL queries
