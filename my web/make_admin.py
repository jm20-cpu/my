import sqlite3

DATABASE = "database.db"

email = input("Enter the email of the account to make admin: ").strip().lower()

connection = sqlite3.connect(DATABASE)

user = connection.execute(
    "SELECT id, name FROM users WHERE email = ?",
    (email,)
).fetchone()

if user:

    connection.execute(
        "UPDATE users SET role = 'admin' WHERE email = ?",
        (email,)
    )

    connection.commit()

    print()
    print("SUCCESS!")
    print(user[1], "is now an administrator.")

else:

    print()
    print("No account was found with that email.")

connection.close()