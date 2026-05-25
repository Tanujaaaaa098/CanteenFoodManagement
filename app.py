import os
import pymysql
import pymysql.cursors
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import date, timedelta

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'canteen-super-secret-key-2024')

# ── DB config ─────────────────────────────────────────────────────────────────
DB_CONFIG = {
    'host':     os.getenv('MYSQLHOST')     or os.getenv('MYSQL_HOST', 'localhost'),
    'user':     os.getenv('MYSQLUSER')     or os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQLPASSWORD') or os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQLDATABASE') or os.getenv('MYSQL_DB', 'canteen_db'),
    'port':     int(os.getenv('MYSQLPORT') or os.getenv('MYSQL_PORT', 3306)),
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit': False,
}

def get_db():
    if 'db' not in g:
        g.db = pymysql.connect(**DB_CONFIG)
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query(sql, args=None, one=False, commit=False):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(sql, args or ())
        if commit:
            db.commit()
            return cur.lastrowid
        return cur.fetchone() if one else cur.fetchall()

def execute(sql, args=None):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(sql, args or ())
    db.commit()

# ── Jinja2 filter: TIME columns come as timedelta from PyMySQL ────────────────
@app.template_filter('fmt_time')
def fmt_time(value):
    if value is None:
        return ''
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        h, m = divmod(total // 60, 60)
        return f'{h:02d}:{m:02d}'
    try:
        return value.strftime('%H:%M')
    except Exception:
        return str(value)

# ── Login ─────────────────────────────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

class Admin(UserMixin):
    def __init__(self, id, name, email):
        self.id = id
        self.name = name
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    admin = query("SELECT * FROM admins WHERE id=%s", (user_id,), one=True)
    if admin:
        return Admin(admin['id'], admin['name'], admin['email'])
    return None

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_settings():
    rows = query("SELECT `key`, value FROM settings")
    return {r['key']: r['value'] for r in rows}

def get_low_stock():
    return query("SELECT * FROM menu_items WHERE available_quantity < 5 AND status='available'")

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        admin = query("SELECT * FROM admins WHERE email=%s", (email,), one=True)
        if admin and check_password_hash(admin['password_hash'], password):
            login_user(Admin(admin['id'], admin['name'], admin['email']))
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

# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    today = date.today().strftime('%Y-%m-%d')
    total_menu    = query("SELECT COUNT(*) as c FROM menu_items", one=True)['c']
    orders_today  = query("SELECT COUNT(*) as c FROM orders WHERE DATE(created_date)=%s", (today,), one=True)['c']
    revenue_today = query("SELECT COALESCE(SUM(amount),0) as r FROM payments WHERE DATE(payment_date)=%s AND status='paid'", (today,), one=True)['r']
    pending_pay   = query("SELECT COUNT(*) as c FROM payments WHERE status='pending'", one=True)['c']

    today_orders = query("""SELECT o.id, s.name as student_name, o.total_amount,
                            o.payment_status, o.order_status, o.order_time
                            FROM orders o JOIN students s ON o.student_id=s.id
                            WHERE DATE(o.created_date)=%s ORDER BY o.order_time DESC""", (today,))
    for o in today_orders:
        o['items'] = query("""SELECT mi.name, oi.quantity FROM order_items oi
                              JOIN menu_items mi ON oi.menu_item_id=mi.id
                              WHERE oi.order_id=%s""", (o['id'],))

    most_ordered = query("""SELECT mi.name, SUM(oi.quantity) as total_qty
                            FROM order_items oi JOIN menu_items mi ON oi.menu_item_id=mi.id
                            JOIN orders o ON oi.order_id=o.id
                            WHERE DATE(o.created_date)=%s
                            GROUP BY mi.id ORDER BY total_qty DESC LIMIT 1""", (today,), one=True)

    week_revenue = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).strftime('%Y-%m-%d')
        rev = query("SELECT COALESCE(SUM(amount),0) as r FROM payments WHERE DATE(payment_date)=%s AND status='paid'", (d,), one=True)['r']
        week_revenue.append({'day': (date.today() - timedelta(days=i)).strftime('%a'), 'revenue': float(rev)})

    latest_notices = query("SELECT * FROM notices ORDER BY posted_date DESC LIMIT 3")
    return render_template('dashboard.html',
        total_menu=total_menu, orders_today=orders_today,
        revenue_today=revenue_today, pending_payments=pending_pay,
        today_orders=today_orders, most_ordered=most_ordered,
        low_stock=get_low_stock(), week_revenue=week_revenue,
        latest_notices=latest_notices, settings=get_settings())

# ── Menu ──────────────────────────────────────────────────────────────────────
@app.route('/menu')
@login_required
def menu():
    search   = request.args.get('search', '')
    category = request.args.get('category', 'All')
    sql = "SELECT * FROM menu_items WHERE 1=1"
    params = []
    if search:
        sql += " AND (name LIKE %s OR category LIKE %s)"
        params += [f'%{search}%', f'%{search}%']
    if category and category != 'All':
        sql += " AND category=%s"
        params.append(category)
    sql += " ORDER BY category, name"
    items = query(sql, params)
    return render_template('menu.html', items=items, search=search,
                           category=category, settings=get_settings(), low_stock=get_low_stock())

@app.route('/menu/add', methods=['GET', 'POST'])
@login_required
def add_menu_item():
    if request.method == 'POST':
        qty    = int(request.form.get('available_quantity', 0))
        status = 'available' if qty > 0 else 'unavailable'
        execute("""INSERT INTO menu_items (name,category,price,description,
                   available_quantity,available_from,available_to,status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (request.form['name'].strip(), request.form['category'],
                 float(request.form['price']), request.form.get('description',''),
                 qty, request.form.get('available_from') or None,
                 request.form.get('available_to') or None, status))
        flash('Menu item added!', 'success')
        return redirect(url_for('menu'))
    return render_template('add_menu_item.html', settings=get_settings(), low_stock=get_low_stock())

@app.route('/menu/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_menu_item(item_id):
    if request.method == 'POST':
        execute("""UPDATE menu_items SET name=%s,category=%s,price=%s,description=%s,
                   available_quantity=%s,available_from=%s,available_to=%s,status=%s
                   WHERE id=%s""",
                (request.form['name'].strip(), request.form['category'],
                 float(request.form['price']), request.form.get('description',''),
                 int(request.form.get('available_quantity',0)),
                 request.form.get('available_from') or None,
                 request.form.get('available_to') or None,
                 request.form.get('status','available'), item_id))
        flash('Menu item updated!', 'success')
        return redirect(url_for('menu'))
    item = query("SELECT * FROM menu_items WHERE id=%s", (item_id,), one=True)
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('menu'))
    return render_template('edit_menu_item.html', item=item, settings=get_settings(), low_stock=get_low_stock())

@app.route('/menu/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_menu_item(item_id):
    execute("DELETE FROM menu_items WHERE id=%s", (item_id,))
    flash('Menu item deleted.', 'success')
    return redirect(url_for('menu'))

@app.route('/menu/toggle/<int:item_id>', methods=['POST'])
@login_required
def toggle_menu_item(item_id):
    item = query("SELECT status FROM menu_items WHERE id=%s", (item_id,), one=True)
    if item:
        new = 'unavailable' if item['status'] == 'available' else 'available'
        execute("UPDATE menu_items SET status=%s WHERE id=%s", (new, item_id))
    return jsonify({'status': 'ok'})

# ── Students ──────────────────────────────────────────────────────────────────
@app.route('/students')
@login_required
def students():
    search = request.args.get('search', '')
    if search:
        rows = query("""SELECT s.*, COUNT(o.id) as total_orders,
                        COALESCE(SUM(CASE WHEN o.payment_status='pending' THEN o.total_amount ELSE 0 END),0) as pending_balance
                        FROM students s LEFT JOIN orders o ON s.id=o.student_id
                        WHERE s.name LIKE %s OR s.roll_number LIKE %s
                        GROUP BY s.id ORDER BY s.name""", (f'%{search}%', f'%{search}%'))
    else:
        rows = query("""SELECT s.*, COUNT(o.id) as total_orders,
                        COALESCE(SUM(CASE WHEN o.payment_status='pending' THEN o.total_amount ELSE 0 END),0) as pending_balance
                        FROM students s LEFT JOIN orders o ON s.id=o.student_id
                        GROUP BY s.id ORDER BY s.name""")
    return render_template('students.html', students=rows, search=search,
                           settings=get_settings(), low_stock=get_low_stock())

@app.route('/students/add', methods=['GET', 'POST'])
@login_required
def add_student():
    if request.method == 'POST':
        try:
            execute("""INSERT INTO students (name,roll_number,branch,year,phone,email,prepaid_balance)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (request.form['name'].strip(), request.form['roll_number'].strip(),
                     request.form.get('branch',''), request.form.get('year',1),
                     request.form.get('phone',''), request.form.get('email',''),
                     float(request.form.get('prepaid_balance',0))))
            flash('Student added!', 'success')
            return redirect(url_for('students'))
        except Exception:
            flash('Error: Roll number may already exist.', 'danger')
    return render_template('add_student.html', settings=get_settings(), low_stock=get_low_stock())

@app.route('/students/<int:student_id>')
@login_required
def student_detail(student_id):
    student = query("SELECT * FROM students WHERE id=%s", (student_id,), one=True)
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('students'))
    order_history = query("""SELECT o.*, GROUP_CONCAT(mi.name ORDER BY mi.name SEPARATOR ', ') as items_list
                             FROM orders o
                             LEFT JOIN order_items oi ON o.id=oi.order_id
                             LEFT JOIN menu_items mi ON oi.menu_item_id=mi.id
                             WHERE o.student_id=%s GROUP BY o.id ORDER BY o.created_date DESC""", (student_id,))
    total_spent   = query("SELECT COALESCE(SUM(total_amount),0) as t FROM orders WHERE student_id=%s AND payment_status='paid'", (student_id,), one=True)['t']
    total_pending = query("SELECT COALESCE(SUM(total_amount),0) as t FROM orders WHERE student_id=%s AND payment_status='pending'", (student_id,), one=True)['t']
    return render_template('student_detail.html', student=student, order_history=order_history,
                           total_spent=total_spent, total_pending=total_pending,
                           settings=get_settings(), low_stock=get_low_stock())

@app.route('/students/edit/<int:student_id>', methods=['POST'])
@login_required
def edit_student(student_id):
    execute("""UPDATE students SET name=%s,branch=%s,year=%s,phone=%s,email=%s,prepaid_balance=%s
               WHERE id=%s""",
            (request.form['name'].strip(), request.form.get('branch',''),
             request.form.get('year',1), request.form.get('phone',''),
             request.form.get('email',''), float(request.form.get('prepaid_balance',0)),
             student_id))
    flash('Student updated!', 'success')
    return redirect(url_for('student_detail', student_id=student_id))

@app.route('/students/delete/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    execute("DELETE FROM students WHERE id=%s", (student_id,))
    flash('Student deleted.', 'success')
    return redirect(url_for('students'))

# ── Orders ────────────────────────────────────────────────────────────────────
@app.route('/orders')
@login_required
def orders():
    period        = request.args.get('period', 'today')
    status_filter = request.args.get('status', 'All')
    today      = date.today().strftime('%Y-%m-%d')
    week_start = (date.today() - timedelta(days=date.today().weekday())).strftime('%Y-%m-%d')
    sql = "SELECT o.*, s.name as student_name, s.roll_number FROM orders o JOIN students s ON o.student_id=s.id WHERE 1=1"
    params = []
    if period == 'today':
        sql += " AND DATE(o.created_date)=%s"; params.append(today)
    elif period == 'week':
        sql += " AND DATE(o.created_date)>=%s"; params.append(week_start)
    if status_filter != 'All':
        sql += " AND o.order_status=%s"; params.append(status_filter.lower())
    sql += " ORDER BY o.created_date DESC"
    orders_list = query(sql, params)
    for o in orders_list:
        o['items'] = query("""SELECT mi.name, oi.quantity, oi.unit_price, oi.subtotal
                              FROM order_items oi JOIN menu_items mi ON oi.menu_item_id=mi.id
                              WHERE oi.order_id=%s""", (o['id'],))
    return render_template('orders.html', orders=orders_list, period=period,
                           status_filter=status_filter, settings=get_settings(), low_stock=get_low_stock())

@app.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    order = query("""SELECT o.*, s.name as student_name, s.roll_number, s.phone, s.branch
                     FROM orders o JOIN students s ON o.student_id=s.id WHERE o.id=%s""",
                  (order_id,), one=True)
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('orders'))
    items = query("""SELECT oi.*, mi.name as item_name FROM order_items oi
                     JOIN menu_items mi ON oi.menu_item_id=mi.id WHERE oi.order_id=%s""", (order_id,))
    return render_template('order_detail.html', order=order, items=items,
                           settings=get_settings(), low_stock=get_low_stock())

@app.route('/orders/add', methods=['GET', 'POST'])
@login_required
def add_order():
    if request.method == 'POST':
        student_id     = int(request.form['student_id'])
        pickup_time    = request.form.get('pickup_time', '')
        payment_method = request.form.get('payment_method', 'cash')
        item_ids       = request.form.getlist('item_id[]')
        quantities     = request.form.getlist('quantity[]')

        order_items_data = []
        total = 0.0
        for iid, qty in zip(item_ids, quantities):
            qty = int(qty)
            if qty <= 0:
                continue
            mi = query("SELECT * FROM menu_items WHERE id=%s AND status='available'", (iid,), one=True)
            if mi and mi['available_quantity'] >= qty:
                sub = float(mi['price']) * qty
                total += sub
                order_items_data.append((int(iid), qty, float(mi['price']), sub))

        if not order_items_data:
            flash('No valid items or insufficient stock.', 'danger')
            return redirect(url_for('add_order'))

        if payment_method == 'prepaid':
            st = query("SELECT prepaid_balance FROM students WHERE id=%s", (student_id,), one=True)
            if not st or float(st['prepaid_balance']) < total:
                flash('Insufficient prepaid balance.', 'danger')
                return redirect(url_for('add_order'))

        pay_status = 'paid' if payment_method == 'prepaid' else 'pending'
        db = get_db()
        with db.cursor() as cur:
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
                           VALUES (%s,%s,%s,%s,%s)""", (order_id, student_id, total, payment_method, pay_status))
            if payment_method == 'prepaid':
                cur.execute("UPDATE students SET prepaid_balance=prepaid_balance-%s WHERE id=%s", (total, student_id))
        db.commit()
        flash(f'Order #{order_id} placed!', 'success')
        return redirect(url_for('orders'))

    students_list  = query("SELECT * FROM students ORDER BY name")
    menu_items_list = query("SELECT * FROM menu_items WHERE status='available' ORDER BY category, name")
    return render_template('add_order.html', students=students_list,
                           menu_items=menu_items_list, settings=get_settings(), low_stock=get_low_stock())

@app.route('/orders/update_status/<int:order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    new_status = request.form.get('status')
    if new_status in ['pending', 'preparing', 'ready', 'delivered']:
        execute("UPDATE orders SET order_status=%s WHERE id=%s", (new_status, order_id))
        flash(f'Order status updated to {new_status}.', 'success')
    return redirect(request.referrer or url_for('orders'))

# ── Payments ──────────────────────────────────────────────────────────────────
@app.route('/payments')
@login_required
def payments():
    month_filter = request.args.get('month', date.today().strftime('%Y-%m'))
    payments_list = query("""SELECT p.*, s.name as student_name, s.roll_number
                             FROM payments p JOIN students s ON p.student_id=s.id
                             WHERE DATE_FORMAT(p.payment_date,'%%Y-%%m')=%s
                             ORDER BY p.payment_date DESC""", (month_filter,))
    today = date.today().strftime('%Y-%m-%d')
    collected_today = query("SELECT COALESCE(SUM(amount),0) as t FROM payments WHERE DATE(payment_date)=%s AND status='paid'", (today,), one=True)['t']
    collected_month = query("SELECT COALESCE(SUM(amount),0) as t FROM payments WHERE DATE_FORMAT(payment_date,'%%Y-%%m')=%s AND status='paid'", (month_filter,), one=True)['t']
    return render_template('payments.html', payments=payments_list, month_filter=month_filter,
                           collected_today=collected_today, collected_month=collected_month,
                           settings=get_settings(), low_stock=get_low_stock())

@app.route('/payments/mark_paid/<int:payment_id>', methods=['POST'])
@login_required
def mark_payment_paid(payment_id):
    pay = query("SELECT * FROM payments WHERE id=%s", (payment_id,), one=True)
    if pay and pay['status'] == 'pending':
        execute("UPDATE payments SET status='paid', payment_date=NOW() WHERE id=%s", (payment_id,))
        execute("UPDATE orders SET payment_status='paid' WHERE id=%s", (pay['order_id'],))
        flash('Payment marked as paid!', 'success')
    return redirect(request.referrer or url_for('payments'))

# ── Reports ───────────────────────────────────────────────────────────────────
@app.route('/reports')
@login_required
def reports():
    date_from  = request.args.get('date_from', date.today().strftime('%Y-%m-%d'))
    date_to    = request.args.get('date_to',   date.today().strftime('%Y-%m-%d'))
    month_start = date.today().replace(day=1).strftime('%Y-%m-%d')

    summary = query("""SELECT COUNT(*) as total_orders, COALESCE(SUM(total_amount),0) as total_revenue
                       FROM orders WHERE DATE(created_date) BETWEEN %s AND %s""",
                    (date_from, date_to), one=True)
    category_sales = query("""SELECT mi.category, COUNT(oi.id) as order_count,
                               SUM(oi.quantity) as total_qty, SUM(oi.subtotal) as total_revenue
                               FROM order_items oi JOIN menu_items mi ON oi.menu_item_id=mi.id
                               JOIN orders o ON oi.order_id=o.id
                               WHERE DATE(o.created_date) BETWEEN %s AND %s
                               GROUP BY mi.category ORDER BY total_revenue DESC""", (date_from, date_to))
    most_ordered = query("""SELECT mi.name, SUM(oi.quantity) as total_qty
                            FROM order_items oi JOIN menu_items mi ON oi.menu_item_id=mi.id
                            JOIN orders o ON oi.order_id=o.id
                            WHERE DATE(o.created_date) BETWEEN %s AND %s
                            GROUP BY mi.id ORDER BY total_qty DESC LIMIT 5""", (date_from, date_to))
    top_items = query("""SELECT mi.name, SUM(oi.quantity) as total_qty, SUM(oi.subtotal) as total_revenue
                         FROM order_items oi JOIN menu_items mi ON oi.menu_item_id=mi.id
                         JOIN orders o ON oi.order_id=o.id
                         WHERE DATE(o.created_date)>=%s
                         GROUP BY mi.id ORDER BY total_qty DESC LIMIT 5""", (month_start,))
    top_students = query("""SELECT s.name, s.roll_number, COUNT(o.id) as order_count
                            FROM orders o JOIN students s ON o.student_id=s.id
                            WHERE DATE(o.created_date)>=%s
                            GROUP BY s.id ORDER BY order_count DESC LIMIT 5""", (month_start,))
    return render_template('reports.html', summary=summary, category_sales=category_sales,
                           top_items=top_items, top_students=top_students, most_ordered=most_ordered,
                           date_from=date_from, date_to=date_to,
                           settings=get_settings(), low_stock=get_low_stock())

# ── Notices ───────────────────────────────────────────────────────────────────
@app.route('/notices')
@login_required
def notices():
    notices_list = query("""SELECT n.*, a.name as admin_name FROM notices n
                            JOIN admins a ON n.admin_id=a.id ORDER BY n.posted_date DESC""")
    return render_template('notices.html', notices=notices_list,
                           settings=get_settings(), low_stock=get_low_stock())

@app.route('/notices/add', methods=['POST'])
@login_required
def add_notice():
    execute("INSERT INTO notices (title,message,admin_id) VALUES (%s,%s,%s)",
            (request.form['title'].strip(), request.form['message'].strip(), current_user.id))
    flash('Notice posted!', 'success')
    return redirect(url_for('notices'))

@app.route('/notices/delete/<int:notice_id>', methods=['POST'])
@login_required
def delete_notice(notice_id):
    execute("DELETE FROM notices WHERE id=%s", (notice_id,))
    flash('Notice deleted.', 'success')
    return redirect(url_for('notices'))

# ── Settings ──────────────────────────────────────────────────────────────────
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings_page():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'change_password':
            admin = query("SELECT password_hash FROM admins WHERE id=%s", (current_user.id,), one=True)
            cur_pw  = request.form.get('current_password', '')
            new_pw  = request.form.get('new_password', '')
            conf_pw = request.form.get('confirm_password', '')
            if not check_password_hash(admin['password_hash'], cur_pw):
                flash('Current password is incorrect.', 'danger')
            elif new_pw != conf_pw:
                flash('New passwords do not match.', 'danger')
            elif len(new_pw) < 6:
                flash('Password must be at least 6 characters.', 'danger')
            else:
                execute("UPDATE admins SET password_hash=%s WHERE id=%s",
                        (generate_password_hash(new_pw), current_user.id))
                flash('Password changed!', 'success')
        elif action == 'update_settings':
            for k in ['canteen_name', 'college_name', 'opening_time', 'closing_time']:
                val = request.form.get(k, '')
                execute("INSERT INTO settings (`key`,value) VALUES (%s,%s) ON DUPLICATE KEY UPDATE value=%s",
                        (k, val, val))
            flash('Settings updated!', 'success')
        return redirect(url_for('settings_page'))
    return render_template('settings.html', settings=get_settings(), low_stock=get_low_stock())

# ── API ───────────────────────────────────────────────────────────────────────
@app.route('/api/menu_item/<int:item_id>')
@login_required
def api_menu_item(item_id):
    item = query("SELECT id,name,price,available_quantity FROM menu_items WHERE id=%s", (item_id,), one=True)
    if item:
        return jsonify({'id': item['id'], 'name': item['name'],
                        'price': float(item['price']), 'qty': item['available_quantity']})
    return jsonify({'error': 'not found'}), 404

@app.route('/api/student_balance/<int:student_id>')
@login_required
def api_student_balance(student_id):
    st = query("SELECT prepaid_balance FROM students WHERE id=%s", (student_id,), one=True)
    if st:
        return jsonify({'balance': float(st['prepaid_balance'])})
    return jsonify({'error': 'not found'}), 404

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
