from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = "my-website-development-secret-key"

DATABASE = "database.db"


# =========================================================
# DATABASE
# =========================================================

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_database():

    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'unread',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Upgrade old database
    columns = connection.execute(
        "PRAGMA table_info(users)"
    ).fetchall()

    column_names = [column["name"] for column in columns]

    if "role" not in column_names:
        connection.execute("""
            ALTER TABLE users
            ADD COLUMN role TEXT NOT NULL DEFAULT 'user'
        """)

    connection.commit()
    connection.close()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# SIGN UP
# =========================================================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            return render_template(
                "signup.html",
                error="Please fill in all fields."
            )

        if len(password) < 6:
            return render_template(
                "signup.html",
                error="Password must be at least 6 characters."
            )

        connection = get_db()

        existing_user = connection.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if existing_user:

            connection.close()

            return render_template(
                "signup.html",
                error="An account with this email already exists."
            )

        hashed_password = generate_password_hash(password)

        connection.execute(
            """
            INSERT INTO users
            (name, email, password, role)
            VALUES (?, ?, ?, 'user')
            """,
            (
                name,
                email,
                hashed_password
            )
        )

        connection.commit()
        connection.close()

        return redirect(
            url_for(
                "login",
                registered="1"
            )
        )

    return render_template("signup.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        connection = get_db()

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        connection.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_role"] = user["role"]

            if user["role"] == "admin":
                return redirect(url_for("admin"))

            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Incorrect email or password."
        )

    registered = request.args.get("registered")

    return render_template(
        "login.html",
        registered=registered
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db()

    user = connection.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    total_users = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM users
        """
    ).fetchone()["count"]

    connection.close()

    if not user:

        session.clear()

        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        user=user,
        total_users=total_users
    )


# =========================================================
# PROFILE
# =========================================================

@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db()

    user = connection.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    connection.close()

    if not user:

        session.clear()

        return redirect(url_for("login"))

    return render_template(
        "profile.html",
        user=user
    )


# =========================================================
# SETTINGS
# =========================================================

@app.route("/settings", methods=["GET", "POST"])
def settings():

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db()

    user = connection.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    if not user:

        connection.close()
        session.clear()

        return redirect(url_for("login"))

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not name or not email:

            connection.close()

            return render_template(
                "settings.html",
                user=user,
                error="Name and email are required."
            )

        existing_user = connection.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            AND id != ?
            """,
            (
                email,
                session["user_id"]
            )
        ).fetchone()

        if existing_user:

            connection.close()

            return render_template(
                "settings.html",
                user=user,
                error="That email is already being used."
            )

        if password:

            if len(password) < 6:

                connection.close()

                return render_template(
                    "settings.html",
                    user=user,
                    error="New password must be at least 6 characters."
                )

            hashed_password = generate_password_hash(password)

            connection.execute(
                """
                UPDATE users
                SET name = ?,
                    email = ?,
                    password = ?
                WHERE id = ?
                """,
                (
                    name,
                    email,
                    hashed_password,
                    session["user_id"]
                )
            )

        else:

            connection.execute(
                """
                UPDATE users
                SET name = ?,
                    email = ?
                WHERE id = ?
                """,
                (
                    name,
                    email,
                    session["user_id"]
                )
            )

        connection.commit()

        session["user_name"] = name

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (session["user_id"],)
        ).fetchone()

        connection.close()

        return render_template(
            "settings.html",
            user=user,
            message="Account updated successfully."
        )

    connection.close()

    return render_template(
        "settings.html",
        user=user
    )


# =========================================================
# ADMIN CHECK
# =========================================================

def is_admin():

    return (
        "user_id" in session
        and session.get("user_role") == "admin"
    )


# =========================================================
# ADMIN PANEL
# =========================================================

@app.route("/admin")
def admin():

    if not is_admin():
        return redirect(url_for("login"))

    connection = get_db()

    users = connection.execute(
        """
        SELECT id, name, email, role
        FROM users
        ORDER BY id DESC
        """
    ).fetchall()

    total_users = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM users
        """
    ).fetchone()["count"]

    total_admins = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM users
        WHERE role = 'admin'
        """
    ).fetchone()["count"]

    total_regular_users = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM users
        WHERE role = 'user'
        """
    ).fetchone()["count"]

    total_messages = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM messages
        """
    ).fetchone()["count"]

    unread_messages = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM messages
        WHERE status = 'unread'
        """
    ).fetchone()["count"]

    connection.close()

    return render_template(
        "admin.html",
        users=users,
        total_users=total_users,
        total_admins=total_admins,
        total_regular_users=total_regular_users,
        total_messages=total_messages,
        unread_messages=unread_messages
    )


# =========================================================
# DELETE USER
# =========================================================

@app.route(
    "/admin/delete/<int:user_id>",
    methods=["POST"]
)
def delete_user(user_id):

    if not is_admin():
        return redirect(url_for("login"))

    if user_id == session["user_id"]:
        return redirect(url_for("admin"))

    connection = get_db()

    connection.execute(
        """
        DELETE FROM users
        WHERE id = ?
        """,
        (user_id,)
    )

    connection.commit()
    connection.close()

    return redirect(url_for("admin"))


# =========================================================
# MAKE ADMIN
# =========================================================

@app.route(
    "/admin/make-admin/<int:user_id>",
    methods=["POST"]
)
def make_admin(user_id):

    if not is_admin():
        return redirect(url_for("login"))

    connection = get_db()

    connection.execute(
        """
        UPDATE users
        SET role = 'admin'
        WHERE id = ?
        """,
        (user_id,)
    )

    connection.commit()
    connection.close()

    return redirect(url_for("admin"))


# =========================================================
# REMOVE ADMIN
# =========================================================

@app.route(
    "/admin/remove-admin/<int:user_id>",
    methods=["POST"]
)
def remove_admin(user_id):

    if not is_admin():
        return redirect(url_for("login"))

    if user_id == session["user_id"]:
        return redirect(url_for("admin"))

    connection = get_db()

    connection.execute(
        """
        UPDATE users
        SET role = 'user'
        WHERE id = ?
        """,
        (user_id,)
    )

    connection.commit()
    connection.close()

    return redirect(url_for("admin"))


# =========================================================
# CONTACT
# =========================================================

@app.route(
    "/contact",
    methods=["POST"]
)
def contact():

    name = request.form.get(
        "name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    message = request.form.get(
        "message",
        ""
    ).strip()

    if not name or not email or not message:

        return {
            "success": False,
            "message": "Please fill in all fields."
        }

    connection = get_db()

    connection.execute(
        """
        INSERT INTO messages
        (name, email, message, status)
        VALUES (?, ?, ?, 'unread')
        """,
        (
            name,
            email,
            message
        )
    )

    connection.commit()
    connection.close()

    return {
        "success": True,
        "message": "Your message has been sent successfully!"
    }


# =========================================================
# ADMIN MESSAGES
# =========================================================

@app.route("/admin/messages")
def admin_messages():

    if not is_admin():
        return redirect(url_for("login"))

    connection = get_db()

    messages = connection.execute(
        """
        SELECT *
        FROM messages
        ORDER BY id DESC
        """
    ).fetchall()

    unread_count = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM messages
        WHERE status = 'unread'
        """
    ).fetchone()["count"]

    connection.close()

    return render_template(
        "messages.html",
        messages=messages,
        unread_count=unread_count
    )


# =========================================================
# MARK MESSAGE READ
# =========================================================

@app.route(
    "/admin/messages/read/<int:message_id>",
    methods=["POST"]
)
def mark_message_read(message_id):

    if not is_admin():
        return redirect(url_for("login"))

    connection = get_db()

    connection.execute(
        """
        UPDATE messages
        SET status = 'read'
        WHERE id = ?
        """,
        (message_id,)
    )

    connection.commit()
    connection.close()

    return redirect(url_for("admin_messages"))


# =========================================================
# DELETE MESSAGE
# =========================================================

@app.route(
    "/admin/messages/delete/<int:message_id>",
    methods=["POST"]
)
def delete_message(message_id):

    if not is_admin():
        return redirect(url_for("login"))

    connection = get_db()

    connection.execute(
        """
        DELETE FROM messages
        WHERE id = ?
        """,
        (message_id,)
    )

    connection.commit()
    connection.close()

    return redirect(url_for("admin_messages"))


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    create_database()

    app.run(debug=True)