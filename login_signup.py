from flask import Flask, render_template, request, redirect, session, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import json
import requests

app = Flask(__name__)
app.secret_key = "secret123"

# ---------- IMAGE UPLOAD CONFIG ----------
UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ---------- MYSQL CONNECTION ----------
import os

db = mysql.connector.connect(
    host=os.environ.get("MYSQLHOST"),
    user=os.environ.get("MYSQLUSER"),
    password=os.environ.get("MYSQLPASSWORD"),
    database=os.environ.get("MYSQLDATABASE"),
    port=int(os.environ.get("MYSQLPORT", 3306))
)

def get_cursor():
    global db
    try:
        db.ping(reconnect=True, attempts=3, delay=2)
    except:
        db = mysql.connector.connect(
            host=os.environ.get('MYSQLHOST', 'localhost'),
            user=os.environ.get('MYSQLUSER', 'root'),
            password=os.environ.get('MYSQLPASSWORD', 'Orpmk_2006'),
            database=os.environ.get('MYSQLDATABASE', 'smart_farmer'),
            port=int(os.environ.get('MYSQLPORT', 3306))
        )
    return db.cursor(dictionary=True)

# ---------- LANGUAGE LOADER ----------
# ---------- TRANSLATION CACHE ----------
translation_cache = {}

def translate_text(text, target_lang):
    try:
        response = requests.get(
            "https://api.mymemory.translated.net/get",
            params={
                "q": text,
                "langpair": f"en|{target_lang}"
            },
            timeout=5
        )
        result = response.json()
        return result["responseData"]["translatedText"]
    except:
        return text


def load_language():
    lang = request.args.get('lang')
    if lang:
        session['lang'] = lang
    lang = session.get('lang', 'en')

   
    if lang == 'en':
        with open("translations/en.json", encoding="utf-8") as f:
            return json.load(f)

  
    if lang in translation_cache:
        return translation_cache[lang]

    try:
        with open(f"translations/{lang}.json", encoding="utf-8") as f:
            data = json.load(f)
            translation_cache[lang] = data
            return data
    except FileNotFoundError:
        pass

    # Fallback to English if something goes wrong
    with open("translations/en.json", encoding="utf-8") as f:
        return json.load(f)

# ---------- LOGIN PAGE ----------
@app.route('/')
def login_page():
    t = load_language()
    return render_template('SFM-login.html', t=t)

# ---------- AUTH ----------
@app.route('/auth', methods=['POST'])
def auth():
    cursor = get_cursor()

    mode = request.form['mode']
    email = request.form['email']
    password = request.form['password']
    role = request.form['role']

    if mode == "signup":

        name = request.form['name']
        hashed_pw = generate_password_hash(password)

        cursor.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s,%s,%s,%s)",
            (name, email, hashed_pw, role)
        )
        db.commit()

        session['user_id'] = cursor.lastrowid
        session['user_role'] = role
        session['user_name'] = name

        return redirect(f"/{role}_dashboard")

    else:

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):

            session['user_id'] = user['id']
            session['user_role'] = user['role']
            session['user_name'] = user['name']

            return redirect(f"/{user['role']}_dashboard")

        return "Invalid credentials"

# ---------- FARMER DASHBOARD ----------
@app.route('/farmer_dashboard')
def farmer_dashboard():

    if 'user_id' not in session or session['user_role'] != 'farmer':
        return redirect('/')

    cursor = get_cursor()
    farmer_id = session['user_id']
    t = load_language()

    cursor.execute("""
        SELECT * FROM products
        WHERE farmer_id=%s
    """, (farmer_id,))

    products = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*) AS total_orders
        FROM orders
        WHERE farmer_id=%s
    """, (farmer_id,))

    total_orders = cursor.fetchone()['total_orders']

    cursor.execute("""
        SELECT COALESCE(SUM(total_price),0) AS total_earnings
        FROM orders
        WHERE farmer_id=%s
    """, (farmer_id,))

    total_earnings = cursor.fetchone()['total_earnings']

    return render_template(
        'farmer_dashboard.html',
        products=products,
        order_count=total_orders,
        total_earnings=total_earnings,
        farmer_name=session['user_name'],
        t=t
    )

# ---------- ADD PRODUCT ----------
@app.route('/add_product', methods=['POST'])
def add_product():

    if 'user_id' not in session or session['user_role'] != 'farmer':
        return redirect('/')

    cursor = get_cursor()

    name = request.form['name']
    category = request.form['category']
    price = request.form['price']
    unit = request.form['unit']
    quantity = request.form.get('quantity', 0)
    description = request.form.get('description', '')

    image_file = request.files.get('image')
    image_filename = 'default_crop.png'

    if image_file and image_file.filename != '':
        image_filename = secure_filename(image_file.filename)

        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
        image_file.save(image_path)

    cursor.execute("""
        INSERT INTO products
        (farmer_id, name, category, price, unit, quantity, description, image, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Listed')
    """, (
        session['user_id'],
        name,
        category,
        price,
        unit,
        quantity,
        description,
        image_filename
    ))

    db.commit()

    return redirect('/farmer_dashboard')

# ---------- DELETE PRODUCT ----------
@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):

    if 'user_id' not in session or session['user_role'] != 'farmer':
        return redirect('/')

    cursor = get_cursor()

    cursor.execute("""
        UPDATE products
        SET status='Deleted'
        WHERE id=%s AND farmer_id=%s AND status!='Deleted'
    """, (product_id, session['user_id']))

    db.commit()

    return redirect('/farmer_dashboard')

# ---------- BUYER DASHBOARD ----------
@app.route('/buyer_dashboard')
def buyer_dashboard():

    cursor = get_cursor()
    t = load_language()
    lang = session.get('lang', 'en')

    cursor.execute("""
        SELECT p.*, u.name AS farmer_name
        FROM products p
        JOIN users u ON p.farmer_id = u.id
        WHERE p.quantity > 0
        AND p.status = 'Listed'
    """)

    products = cursor.fetchall()

    # Translate product name & description if not English
    if lang != 'en':
        for product in products:
            if product.get('name'):
                product['name'] = translate_text(
                    product['name'], lang)
            if product.get('description'):
                product['description'] = translate_text(
                    product['description'], lang)

    return render_template(
        'buyer_dashboard.html',
        products=products,
        t=t
    )

# ---------- ADD TO CART ----------
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):

    if 'user_id' not in session or session['user_role'] != 'buyer':
        return jsonify(success=False)

    cursor = get_cursor()
    buyer_id = session['user_id']
    quantity = int(request.form.get('quantity', 1))

    cursor.execute("SELECT quantity FROM products WHERE id=%s", (product_id,))
    product = cursor.fetchone()

    if not product or product['quantity'] < quantity:
        return jsonify(success=False, message="Not enough stock")

    cursor.execute("""
        SELECT * FROM cart
        WHERE buyer_id=%s AND product_id=%s
    """, (buyer_id, product_id))

    existing = cursor.fetchone()

    if existing:

        cursor.execute("""
            UPDATE cart
            SET quantity = quantity + %s
            WHERE buyer_id=%s AND product_id=%s
        """, (quantity, buyer_id, product_id))

    else:

        cursor.execute("""
            INSERT INTO cart (buyer_id, product_id, quantity)
            VALUES (%s,%s,%s)
        """, (buyer_id, product_id, quantity))

    db.commit()

    return jsonify(success=True)

# ---------- CART COUNT ----------
@app.route('/cart_count')
def cart_count():

    if 'user_id' not in session:
        return jsonify(count=0)

    cursor = get_cursor()
    buyer_id = session['user_id']

    cursor.execute("""
        SELECT COALESCE(SUM(quantity),0) AS count
        FROM cart
        WHERE buyer_id=%s
    """, (buyer_id,))

    count = cursor.fetchone()['count']

    return jsonify(count=count)

# ---------- VIEW CART ----------
@app.route('/cart')
def view_cart():

    if 'user_id' not in session or session['user_role'] != 'buyer':
        return redirect('/')

    cursor = get_cursor()
    buyer_id = session['user_id']
    t = load_language()

    cursor.execute("""
        SELECT c.id, p.name, p.price, p.unit, c.quantity,
        (p.price * c.quantity) AS total_price,
        u.name AS farmer_name
        FROM cart c
        JOIN products p ON c.product_id = p.id
        JOIN users u ON p.farmer_id = u.id
        WHERE c.buyer_id=%s
    """, (buyer_id,))

    cart_items = cursor.fetchall()

    total_amount = sum(item['total_price'] for item in cart_items)

    return render_template(
        'cart.html',
        cart_items=cart_items,
        total_amount=total_amount,
        t=t
    )

# ---------- DELETE FROM CART ----------
@app.route('/delete_from_cart/<int:cart_id>', methods=['POST'])
def delete_from_cart(cart_id):

    if 'user_id' not in session or session['user_role'] != 'buyer':
        return redirect('/')

    cursor = get_cursor()

    cursor.execute(
        "DELETE FROM cart WHERE id=%s AND buyer_id=%s",
        (cart_id, session['user_id'])
    )

    db.commit()

    return redirect('/cart')

# ---------- CHECKOUT ----------

@app.route('/payment')
def payment_page():

    if 'user_id' not in session or session['user_role'] != 'buyer':
        return redirect('/')

    cursor = get_cursor()
    buyer_id = session['user_id']
    t = load_language()

    cursor.execute("""
        SELECT c.id, p.name, p.price, p.unit, c.quantity,
               (p.price * c.quantity) AS total_price,
               u.name AS farmer_name
        FROM cart c
        JOIN products p ON c.product_id = p.id
        JOIN users u ON p.farmer_id = u.id
        WHERE c.buyer_id=%s
    """, (buyer_id,))

    cart_items = cursor.fetchall()

    if not cart_items:
        return redirect('/cart')

    total_amount = sum(item['total_price'] for item in cart_items)

    return render_template(
        'payment.html',
        cart_items=cart_items,
        total_amount=total_amount,
        t=t
    )
@app.route('/checkout', methods=['POST'])
def checkout():

    if 'user_id' not in session or session['user_role'] != 'buyer':
        return redirect('/')

    cursor = get_cursor()
    buyer_id = session['user_id']

    # ── Collect address & payment details from the payment form ──
    full_name    = request.form.get('full_name', '')
    phone        = request.form.get('phone', '')
    address_line1 = request.form.get('address_line1', '')
    address_line2 = request.form.get('address_line2', '')
    city         = request.form.get('city', '')
    state        = request.form.get('state', '')
    pincode      = request.form.get('pincode', '')
    payment_mode = request.form.get('payment_mode', 'UPI')

    full_address = f"{address_line1}, {address_line2}, {city}, {state} - {pincode}".strip(', ')

    try:
        cursor.execute("""
            SELECT c.product_id, c.quantity, p.price, p.farmer_id, p.quantity AS stock
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.buyer_id=%s
        """, (buyer_id,))

        items = cursor.fetchall()

        if not items:
            return "Cart is empty"

        for item in items:

            if item['quantity'] > item['stock']:
                db.rollback()
                return f"Not enough stock for product {item['product_id']}"

            total_price = item['price'] * item['quantity']

            cursor.execute("""
                INSERT INTO orders
                (buyer_id, farmer_id, product_id, quantity, total_price,
                 status, delivery_address, payment_mode, buyer_name, buyer_phone)
                VALUES (%s,%s,%s,%s,%s,'Confirmed',%s,%s,%s,%s)
            """, (
                buyer_id,
                item['farmer_id'],
                item['product_id'],
                item['quantity'],
                total_price,
                full_address,
                payment_mode,
                full_name,
                phone
            ))

            cursor.execute("""
                UPDATE products
                SET quantity = quantity - %s
                WHERE id=%s
            """, (item['quantity'], item['product_id']))

        cursor.execute("DELETE FROM cart WHERE buyer_id=%s", (buyer_id,))
        db.commit()

        return redirect('/buyer_dashboard')

    except Exception as e:
        db.rollback()
        return f"Checkout error: {str(e)}"
    

# ---------- LOGOUT ----------
@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')

# ---------- RUN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)