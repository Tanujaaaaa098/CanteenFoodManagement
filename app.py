import os
try:
    import MySQLdb
except ImportError:
    import pymysql
    pymysql.install_as_MySQLdb()

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_mysqldb import MySQL
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime, date, timedelta
import MySQLdb.cursors

load_dotenv()

app = Flask(__name__)

# ── Jinja2 filter: format TIME columns (PyMySQL returns timedelta) ────────────
@app.template_filter('fmt_time')
def fmt_time(value):
    if value is None:
        return ''
    from datetime import timedelta, time
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        h, m = divmod(total // 60, 60)
        return f'{h:02d}:{m:02d}'
    if isinstance(value, time):
        return value.strftime('%H:%M')
    return str(value)
app.secret_key = os.getenv('SECRET_KEY', 'canteen-secret-key')

# MySQL config — supports Railway's MYSQLDATABASE_URL or individual vars
app.config['MYSQL_HOST'] = os.getenv('MYSQLHOST') or os.getenv('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.getenv('MYSQLUSER') or os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQLPASSWORD') or os.getenv('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = os.getenv('MYSQLDATABASE') or os.getenv('MYSQL_DB', 'canteen_db')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQLPORT') or os.getenv('MYSQL_PORT', 3306))
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

# ── User model ──────────────────────────────────────────────────────────────
class Admin(UserMixin):
    def __init__(self, id, name, email):
        self.id = id
        self.name = name
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM admins WHERE id = %s", (user_id,))
    admin = cur.fetchone()
    cur.close()
    if admin:
        return Admin(admin['id'], admin['name'], admin['email'])
    return None

# ── Helper ───────────────────────────────────────────────────────────────────
def get_settings():
    cur = mysql.connection.cursor()
    cur.execute("SELECT `key`, value FROM settings")
    rows = cur.fetchall()
    cur.close()
    return {r['key']: r['value'] for r in rows}

def get_low_stock_items():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM menu_items WHERE available_quantity < 5 AND status='available'")
    items = cur.fetchall()
    cur.close()
    return items

# ── Auth ─────────────────────────────────────────────────────────────────────
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM admins WHERE email = %s", (email,))
        admin = cur.fetchone()
        cur.close()
        if admin and check_password_hash(admin['password_hash'], password):
            user = Admin(admin['id'], admin['name'], admin['email'])
            login_user(user)
            flash(f"Welcome back, {admin['name']}!", 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# ── Dashboard ────────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    cur = mysql.connection.cursor()
    today = date.today().strftime('%Y-%m-%d')

    cur.execute("SELECT COUNT(*) as cnt FROM menu_items")
    total_menu = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM orders WHERE DATE(created_date)=%s", (today,))
    orders_today = cur.fetchone()['cnt']

    cur.execute("""SELECT COALESCE(SUM(p.amount),0) as rev FROM payments p
                   WHERE DATE(p.payment_date)=%s AND p.status='paid'""", (today,))
    revenue_today = cur.fetchone()['rev']

    cur.execute("""SELECT COUNT(*) as cnt FROM payments WHERE status='pending'""")
    pending_payments = cur.fetchone()['cnt']

    cur.execute("""SELECT o.id, s.name as student_name, o.total_amount,
                          o.payment_status, o.order_status, o.order_time
                   FROM orders o JOIN students s ON o.student_id=s.id
                   WHERE DATE(o.created_date)=%s ORDER BY o.order_time DESC""", (today,))
    today_orders = cur.fetchall()

    for o in today_orders:
        cur.execute("""SELECT mi.name, oi.quantity FROM order_items oi
                       JOIN menu_items mi ON oi.menu_item_id=mi.id
                       WHERE oi.order_id=%s""", (o['id'],))
        o['items'] = cur.fetchall()

    cur.execute("""SELECT mi.name, SUM(oi.quantity) as total_qty
                   FROM order_items oi JOIN menu_items mi ON oi.menu_item_id=mi.id
                   JOIN orders o ON oi.order_id=o.id
                   WHERE DATE(o.created_date)=%s
                   GROUP BY mi.id ORDER BY total_qty DESC LIMIT 1""", (today,))
    most_ordered = cur.fetchone()

    low_stock = get_low_stock_items()

    week_revenue = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).strftime('%Y-%m-%d')
        cur.execute("""SELECT COALESCE(SUM(amount),0) as rev FROM payments
                       WHERE DATE(payment_date)=%s AND status='paid'""", (d,))
        rev = cur.fetchone()['rev']
        week_revenue.append({'day': (date.today() - timedelta(days=i)).strftime('%a'), 'revenue': float(rev)})

    cur.execute("SELECT * FROM notices ORDER BY posted_date DESC LIMIT 3")
    latest_notices = cur.fetchall()
    cur.close()

    settings = get_settings()
    return render_template('dashboard.html',
        total_menu=total_menu, orders_today=orders_today,
        revenue_today=revenue_today, pending_payments=pending_payments,
        today_orders=today_orders, most_ordered=most_ordered,
        low_stock=low_stock, week_revenue=week_revenue,
        latest_notices=latest_notices, settings=settings)

# ── Menu ─────────────────────────────────────────────────────────────────────
@app.route('/menu')
@login_required
def menu():
    search = request.args.get('search', '')
    category = request.args.get('category', 'All')
    cur = mysql.connection.cursor()
    query = "SELECT * FROM menu_items WHERE 1=1"
    params = []
    if search:
        query += " AND (name LIKE %s OR category LIKE %s)"
        params += [f'%{search}%', f'%{search}%']
    if category and category != 'All':
        query += " AND category = %s"
        params.append(category)
    query += " ORDER BY category, name"
    cur.execute(query, params)
    items = cur.fetchall()
    cur.close()
    settings = get_settings()
    return render_template('menu.html', items=items, search=search,
                           category=category, settings=settings, low_stock=get_low_stock_items())

@app.route('/menu/add', methods=['GET', 'POST'])
@login_required
def add_menu_item():
    if request.method == 'POST':
        name = request.form['name'].strip()
        category = request.form['category']
        price = float(request.form['price'])
        description = request.form.get('description', '')
        qty = int(request.form.get('available_quantity', 0))
        avail_from = request.form.get('available_from', '')
        avail_to = request.form.get('available_to', '')
        status = 'available' if qty > 0 else 'unavailable'
        cur = mysql.connection.cursor()
        cur.execute("""INSERT INTO menu_items (name,category,price,description,
                       available_quantity,available_from,available_to,status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (name, category, price, description, qty, avail_from, avail_to, status))
        mysql.connection.commit()
        cur.close()
        flash('Menu item added successfully!', 'success')
        return redirect(url_for('menu'))
    settings = get_settings()
    return render_template('add_menu_item.html', settings=settings, low_stock=get_low_stock_items())

@app.route('/menu/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_menu_item(item_id):
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        name = request.form['name'].strip()
        category = request.form['category']
        price = float(request.form['price'])
        description = request.form.get('description', '')
        qty = int(request.form.get('available_quantity', 0))
        avail_from = request.form.get('available_from', '')
        avail_to = request.form.get('available_to', '')
        status = request.form.get('status', 'available')
        cur.execute("""UPDATE menu_items SET name=%s,category=%s,price=%s,description=%s,
                       available_quantity=%s,available_from=%s,available_to=%s,status=%s
                       WHERE id=%s""",
                    (name, category, price, description, qty, avail_from, avail_to, status, item_id))
        mysql.connection.commit()
        cur.close()
        flash('Menu item updated!', 'success')
        return redirect(url_for('menu'))
    cur.execute("SELECT * FROM menu_items WHERE id=%s", (item_id,))
    item = cur.fetchone()
    cur.close()
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('menu'))
    settings = get_settings()
    return render_template('edit_menu_item.html', item=item, settings=settings, low_stock=get_low_stock_items())

@app.route('/menu/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_menu_item(item_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM menu_items WHERE id=%s", (item_id,))
    mysql.connection.commit()
    cur.close()
    flash('Menu item deleted.', 'success')
    return redirect(url_for('menu'))

@app.route('/menu/toggle/<int:item_id>', methods=['POST'])
@login_required
def toggle_menu_item(item_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT status FROM menu_items WHERE id=%s", (item_id,))
    item = cur.fetchone()
    if item:
        new_status = 'unavailable' if item['status'] == 'available' else 'available'
        cur.execute("UPDATE menu_items SET status=%s WHERE id=%s", (new_status, item_id))
        mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})

# ── Students ──────────────────────────────────────────────────────────────────
@app.route('/students')
@login_required
def students():
    search = request.args.get('search', '')
    cur = mysql.connection.cursor()
    if search:
        cur.execute("""SELECT s.*, COUNT(o.id) as total_orders,
                       COALESCE(SUM(CASE WHEN o.payment_status='pending' THEN o.total_amount ELSE 0 END),0) as pending_balance
                       FROM students s LEFT JOIN orders o ON s.id=o.student_id
                       WHERE s.name LIKE %s OR s.roll_number LIKE %s
                       GROUP BY s.id ORDER BY s.name""",
                    (f'%{search}%', f'%{search}%'))
    else:
        cur.execute("""SELECT s.*, COUNT(o.id) as total_orders,
                       COALESCE(SUM(CASE WHEN o.payment_status='pending' THEN o.total_amount ELSE 0 END),0) as pending_balance
                       FROM students s LEFT JOIN orders o ON s.id=o.student_id
                       GROUP BY s.id ORDER BY s.name""")
    students_list = cur.fetchall()
    cur.close()
    settings = get_settings()
    return render_template('students.html', students=students_list, search=search,
                           settings=settings, low_stock=get_low_stock_items())

@app.route('/students/add', methods=['GET', 'POST'])
@login_required
def add_student():
    if request.method == 'POST':
        name = request.form['name'].strip()
        roll = request.form['roll_number'].strip()
        branch = request.form.get('branch', '')
        year = request.form.get('year', 1)
        phone = request.form.get('phone', '')
        email = request.form.get('email', '')
        balance = float(request.form.get('prepaid_balance', 0))
        cur = mysql.connection.cursor()
        try:
            cur.execute("""INSERT INTO students (name,roll_number,branch,year,phone,email,prepaid_balance)
                           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                        (name, roll, branch, year, phone, email, balance))
            mysql.connection.commit()
            flash('Student added successfully!', 'success')
            return redirect(url_for('students'))
        except Exception as e:
            flash(f'Error: Roll number may already exist.', 'danger')
        finally:
            cur.close()
    settings = get_settings()
    return render_template('add_student.html', settings=settings, low_stock=get_low_stock_items())

@app.route('/students/<int:student_id>')
@login_required
def student_detail(student_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM students WHERE id=%s", (student_id,))
    student = cur.fetchone()
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('students'))
    cur.execute("""SELECT o.*, GROUP_CONCAT(mi.name ORDER BY mi.name SEPARATOR ', ') as items_list
                   FROM orders o
                   LEFT JOIN order_items oi ON o.id=oi.order_id
                   LEFT JOIN menu_items mi ON oi.menu_item_id=mi.id
                   WHERE o.student_id=%s GROUP BY o.id ORDER BY o.created_date DESC""", (student_id,))
    order_history = cur.fetchall()
    cur.execute("SELECT COALESCE(SUM(total_amount),0) as total_spent FROM orders WHERE student_id=%s AND payment_status='paid'", (student_id,))
    total_spent = cur.fetchone()['total_spent']
    cur.execute("SELECT COALESCE(SUM(total_amount),0) as total_pending FROM orders WHERE student_id=%s AND payment_status='pending'", (student_id,))
    total_pending = cur.fetchone()['total_pending']
    cur.close()
    settings = get_settings()
    return render_template('student_detail.html', student=student, order_history=order_history,
                           total_spent=total_spent, total_pending=total_pending,
                           settings=settings, low_stock=get_low_stock_items())

@app.route('/students/edit/<int:student_id>', methods=['POST'])
@login_required
def edit_student(student_id):
    name = request.form['name'].strip()
    branch = request.form.get('branch', '')
    year = request.form.get('year', 1)
    phone = request.form.get('phone', '')
    email = request.form.get('email', '')
    balance = float(request.form.get('prepaid_balance', 0))
    cur = mysql.connection.cursor()
    cur.execute("""UPDATE students SET name=%s,branch=%s,year=%s,phone=%s,email=%s,prepaid_balance=%s
                   WHERE id=%s""", (name, branch, year, phone, email, balance, student_id))
    mysql.connection.commit()
    cur.close()
    flash('Student updated!', 'success')
    return redirect(url_for('student_detail', student_id=student_id))

@app.route('/students/delete/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM students WHERE id=%s", (student_id,))
    mysql.connection.commit()
    cur.close()
    flash('Student deleted.', 'success')
    return redirect(url_for('students'))

# ── Orders ────────────────────────────────────────────────────────────────────
@app.route('/orders')
@login_required
def orders():
    period = request.args.get('period', 'today')
    status_filter = request.args.get('status', 'All')
    cur = mysql.connection.cursor()
    today = date.today().strftime('%Y-%m-%d')
    week_start = (date.today() - timedelta(days=date.today().weekday())).strftime('%Y-%m-%d')

    query = """SELECT o.*, s.name as student_name, s.roll_number
               FROM orders o JOIN students s ON o.student_id=s.id WHERE 1=1"""
    params = []
    if period == 'today':
        query += " AND DATE(o.created_date)=%s"
        params.append(today)
    elif period == 'week':
        query += " AND DATE(o.created_date)>=%s"
        params.append(week_start)
    if status_filter != 'All':
        query += " AND o.order_status=%s"
        params.append(status_filter.lower())
    query += " ORDER BY o.created_date DESC"
    cur.execute(query, params)
    orders_list = cur.fetchall()
    for o in orders_list:
        cur.execute("""SELECT mi.name, oi.quantity, oi.unit_price, oi.subtotal
                       FROM order_items oi JOIN menu_items mi ON oi.menu_item_id=mi.id
                       WHERE oi.order_id=%s""", (o['id'],))
        o['items'] = cur.fetchall()
    cur.close()
    settings = get_settings()
    return render_template('orders.html', orders=orders_list, period=period,
                           status_filter=status_filter, settings=settings, low_stock=get_low_stock_items())

@app.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    cur = mysql.connection.cursor()
    cur.execute("""SELECT o.*, s.name as student_name, s.roll_number, s.phone, s.branch
                   FROM orders o JOIN students s ON o.student_id=s.id WHERE o.id=%s""", (order_id,))
    order = cur.fetchone()
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('orders'))
    cur.execute("""SELECT oi.*, mi.name as item_name FROM order_items oi
                   JOIN menu_items mi ON oi.menu_item_id=mi.id WHERE oi.order_id=%s""", (order_id,))
    items = cur.fetchall()
    cur.close()
    settings = get_settings()
    return render_template('order_detail.html', order=order, items=items,
                           settings=settings, low_stock=get_low_stock_items())

@app.route('/orders/add', methods=['GET', 'POST'])
@login_required
def add_order():
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        student_id = int(request.form['student_id'])
        pickup_time = request.form.get('pickup_time', '')
        payment_method = request.form.get('payment_method', 'cash')
        item_ids = request.form.getlist('item_id[]')
        quantities = request.form.getlist('quantity[]')

        if not item_ids:
            flash('Please add at least one item.', 'danger')
            cur.execute("SELECT * FROM students ORDER BY name")
            students_list = cur.fetchall()
            cur.execute("SELECT * FROM menu_items WHERE status='available' ORDER BY category, name")
            menu_items_list = cur.fetchall()
            cur.close()
            return render_template('add_order.html', students=students_list,
                                   menu_items=menu_items_list, settings=get_settings(), low_stock=get_low_stock_items())

        total = 0.0
        order_items_data = []
        for iid, qty in zip(item_ids, quantities):
            qty = int(qty)
            if qty <= 0:
                continue
            cur.execute("SELECT * FROM menu_items WHERE id=%s AND status='available'", (iid,))
            mi = cur.fetchone()
            if mi and mi['available_quantity'] >= qty:
                subtotal = float(mi['price']) * qty
                total += subtotal
                order_items_data.append((int(iid), qty, float(mi['price']), subtotal))

        if not order_items_data:
            flash('No valid items selected or insufficient stock.', 'danger')
            cur.execute("SELECT * FROM students ORDER BY name")
            students_list = cur.fetchall()
            cur.execute("SELECT * FROM menu_items WHERE status='available' ORDER BY category, name")
            menu_items_list = cur.fetchall()
            cur.close()
            return render_template('add_order.html', students=students_list,
                                   menu_items=menu_items_list, settings=get_settings(), low_stock=get_low_stock_items())

        if payment_method == 'prepaid':
            cur.execute("SELECT prepaid_balance FROM students WHERE id=%s", (student_id,))
            st = cur.fetchone()
            if not st or float(st['prepaid_balance']) < total:
                flash('Insufficient prepaid balance.', 'danger')
                cur.execute("SELECT * FROM students ORDER BY name")
                students_list = cur.fetchall()
                cur.execute("SELECT * FROM menu_items WHERE status='available' ORDER BY category, name")
                menu_items_list = cur.fetchall()
                cur.close()
                return render_template('add_order.html', students=students_list,
                                       menu_items=menu_items_list, settings=get_settings(), low_stock=get_low_stock_items())

        pay_status = 'paid' if payment_method == 'prepaid' else 'pending'
        cur.execute("""INSERT INTO orders (student_id,pickup_time,total_amount,payment_method,payment_status)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (student_id, pickup_time, total, payment_method, pay_status))
        order_id = cur.lastrowid

        for iid, qty, unit_price, subtotal in order_items_data:
            cur.execute("""INSERT INTO order_items (order_id,menu_item_id,quantity,unit_price,subtotal)
                           VALUES (%s,%s,%s,%s,%s)""", (order_id, iid, qty, unit_price, subtotal))
            cur.execute("UPDATE menu_items SET available_quantity=available_quantity-%s WHERE id=%s", (qty, iid))
            cur.execute("UPDATE menu_items SET status='unavailable' WHERE id=%s AND available_quantity<=0", (iid,))

        cur.execute("""INSERT INTO payments (order_id,student_id,amount,payment_method,status)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (order_id, student_id, total, payment_method, pay_status))

        if payment_method == 'prepaid':
            cur.execute("UPDATE students SET prepaid_balance=prepaid_balance-%s WHERE id=%s", (total, student_id))

        mysql.connection.commit()
        cur.close()
        flash(f'Order #{order_id} placed successfully!', 'success')
        return redirect(url_for('orders'))

    cur.execute("SELECT * FROM students ORDER BY name")
    students_list = cur.fetchall()
    cur.execute("SELECT * FROM menu_items WHERE status='available' ORDER BY category, name")
    menu_items_list = cur.fetchall()
    cur.close()
    settings = get_settings()
    return render_template('add_order.html', students=students_list,
                           menu_items=menu_items_list, settings=settings, low_stock=get_low_stock_items())

@app.route('/orders/update_status/<int:order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    new_status = request.form.get('status')
    valid = ['pending', 'preparing', 'ready', 'delivered']
    if new_status in valid:
        cur = mysql.connection.cursor()
        cur.execute("UPDATE orders SET order_status=%s WHERE id=%s", (new_status, order_id))
        mysql.connection.commit()
        cur.close()
        flash(f'Order status updated to {new_status}.', 'success')
    return redirect(request.referrer or url_for('orders'))

# ── Payments ──────────────────────────────────────────────────────────────────
@app.route('/payments')
@login_required
def payments():
    month_filter = request.args.get('month', date.today().strftime('%Y-%m'))
    cur = mysql.connection.cursor()
    cur.execute("""SELECT p.*, s.name as student_name, s.roll_number
                   FROM payments p JOIN students s ON p.student_id=s.id
                   WHERE DATE_FORMAT(p.payment_date,'%%Y-%%m')=%s
                   ORDER BY p.payment_date DESC""", (month_filter,))
    payments_list = cur.fetchall()

    today = date.today().strftime('%Y-%m-%d')
    cur.execute("SELECT COALESCE(SUM(amount),0) as total FROM payments WHERE DATE(payment_date)=%s AND status='paid'", (today,))
    collected_today = cur.fetchone()['total']
    cur.execute("SELECT COALESCE(SUM(amount),0) as total FROM payments WHERE DATE_FORMAT(payment_date,'%%Y-%%m')=%s AND status='paid'", (month_filter,))
    collected_month = cur.fetchone()['total']
    cur.close()
    settings = get_settings()
    return render_template('payments.html', payments=payments_list, month_filter=month_filter,
                           collected_today=collected_today, collected_month=collected_month,
                           settings=settings, low_stock=get_low_stock_items())

@app.route('/payments/mark_paid/<int:payment_id>', methods=['POST'])
@login_required
def mark_payment_paid(payment_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM payments WHERE id=%s", (payment_id,))
    pay = cur.fetchone()
    if pay and pay['status'] == 'pending':
        cur.execute("UPDATE payments SET status='paid', payment_date=NOW() WHERE id=%s", (payment_id,))
        cur.execute("UPDATE orders SET payment_status='paid' WHERE id=%s", (pay['order_id'],))
        mysql.connection.commit()
        flash('Payment marked as paid!', 'success')
    cur.close()
    return redirect(request.referrer or url_for('payments'))

# ── Reports ───────────────────────────────────────────────────────────────────
@app.route('/reports')
@login_required
def reports():
    date_from = request.args.get('date_from', date.today().strftime('%Y-%m-%d'))
    date_to = request.args.get('date_to', date.today().strftime('%Y-%m-%d'))
    cur = mysql.connection.cursor()

    cur.execute("""SELECT COUNT(*) as total_orders, COALESCE(SUM(total_amount),0) as total_revenue
                   FROM orders WHERE DATE(created_date) BETWEEN %s AND %s""", (date_from, date_to))
    summary = cur.fetchone()

    cur.execute("""SELECT mi.category, COUNT(oi.id) as order_count, SUM(oi.quantity) as total_qty,
                   SUM(oi.subtotal) as total_revenue
                   FROM order_items oi JOIN menu_items mi ON oi.menu_item_id=mi.id
                   JOIN orders o ON oi.order_id=o.id
                   WHERE DATE(o.created_date) BETWEEN %s AND %s
                   GROUP BY mi.category ORDER BY total_revenue DESC""", (date_from, date_to))
    category_sales = cur.fetchall()

    month_start = date.today().replace(day=1).strftime('%Y-%m-%d')
    cur.execute("""SELECT mi.name, SUM(oi.quantity) as total_qty, SUM(oi.subtotal) as total_revenue
                   FROM order_items oi JOIN menu_items mi ON oi.menu_item_id=mi.id
                   JOIN orders o ON oi.order_id=o.id
                   WHERE DATE(o.created_date)>=%s
                   GROUP BY mi.id ORDER BY total_qty DESC LIMIT 5""", (month_start,))
    top_items = cur.fetchall()

    cur.execute("""SELECT s.name, s.roll_number, COUNT(o.id) as order_count
                   FROM orders o JOIN students s ON o.student_id=s.id
                   WHERE DATE(o.created_date)>=%s
                   GROUP BY s.id ORDER BY order_count DESC LIMIT 5""", (month_start,))
    top_students = cur.fetchall()

    cur.execute("""SELECT mi.name, SUM(oi.quantity) as total_qty
                   FROM order_items oi JOIN menu_items mi ON oi.menu_item_id=mi.id
                   JOIN orders o ON oi.order_id=o.id
                   WHERE DATE(o.created_date) BETWEEN %s AND %s
                   GROUP BY mi.id ORDER BY total_qty DESC LIMIT 5""", (date_from, date_to))
    most_ordered = cur.fetchall()
    cur.close()
    settings = get_settings()
    return render_template('reports.html', summary=summary, category_sales=category_sales,
                           top_items=top_items, top_students=top_students, most_ordered=most_ordered,
                           date_from=date_from, date_to=date_to, settings=settings, low_stock=get_low_stock_items())

# ── Notices ───────────────────────────────────────────────────────────────────
@app.route('/notices')
@login_required
def notices():
    cur = mysql.connection.cursor()
    cur.execute("""SELECT n.*, a.name as admin_name FROM notices n
                   JOIN admins a ON n.admin_id=a.id ORDER BY n.posted_date DESC""")
    notices_list = cur.fetchall()
    cur.close()
    settings = get_settings()
    return render_template('notices.html', notices=notices_list, settings=settings, low_stock=get_low_stock_items())

@app.route('/notices/add', methods=['POST'])
@login_required
def add_notice():
    title = request.form['title'].strip()
    message = request.form['message'].strip()
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO notices (title,message,admin_id) VALUES (%s,%s,%s)",
                (title, message, current_user.id))
    mysql.connection.commit()
    cur.close()
    flash('Notice posted!', 'success')
    return redirect(url_for('notices'))

@app.route('/notices/delete/<int:notice_id>', methods=['POST'])
@login_required
def delete_notice(notice_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM notices WHERE id=%s", (notice_id,))
    mysql.connection.commit()
    cur.close()
    flash('Notice deleted.', 'success')
    return redirect(url_for('notices'))

# ── Settings ──────────────────────────────────────────────────────────────────
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings_page():
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'change_password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')
            cur.execute("SELECT password_hash FROM admins WHERE id=%s", (current_user.id,))
            admin = cur.fetchone()
            if not check_password_hash(admin['password_hash'], current_pw):
                flash('Current password is incorrect.', 'danger')
            elif new_pw != confirm_pw:
                flash('New passwords do not match.', 'danger')
            elif len(new_pw) < 6:
                flash('Password must be at least 6 characters.', 'danger')
            else:
                new_hash = generate_password_hash(new_pw)
                cur.execute("UPDATE admins SET password_hash=%s WHERE id=%s", (new_hash, current_user.id))
                mysql.connection.commit()
                flash('Password changed successfully!', 'success')
        elif action == 'update_settings':
            keys = ['canteen_name', 'college_name', 'opening_time', 'closing_time']
            for k in keys:
                val = request.form.get(k, '')
                cur.execute("INSERT INTO settings (`key`,value) VALUES (%s,%s) ON DUPLICATE KEY UPDATE value=%s",
                            (k, val, val))
            mysql.connection.commit()
            flash('Settings updated!', 'success')
        cur.close()
        return redirect(url_for('settings_page'))
    cur.close()
    settings = get_settings()
    return render_template('settings.html', settings=settings, low_stock=get_low_stock_items())

# ── API helpers ───────────────────────────────────────────────────────────────
@app.route('/api/menu_item/<int:item_id>')
@login_required
def api_menu_item(item_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, price, available_quantity FROM menu_items WHERE id=%s", (item_id,))
    item = cur.fetchone()
    cur.close()
    if item:
        return jsonify({'id': item['id'], 'name': item['name'],
                        'price': float(item['price']), 'qty': item['available_quantity']})
    return jsonify({'error': 'not found'}), 404

@app.route('/api/student_balance/<int:student_id>')
@login_required
def api_student_balance(student_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT prepaid_balance FROM students WHERE id=%s", (student_id,))
    st = cur.fetchone()
    cur.close()
    if st:
        return jsonify({'balance': float(st['prepaid_balance'])})
    return jsonify({'error': 'not found'}), 404

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
