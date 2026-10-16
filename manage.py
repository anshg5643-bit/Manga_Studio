"""Small admin tool for the local user database.
python manage.py list
python manage.py reset-password you@example.com NewPassword123
python manage.py delete-user you@example.com"""
import sqlite3, sys, os
from werkzeug.security import generate_password_hash
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "users.db")
c = sqlite3.connect(DB); a = sys.argv[1:]
if a[:1] == ["list"]:
    for r in c.execute("SELECT id,email,name,created,google_sub IS NOT NULL FROM users"): print(r)
elif a[:1] == ["reset-password"] and len(a) == 3:
    if len(a[2]) < 8: sys.exit("Password must be at least 8 characters.")
    n = c.execute("UPDATE users SET pw_hash=? WHERE email=?", (generate_password_hash(a[2]), a[1].lower())).rowcount; c.commit()
    print("updated" if n else "no such user")
elif a[:1] == ["delete-user"] and len(a) == 2:
    n = c.execute("DELETE FROM users WHERE email=?", (a[1].lower(),)).rowcount; c.commit(); print("deleted" if n else "no such user")
else:
    print(__doc__)
