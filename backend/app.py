
import json
import os
import hmac
from contextlib import contextmanager

import boto3
import pymysql
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymysql.cursors import DictCursor

app = Flask(__name__)

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "")
if FRONTEND_ORIGIN:  # only needed when frontend and API are on different hostnames
    CORS(app, origins=[FRONTEND_ORIGIN])

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")


def _load_db_password():
    """Use Secrets Manager if DB_SECRET_NAME is set, else DB_PASSWORD env var."""
    name = os.environ.get("DB_SECRET_NAME")
    if name:
        sm = boto3.client("secretsmanager", region_name=AWS_REGION)
        secret = json.loads(sm.get_secret_value(SecretId=name)["SecretString"])
        return secret["password"]
    return os.environ["DB_PASSWORD"]


DB = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "cloudcart_app"),
    "database": os.environ.get("DB_NAME", "shopdb"),
    "password": None,
}
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")


@contextmanager
def get_conn():
    if DB["password"] is None:
        DB["password"] = _load_db_password()
    conn = pymysql.connect(
        host=DB["host"], port=DB["port"], user=DB["user"], password=DB["password"],
        database=DB["database"], cursorclass=DictCursor, autocommit=False,
        connect_timeout=5,
    )
    try:
        yield conn
    finally:
        conn.close()


def require_admin():
    key = request.headers.get("X-Admin-Key", "")
    if not ADMIN_API_KEY or not hmac.compare_digest(key, ADMIN_API_KEY):
        return jsonify(error="unauthorized"), 401
    return None


def money(row):
    row = dict(row)
    for k, v in row.items():
        if hasattr(v, "quantize"):  # Decimal
            row[k] = float(v)
        elif hasattr(v, "isoformat"):
            row[k] = v.isoformat()
    return row


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/api/products")
def list_products():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,name,description,price,stock,emoji FROM products "
                    "WHERE active=1 ORDER BY id")
        return jsonify([money(r) for r in cur.fetchall()])


@app.post("/api/orders")
def create_order():
    data = request.get_json(silent=True) or {}
    name = str(data.get("customer_name", "")).strip()[:120]
    email = str(data.get("customer_email", "")).strip()[:200]
    items = data.get("items")
    if not name or "@" not in email or not isinstance(items, list) or not items:
        return jsonify(error="customer_name, customer_email and items are required"), 400

    wanted = {}
    try:
        for it in items:
            pid, qty = int(it["product_id"]), int(it["quantity"])
            if qty < 1 or qty > 100:
                raise ValueError
            wanted[pid] = wanted.get(pid, 0) + qty
    except (KeyError, ValueError, TypeError):
        return jsonify(error="invalid items"), 400

    with get_conn() as conn:
        try:
            with conn.cursor() as cur:
                total = 0
                lines = []
                for pid in sorted(wanted):  # consistent lock order avoids deadlocks
                    cur.execute("SELECT id,name,price,stock FROM products "
                                "WHERE id=%s AND active=1 FOR UPDATE", (pid,))
                    p = cur.fetchone()
                    if not p:
                        conn.rollback()
                        return jsonify(error=f"product {pid} not found"), 404
                    if p["stock"] < wanted[pid]:
                        conn.rollback()
                        return jsonify(error=f"insufficient stock for {p['name']}",
                                       available=p["stock"]), 409
                    cur.execute("UPDATE products SET stock=stock-%s WHERE id=%s",
                                (wanted[pid], pid))
                    total += p["price"] * wanted[pid]
                    lines.append((pid, wanted[pid], p["price"]))

                cur.execute("INSERT INTO orders (customer_name,customer_email,total) "
                            "VALUES (%s,%s,%s)", (name, email, total))
                order_id = cur.lastrowid
                cur.executemany("INSERT INTO order_items (order_id,product_id,quantity,unit_price) "
                                "VALUES (%s,%s,%s,%s)",
                                [(order_id, a, b, c) for a, b, c in lines])
            conn.commit()
        except Exception:
            conn.rollback()
            app.logger.exception("order failed")
            return jsonify(error="could not place order"), 500

    return jsonify(order_id=order_id, total=float(total), status="PLACED"), 201


@app.get("/api/orders/<int:order_id>")
def get_order(order_id):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM orders WHERE id=%s", (order_id,))
        o = cur.fetchone()
        if not o:
            return jsonify(error="not found"), 404
        cur.execute("SELECT product_id,quantity,unit_price FROM order_items WHERE order_id=%s",
                    (order_id,))
        o = money(o)
        o["items"] = [money(r) for r in cur.fetchall()]
        return jsonify(o)


@app.post("/api/admin/products")
def admin_add_product():
    denied = require_admin()
    if denied:
        return denied
    d = request.get_json(silent=True) or {}
    try:
        name = str(d["name"]).strip()[:120]
        price = float(d["price"])
        stock = int(d.get("stock", 0))
        if not name or price < 0 or stock < 0:
            raise ValueError
    except (KeyError, ValueError, TypeError):
        return jsonify(error="name, price (>=0), stock (>=0) required"), 400
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO products (name,description,price,stock,emoji) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (name, str(d.get("description", ""))[:500], price, stock,
                     str(d.get("emoji", "📦"))[:8]))
        conn.commit()
        return jsonify(id=cur.lastrowid), 201


@app.patch("/api/admin/products/<int:pid>")
def admin_update_product(pid):
    denied = require_admin()
    if denied:
        return denied
    d = request.get_json(silent=True) or {}
    allowed = {"name", "description", "price", "stock", "emoji", "active"}
    fields = {k: v for k, v in d.items() if k in allowed}
    if not fields:
        return jsonify(error="no valid fields"), 400
    sets = ", ".join(f"{k}=%s" for k in fields)  # keys come from the whitelist only
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE products SET {sets} WHERE id=%s", (*fields.values(), pid))
        conn.commit()
        return jsonify(updated=cur.rowcount)


@app.get("/api/admin/orders")
def admin_orders():
    denied = require_admin()
    if denied:
        return denied
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 50")
        return jsonify([money(r) for r in cur.fetchall()])


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
