import os, sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
DB = os.path.join(os.path.dirname(__file__), "shop.db")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    con=db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'admin');
    CREATE TABLE IF NOT EXISTS products(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, sku TEXT UNIQUE,
      category TEXT, buy_price REAL NOT NULL DEFAULT 0, sell_price REAL NOT NULL DEFAULT 0,
      stock INTEGER NOT NULL DEFAULT 0, low_stock INTEGER NOT NULL DEFAULT 5);
    CREATE TABLE IF NOT EXISTS customers(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT, email TEXT,
      balance REAL NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS sales(
      id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, total REAL NOT NULL,
      payment_method TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(customer_id) REFERENCES customers(id));
    CREATE TABLE IF NOT EXISTS sale_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
      quantity INTEGER NOT NULL, price REAL NOT NULL,
      FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE,
      FOREIGN KEY(product_id) REFERENCES products(id));
    """)
    if not con.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        con.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",
                    ("admin", generate_password_hash("admin123"), "admin"))
    con.commit(); con.close()

def login_required(f):
    @wraps(f)
    def wrapper(*a,**kw):
        if "user_id" not in session: return redirect(url_for("login"))
        return f(*a,**kw)
    return wrapper

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form["username"].strip(); p=request.form["password"]
        con=db(); user=con.execute("SELECT * FROM users WHERE username=?",(u,)).fetchone(); con.close()
        if user and check_password_hash(user["password"],p):
            session["user_id"]=user["id"]; session["username"]=user["username"]; session["role"]=user["role"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password","error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/")
@login_required
def dashboard():
    con=db()
    stats={
      "products": con.execute("SELECT COUNT(*) c FROM products").fetchone()["c"],
      "stock": con.execute("SELECT COALESCE(SUM(stock),0) s FROM products").fetchone()["s"],
      "sales": con.execute("SELECT COALESCE(SUM(total),0) s FROM sales WHERE date(created_at)=date('now','localtime')").fetchone()["s"],
      "low": con.execute("SELECT COUNT(*) c FROM products WHERE stock<=low_stock").fetchone()["c"],
    }
    recent=con.execute("""SELECT s.*, COALESCE(c.name,'Walk-in customer') customer
                         FROM sales s LEFT JOIN customers c ON c.id=s.customer_id
                         ORDER BY s.id DESC LIMIT 8""").fetchall()
    con.close()
    return render_template("dashboard.html",stats=stats,recent=recent)

@app.route("/products")
@login_required
def products():
    q=request.args.get("q","").strip()
    con=db()
    rows=con.execute("""SELECT * FROM products WHERE name LIKE ? OR COALESCE(sku,'') LIKE ?
                        OR COALESCE(category,'') LIKE ? ORDER BY id DESC""",
                     (f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
    con.close(); return render_template("products.html",products=rows,q=q)

@app.route("/products/add", methods=["GET","POST"])
@login_required
def add_product():
    if request.method=="POST":
        try:
            con=db()
            con.execute("""INSERT INTO products(name,sku,category,buy_price,sell_price,stock,low_stock)
                           VALUES(?,?,?,?,?,?,?)""",
                        (request.form["name"],request.form["sku"] or None,request.form["category"],
                         float(request.form["buy_price"] or 0),float(request.form["sell_price"] or 0),
                         int(request.form["stock"] or 0),int(request.form["low_stock"] or 5)))
            con.commit(); con.close(); flash("Product added","success"); return redirect(url_for("products"))
        except sqlite3.IntegrityError: flash("SKU already exists","error")
        except Exception as e: flash(str(e),"error")
    return render_template("product_form.html",product=None)

@app.route("/products/edit/<int:pid>", methods=["GET","POST"])
@login_required
def edit_product(pid):
    con=db(); product=con.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
    if not product: con.close(); return "Product not found",404
    if request.method=="POST":
        try:
            con.execute("""UPDATE products SET name=?,sku=?,category=?,buy_price=?,sell_price=?,stock=?,low_stock=? WHERE id=?""",
                        (request.form["name"],request.form["sku"] or None,request.form["category"],
                         float(request.form["buy_price"] or 0),float(request.form["sell_price"] or 0),
                         int(request.form["stock"] or 0),int(request.form["low_stock"] or 5),pid))
            con.commit(); con.close(); flash("Product updated","success"); return redirect(url_for("products"))
        except sqlite3.IntegrityError: flash("SKU already exists","error")
    con.close(); return render_template("product_form.html",product=product)

@app.post("/products/delete/<int:pid>")
@login_required
def delete_product(pid):
    con=db(); con.execute("DELETE FROM products WHERE id=?",(pid,)); con.commit(); con.close()
    flash("Product deleted","success"); return redirect(url_for("products"))

@app.route("/pos")
@login_required
def pos():
    con=db()
    products=con.execute("SELECT * FROM products WHERE stock>0 ORDER BY name").fetchall()
    customers=con.execute("SELECT * FROM customers ORDER BY name").fetchall()
    con.close(); return render_template("pos.html",products=products,customers=customers)

@app.post("/api/sale")
@login_required
def api_sale():
    data=request.get_json()
    items=data.get("items",[])
    if not items: return jsonify(ok=False,error="Cart is empty"),400
    con=db()
    try:
        total=0; checked=[]
        for x in items:
            p=con.execute("SELECT * FROM products WHERE id=?",(int(x["id"]),)).fetchone()
            qty=int(x["qty"])
            if not p or qty<1 or p["stock"]<qty: raise ValueError(f"Insufficient stock for {p['name'] if p else 'product'}")
            total += p["sell_price"]*qty; checked.append((p,qty))
        cid=data.get("customer_id") or None
        cur=con.execute("INSERT INTO sales(customer_id,total,payment_method) VALUES(?,?,?)",
                        (cid,total,data.get("payment_method","Cash")))
        sid=cur.lastrowid
        for p,qty in checked:
            con.execute("INSERT INTO sale_items(sale_id,product_id,quantity,price) VALUES(?,?,?,?)",
                        (sid,p["id"],qty,p["sell_price"]))
            con.execute("UPDATE products SET stock=stock-? WHERE id=?",(qty,p["id"]))
        con.commit()
        return jsonify(ok=True,sale_id=sid,total=round(total,2))
    except Exception as e:
        con.rollback(); return jsonify(ok=False,error=str(e)),400
    finally: con.close()

@app.route("/sales")
@login_required
def sales():
    con=db()
    rows=con.execute("""SELECT s.*,COALESCE(c.name,'Walk-in customer') customer
                        FROM sales s LEFT JOIN customers c ON c.id=s.customer_id ORDER BY s.id DESC""").fetchall()
    con.close(); return render_template("sales.html",sales=rows)

@app.route("/receipt/<int:sid>")
@login_required
def receipt(sid):
    con=db()
    sale=con.execute("""SELECT s.*,COALESCE(c.name,'Walk-in customer') customer, c.phone
                        FROM sales s LEFT JOIN customers c ON c.id=s.customer_id WHERE s.id=?""",(sid,)).fetchone()
    items=con.execute("""SELECT si.*,p.name,p.sku FROM sale_items si JOIN products p ON p.id=si.product_id
                         WHERE si.sale_id=?""",(sid,)).fetchall()
    con.close()
    if not sale:return "Sale not found",404
    return render_template("receipt.html",sale=sale,items=items)

@app.route("/customers")
@login_required
def customers():
    con=db(); rows=con.execute("SELECT * FROM customers ORDER BY name").fetchall(); con.close()
    return render_template("customers.html",customers=rows)

@app.route("/customers/add",methods=["GET","POST"])
@login_required
def add_customer():
    if request.method=="POST":
        con=db(); con.execute("INSERT INTO customers(name,phone,email,balance) VALUES(?,?,?,?)",
                              (request.form["name"],request.form["phone"],request.form["email"],float(request.form["balance"] or 0)))
        con.commit(); con.close(); flash("Customer added","success"); return redirect(url_for("customers"))
    return render_template("customer_form.html")

@app.route("/reports")
@login_required
def reports():
    con=db()
    summary=con.execute("""SELECT COUNT(*) count,COALESCE(SUM(total),0) revenue FROM sales
                           WHERE date(created_at)=date('now','localtime')""").fetchone()
    best=con.execute("""SELECT p.name,SUM(si.quantity) qty,SUM(si.quantity*si.price) revenue
                        FROM sale_items si JOIN products p ON p.id=si.product_id
                        GROUP BY p.id ORDER BY qty DESC LIMIT 10""").fetchall()
    con.close(); return render_template("reports.html",summary=summary,best=best)

init_db()
if __name__=="__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
