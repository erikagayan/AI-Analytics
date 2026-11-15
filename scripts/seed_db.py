import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sales.db"
TODAY = date.today()
random.seed(42)  # воспроизводимые данные

SCHEMA = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    city TEXT NOT NULL,
    created_at DATE NOT NULL
);
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    order_date DATE NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL
);
"""

FIRST = [
    "Ivan",
    "Anna",
    "Petr",
    "Olga",
    "Dmitry",
    "Elena",
    "Sergey",
    "Maria",
    "Alex",
    "Natalia",
]
LAST = [
    "Ivanov",
    "Petrova",
    "Sidorov",
    "Smirnova",
    "Kuznetsov",
    "Popova",
    "Volkov",
    "Sokolova",
]
CITIES = ["Moscow", "Berlin", "Warsaw", "Paris", "Prague", "Madrid"]
CATALOG = {
    "Electronics": [
        "Headphones",
        "Keyboard",
        "Mouse",
        "Monitor",
        "Webcam",
        "Charger",
        "Speaker",
    ],
    "Home": ["Lamp", "Chair", "Desk", "Mug", "Blanket", "Vase", "Clock"],
    "Sports": ["Yoga Mat", "Dumbbells", "Bottle", "Jump Rope", "Backpack", "Gloves"],
    "Books": ["Python Guide", "SQL Basics", "Data Science", "Novel", "Notebook"],
}
N_CUSTOMERS = 80
N_CHURNED = 10  # перестали покупать > 3 месяцев назад


def main() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    DB_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    # products
    products = []
    for category, names in CATALOG.items():
        for name in names:
            products.append((name, category, round(random.uniform(5, 300), 2)))
    conn.executemany(
        "INSERT INTO products (name, category, price) VALUES (?,?,?)", products
    )
    price_by_id = {i + 1: p[2] for i, p in enumerate(products)}

    # customers + их orders
    churned_ids = set(random.sample(range(1, N_CUSTOMERS + 1), N_CHURNED))
    for cid in range(1, N_CUSTOMERS + 1):
        created = TODAY - timedelta(days=random.randint(330, 365))
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        conn.execute(
            "INSERT INTO customers VALUES (?,?,?,?,?)",
            (cid, name, f"user{cid}@example.com", random.choice(CITIES), created),
        )

        # последний день активности клиента
        if cid in churned_ids:
            last_active = TODAY - timedelta(days=random.randint(100, 200))
        else:
            last_active = TODAY - timedelta(days=random.randint(0, 60))

        span = (last_active - created).days
        order_dates = [
            created + timedelta(days=random.randint(0, span))
            for _ in range(random.randint(4, 25))
        ]
        order_dates.append(last_active)  # гарантируем последний заказ

        for od in order_dates:
            status = random.choices(["completed", "cancelled"], weights=[93, 7])[0]
            cur = conn.execute(
                "INSERT INTO orders (customer_id, order_date, status) VALUES (?,?,?)",
                (cid, od, status),
            )
            for pid in random.sample(list(price_by_id), random.randint(1, 4)):
                conn.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?,?,?,?)",
                    (cur.lastrowid, pid, random.randint(1, 3), price_by_id[pid]),
                )

    conn.commit()
    conn.close()
    print(f"Done: {DB_PATH}")
    print(f"Churned customer ids: {sorted(churned_ids)}")


if __name__ == "__main__":
    main()
