from bottle_suite import BottleSuite, bottle
import socket
import argparse
import time
from pathlib import Path

MIN_PORT = 8000
MAX_PORT = 8999
dist = f"{Path(__file__).parent.parent.resolve()}/bottle_suite/dist"

def checkPort(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
            sock.close()
            return True
        except:
            sock.close()
            return False

def dashboard(path=""):
    # print(dist)
    return bottle.static_file("index.html", dist)

def nuxt(filename):
    print(filename)
    return bottle.static_file(filename, f"{dist}/_nuxt")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        help="Port to listen on",
        dest="port",
        default=MIN_PORT,
    )
    parser.add_argument(
        "--host",
        type=str,
        help="Host to listen on",
        dest="host",
        default="localhost",
    )
    parser.add_argument(
        "-r",
        help="Automatic reloading",
        dest="reloader",
        action="store_true",
    )
    parser.add_argument(
        "-d",
        help="Enable dashboard",
        dest="dashboard",
        action="store_true",
    )
    args = parser.parse_args()

    while True:
        try:
            app = BottleSuite(run_args=args.__dict__)
            if args.dashboard:
                app.route("/dashboard/_nuxt/<filename>", method="GET", callback=nuxt)
                app.route(["/dashboard", "/dashboard<path:path>"], method="GET", callback=dashboard)
                print(f"View dashboard @ http://{args.host}:{args.port}/dashboard")
            app.run(**args.__dict__)
            break
        except Exception as e:
            print(f"{type(e)} {e}")
            time.sleep(5)
