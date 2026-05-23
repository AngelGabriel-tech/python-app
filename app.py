from __future__ import annotations

import os
from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///ecommerce.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(60), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    price_cents = db.Column(db.Integer, nullable=False)
    accent = db.Column(db.String(20), nullable=False)
    badge = db.Column(db.String(40), nullable=False)
    inventory = db.Column(db.Integer, nullable=False, default=0)
    featured = db.Column(db.Boolean, nullable=False, default=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(80), nullable=False)
    country = db.Column(db.String(80), nullable=False)
    total_cents = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan", lazy=True)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, nullable=False)
    product_name = db.Column(db.String(120), nullable=False)
    unit_price_cents = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal_cents = db.Column(db.Integer, nullable=False)


SEED_PRODUCTS = [
    {
        "slug": "nordic-desk-lamp",
        "name": "Nordic Desk Lamp",
        "category": "Home Office",
        "description": "A warm matte lamp with a soft-focus glow that makes late-night work feel intentional instead of exhausting.",
        "price_cents": 6400,
        "accent": "#6b5b95",
        "badge": "Bestseller",
        "inventory": 24,
        "featured": True,
    },
    {
        "slug": "trail-copper-bottle",
        "name": "Trail Copper Bottle",
        "category": "Lifestyle",
        "description": "Double-walled steel with a durable powder coat finish and an angled cap for easy daily carry.",
        "price_cents": 2800,
        "accent": "#cc6b49",
        "badge": "New",
        "inventory": 58,
        "featured": True,
    },
    {
        "slug": "linen-market-tote",
        "name": "Linen Market Tote",
        "category": "Accessories",
        "description": "Structured enough for groceries, soft enough for everyday errands, and stitched to hold the shape.",
        "price_cents": 2100,
        "accent": "#0f766e",
        "badge": "Eco",
        "inventory": 40,
        "featured": True,
    },
    {
        "slug": "amber-candle-set",
        "name": "Amber Candle Set",
        "category": "Home",
        "description": "Three layered scents built for relaxed evenings, dinner tables, and slower weekends.",
        "price_cents": 3600,
        "accent": "#b45309",
        "badge": "Giftable",
        "inventory": 18,
        "featured": False,
    },
    {
        "slug": "studio-notebook-pack",
        "name": "Studio Notebook Pack",
        "category": "Stationery",
        "description": "Minimal paper goods with heavy stock pages, stitched spines, and lay-flat binding.",
        "price_cents": 1800,
        "accent": "#2563eb",
        "badge": "Bundle",
        "inventory": 72,
        "featured": False,
    },
    {
        "slug": "ceramic-espresso-cups",
        "name": "Ceramic Espresso Cups",
        "category": "Kitchen",
        "description": "Small-batch ceramic cups designed for the first focused cup of the morning.",
        "price_cents": 2600,
        "accent": "#8b5cf6",
        "badge": "Handmade",
        "inventory": 33,
        "featured": False,
    },
]


def money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


@app.template_filter("money")
def money_filter(cents: int) -> str:
    return money(cents)


def get_cart() -> dict[str, int]:
    cart = session.get("cart", {})
    return {str(product_id): int(quantity) for product_id, quantity in cart.items() if int(quantity) > 0}


def save_cart(cart: dict[str, int]) -> None:
    session["cart"] = cart
    session.modified = True


def build_cart_summary(cart: dict[str, int]) -> dict[str, object]:
    product_ids = [int(product_id) for product_id in cart.keys()]
    products = Product.query.filter(Product.id.in_(product_ids)).all() if product_ids else []
    products_by_id = {str(product.id): product for product in products}

    items = []
    subtotal_cents = 0
    for product_id, quantity in cart.items():
        product = products_by_id.get(product_id)
        if not product:
            continue
        line_total_cents = product.price_cents * quantity
        subtotal_cents += line_total_cents
        items.append(
            {
                "product": product,
                "quantity": quantity,
                "line_total_cents": line_total_cents,
            }
        )

    shipping_cents = 0 if subtotal_cents >= 7500 else (799 if subtotal_cents else 0)
    tax_cents = round(subtotal_cents * 0.08)
    total_cents = subtotal_cents + shipping_cents + tax_cents

    return {
        "items": items,
        "subtotal_cents": subtotal_cents,
        "shipping_cents": shipping_cents,
        "tax_cents": tax_cents,
        "total_cents": total_cents,
    }


def seed_database() -> None:
    if Product.query.count():
        return
    db.session.add_all(Product(**product) for product in SEED_PRODUCTS)
    db.session.commit()


@app.context_processor
def inject_globals() -> dict[str, object]:
    cart = get_cart()
    cart_count = sum(cart.values())
    categories = [row[0] for row in db.session.query(Product.category).distinct().order_by(Product.category).all()]
    return {
        "cart_count": cart_count,
        "site_categories": categories,
    }


@app.get("/")
def index():
    products = Product.query.order_by(Product.featured.desc(), Product.category.asc(), Product.name.asc()).all()
    featured_products = [product for product in products if product.featured]
    categories = sorted({product.category for product in products})
    return render_template(
        "index.html",
        products=products,
        featured_products=featured_products,
        categories=categories,
    )


@app.get("/product/<slug>")
def product_detail(slug: str):
    product = Product.query.filter_by(slug=slug).first_or_404()
    related_products = (
        Product.query.filter(Product.category == product.category, Product.id != product.id)
        .order_by(Product.name.asc())
        .limit(3)
        .all()
    )
    return render_template("product.html", product=product, related_products=related_products)


@app.post("/cart/add/<int:product_id>")
def add_to_cart(product_id: int):
    product = db.session.get(Product, product_id)
    if not product:
        flash("That item is no longer available.", "error")
        return redirect(url_for("index"))

    cart = get_cart()
    quantity = max(1, request.form.get("quantity", type=int) or 1)
    cart[str(product_id)] = cart.get(str(product_id), 0) + quantity
    save_cart(cart)

    flash(f"Added {product.name} to your cart.", "success")
    return redirect(request.referrer or url_for("cart"))


@app.get("/cart")
def cart():
    summary = build_cart_summary(get_cart())
    return render_template("cart.html", summary=summary)


@app.post("/cart/update")
def update_cart():
    cart = get_cart()
    updated_cart: dict[str, int] = {}
    for product_id in list(cart.keys()):
        quantity = request.form.get(f"qty_{product_id}", type=int) or 0
        if quantity > 0:
            updated_cart[product_id] = quantity
    save_cart(updated_cart)
    flash("Cart updated.", "success")
    return redirect(url_for("cart"))


@app.post("/cart/remove/<int:product_id>")
def remove_from_cart(product_id: int):
    cart = get_cart()
    cart.pop(str(product_id), None)
    save_cart(cart)
    flash("Item removed from your cart.", "success")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    summary = build_cart_summary(get_cart())
    if not summary["items"]:
        flash("Your cart is empty.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        country = request.form.get("country", "").strip()

        if not all([customer_name, email, address, city, country]):
            flash("Please fill in every checkout field.", "error")
            return render_template("checkout.html", summary=summary)

        order = Order(
            customer_name=customer_name,
            email=email,
            address=address,
            city=city,
            country=country,
            total_cents=summary["total_cents"],
        )
        db.session.add(order)
        db.session.flush()

        for item in summary["items"]:
            product = item["product"]
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.name,
                    unit_price_cents=product.price_cents,
                    quantity=item["quantity"],
                    subtotal_cents=item["line_total_cents"],
                )
            )

        db.session.commit()
        save_cart({})
        return redirect(url_for("confirmation", order_id=order.id))

    return render_template("checkout.html", summary=summary)


@app.get("/order/<int:order_id>")
def confirmation(order_id: int):
    order = db.session.get(Order, order_id)
    if not order:
        flash("We could not find that order.", "error")
        return redirect(url_for("index"))
    return render_template("confirmation.html", order=order)


with app.app_context():
    db.create_all()
    seed_database()


if __name__ == "__main__":
    app.run(debug=True)