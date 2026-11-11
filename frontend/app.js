// Leave "" when CloudFront serves both the site and /api/* (no-domain option).
// With a separate API hostname: const API_BASE = "https://api.yourdomain.com";
const API_BASE = "";

const cart = {}; // product_id -> {p, qty}
let products = [];
const $ = (id) => document.getElementById(id);

async function loadProducts() {
  try {
    const r = await fetch(`${API_BASE}/api/products`);
    products = await r.json();
  } catch (e) {
    $("products").textContent = "Could not load products.";
    return;
  }
  const box = $("products");
  box.replaceChildren();
  products.forEach((p) => {
    const d = document.createElement("div");
    d.className = "card";
    const em = document.createElement("div"); em.className = "e"; em.textContent = p.emoji;
    const h = document.createElement("h3"); h.textContent = p.name;
    const ds = document.createElement("p"); ds.textContent = p.description;
    const pr = document.createElement("p"); pr.textContent = `₹${p.price} • stock: ${p.stock}`;
    const b = document.createElement("button");
    b.textContent = p.stock > 0 ? "Add to cart" : "Out of stock";
    b.disabled = p.stock < 1;
    b.onclick = () => addToCart(p);
    d.append(em, h, ds, pr, b);
    box.append(d);
  });
}

function addToCart(p) {
  const c = cart[p.id] || (cart[p.id] = { p, qty: 0 });
  if (c.qty < p.stock) c.qty++;
  renderCart();
}

function renderCart() {
  const ul = $("cartList"); ul.replaceChildren();
  let total = 0, count = 0;
  Object.values(cart).forEach(({ p, qty }) => {
    const li = document.createElement("li");
    li.textContent = `${p.name} × ${qty}`;
    ul.append(li);
    total += p.price * qty; count += qty;
  });
  $("cartTotal").textContent = total.toFixed(2);
  $("cartCount").textContent = `Cart: ${count}`;
}

$("orderBtn").onclick = async () => {
  const items = Object.values(cart).map(({ p, qty }) => ({ product_id: p.id, quantity: qty }));
  if (!items.length) { $("msg").textContent = "Cart is empty."; return; }
  const r = await fetch(`${API_BASE}/api/orders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ customer_name: $("name").value, customer_email: $("email").value, items }),
  });
  const data = await r.json();
  if (r.status === 201) {
    $("msg").textContent = `✅ Order #${data.order_id} placed. Total ₹${data.total}`;
    Object.keys(cart).forEach((k) => delete cart[k]);
    renderCart(); loadProducts();
  } else {
    $("msg").textContent = `❌ ${data.error || "Failed"}`;
  }
};

loadProducts();
