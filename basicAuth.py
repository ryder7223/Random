import time
from flask import request, Response, render_template_string, Flask
from functools import wraps
import base64

AUTH_USERS = {
    "user": "pass"
}

def convertTime(timeText):
    parts = timeText.split(":")
    hour = int(parts[0])
    minute = parts[1]
    second = parts[2]

    if hour == 0:
        hour = 12
        suffix = " AM"
    elif hour < 12:
        suffix = " AM"
    elif hour == 12:
        suffix = " PM"
    else:
        hour = hour % 12
        suffix = " PM"

    return f"{hour}:{minute}:{second}{suffix}"

def getFormattedTimestamp(epochTime=None):
    if epochTime is None:
        epochTime = time.time()

    localTime = time.localtime(epochTime)

    datePart = time.strftime("%Y-%m-%d", localTime)
    time24 = time.strftime("%H:%M:%S", localTime)
    time12 = convertTime(time24)

    return f"{datePart} {time12}"

def getClientIp():
    if request.headers.get("X-Forwarded-For"):
        # Handles proxies/load balancers
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr

def logAuthEvent(event, username=None):
    clientIp = getClientIp()
    timestamp = getFormattedTimestamp()
    print(f"\n[{timestamp}] AUTH {event} | user={username} | ip={clientIp}")

def checkAuth(authHeader):
    if not authHeader:
        logAuthEvent("missing_auth_header")
        return False

    try:
        scheme, encoded = authHeader.split(" ", 1)
        if scheme.lower() != "basic":
            logAuthEvent("invalid_scheme")
            return False

        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)

        storedPassword = AUTH_USERS.get(username)
        if storedPassword is None:
            logAuthEvent("unknown_user", username)
            return False

        if storedPassword != password:
            logAuthEvent("bad_password", username)
            return False

        # THIS is the successful "login"
        logAuthEvent("success", username)
        return True

    except Exception as e:
        logAuthEvent(f"auth_exception:{e}")
        return False

def authenticate():
    return Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="Protected"'}
    )

def requireAuth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        authHeader = request.headers.get("Authorization")
        if not checkAuth(authHeader):
            return authenticate()
        return func(*args, **kwargs)
    return wrapper

app = Flask(__name__)

@app.route('/')
@requireAuth
def main():
    return render_template_string("Hi")

app.run(host="0.0.0.0", port=5016)