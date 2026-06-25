from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "<h1 style='color:green;font-family:sans-serif'>✅ Flask is working! Your Jyotish AI site will run here.</h1>"

if __name__ == "__main__":
    print("\n✅ Flask started!")
    print("Try these in Chrome one by one:")
    print("  http://127.0.0.1:8080")
    print("  http://localhost:8080\n")
    app.run(host="0.0.0.0", port=8080, debug=True)
