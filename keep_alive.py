from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running 24/7!"

def run():
    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False,
        use_reloader=False
    )

def keep_alive():
    thread = Thread(target=run, daemon=True)
    thread.start()
