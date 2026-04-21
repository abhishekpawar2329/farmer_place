from flask import Flask, render_template, request, redirect, session, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os, json, requests, logging

# ---------- CONFIG ----------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret123")
logging.basicConfig(level=logging.INFO)

UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ---------- DATABASE ----------
db = None

def get_db():
    global db
    if db is None or not db.is_connected():
        db = mysql.connector.connect(
            host=os.environ.get('MYSQLHOST'),
            user=os.environ.get('MYSQLUSER'),
            password=os.environ.get('MYSQLPASSWORD'),
            database=os.environ.get('MYSQLDATABASE'),
            port=int(os.environ.get('MYSQLPORT', 3306))
        )
    return db

def get_cursor():
    return get_db().cursor(dictionary=True)

# ---------- TRANSLATION ----------
def translate_text(text, lang):
    try:
        res = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text, "langpair": f"en|{lang}"},
            timeout=5
        )
        return res.json()["responseData"]["translatedText"]
    except:
        return text

def load_language():
    lang = request.args.get('lang')
    if lang:
        session['lang'] = lang
    lang = session.get('lang', 'en')

    try:
        with open(f"translations/{lang}.json", encoding="utf-8") as f:
            return json.load(f)
    except:
        with open("translations/en.json", encoding="utf-8") as f:
            return json.load(f)

# ---------- AUTH ----------
@app.route('/')
def login_page():
    return render_template('SFM-login.html', t=load_language())

@app.route('/auth', methods=['POST'])
def auth():
    cursor = get_cursor()

    mode = request.form.get('mode')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')

    if mode == "signup":
        name = request.form.get('name')
        hashed = generate_password_hash(password)

        cursor.execute(
            "INSERT INTO users (name,email,password,role) VALUES (%s,%s,%s,%s)",
            (name, email, hashed, role)
        )
        get_db().commit()

        session['user_id'] = cursor.lastrowid
        session['user_role'] = role
        session['user_name'] = name

        return redirect(f"/{role}_dashboard")

    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['user_role'] = user['role']
        session['user_name'] = user['name']
        return redirect(f"/{user['role']}_dashboard")

    return "Invalid credentials"

# ---------- FARMER ----------
@app.route('/farmer_dashboard')
def farmer_dashboard():
    if 'user_role' not in session or session['user_role'] != 'farmer':
        return redirect('/')

    cursor = get_cursor()
    fid = session['user_id']

    cursor.execute("SELECT * FROM products WHERE farmer_id=%s", (fid,))
    products = cursor.fetchall()

    return render_template('farmer_dashboard.html',
                           products=products,
                           farmer_name=session['user_name'],
                           t=load_language())

@app.route('/add_product', methods=['POST'])
def add_product():
    if 'user_role' not in session or session['user_role'] != 'farmer':
        return redirect('/')

    cursor = get_cursor()

    name = request.form.get('name')
    category = request.form.get('category')
    price = request.form.get('price')
    unit = request.form.get('unit')
    quantity = request.form.get('quantity', 0)
    description = request.form.get('description', '')

    if not name or not price:
        return "Missing required fields"

    image = request.files.get('image')
    filename = 'default_crop.png'

    if image and image.filename:
        filename = secure_filename(image.filename)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        image.save(os.path.join(UPLOAD_FOLDER, filename))

    cursor.execute("""
        INSERT INTO products
        (farmer_id,name,category,price,unit,quantity,description,image,status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Listed')
    """, (
        session['user_id'], name, category, price,
        unit, quantity, description, filename
    ))

    get_db().commit()
    return redirect('/farmer_dashboard')

# ---------- BUYER ----------
@app.route('/buyer_dashboard')
def buyer_dashboard():
    cursor = get_cursor()

    cursor.execute("""
        SELECT p.*, u.name farmer_name
        FROM products p
        JOIN users u ON p.farmer_id=u.id
        WHERE p.quantity>0 AND p.status='Listed'
    """)

    products = cursor.fetchall()

    return render_template('buyer_dashboard.html',
                           products=products,
                           t=load_language())

# ---------- CART ----------
@app.route('/add_to_cart/<int:id>', methods=['POST'])
def add_to_cart(id):
    if 'user_role' not in session or session['user_role'] != 'buyer':
        return jsonify(success=False)

    cursor = get_cursor()
    qty = int(request.form.get('quantity', 1))

    cursor.execute("SELECT quantity FROM products WHERE id=%s", (id,))
    p = cursor.fetchone()

    if not p or p['quantity'] < qty:
        return jsonify(success=False)

    cursor.execute("SELECT * FROM cart WHERE buyer_id=%s AND product_id=%s",
                   (session['user_id'], id))
    exist = cursor.fetchone()

    if exist:
        cursor.execute("""
            UPDATE cart 
            SET quantity = quantity + %s 
            WHERE buyer_id = %s AND product_id = %s
        """, (qty, session['user_id'], id))
    else:
        cursor.execute("INSERT INTO cart (buyer_id,product_id,quantity) VALUES (%s,%s,%s)",
                       (session['user_id'], id, qty))

    get_db().commit()
    return jsonify(success=True)

@app.route('/cart')
def cart():
    if 'user_role' not in session:
        return redirect('/')

    cursor = get_cursor()

    cursor.execute("""
        SELECT c.id, p.name, p.price, c.quantity,
        (p.price*c.quantity) total_price
        FROM cart c JOIN products p ON c.product_id=p.id
        WHERE c.buyer_id=%s
    """, (session['user_id'],))

    items = cursor.fetchall()
    total = sum(i['total_price'] for i in items)

    return render_template('cart.html',
                           cart_items=items,
                           total_amount=total,
                           t=load_language())

@app.route('/payment')
def payment_page():
    return redirect('/cart')

# ---------- CHECKOUT ----------
@app.route('/checkout', methods=['POST'])
def checkout():
    cursor = get_cursor()

    cursor.execute("""
        SELECT c.product_id, c.quantity, p.price, p.farmer_id
        FROM cart c JOIN products p ON c.product_id=p.id
        WHERE c.buyer_id=%s
    """, (session['user_id'],))

    items = cursor.fetchall()

    if not items:
        return "Cart is empty"

    for i in items:
        total = i['price'] * i['quantity']

        cursor.execute("""
            INSERT INTO orders (buyer_id, farmer_id, product_id, quantity, total_price, status)
            VALUES (%s,%s,%s,%s,%s,'Confirmed')
        """, (
            session['user_id'],
            i['farmer_id'],
            i['product_id'],
            i['quantity'],
            total
        ))

        cursor.execute("UPDATE products SET quantity=quantity-%s WHERE id=%s",
                       (i['quantity'], i['product_id']))

    cursor.execute("DELETE FROM cart WHERE buyer_id=%s", (session['user_id'],))
    get_db().commit()

    return redirect('/buyer_dashboard')

# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------- RUN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)