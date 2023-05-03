from bottle_suite import BottleSuite, bottle
import socket
import argparse
import time
from pathlib import Path
from string import ascii_letters as letters, digits, punctuation
import secrets
import os
import sqlite3
import pymysql

MIN_PORT = 8000
MAX_PORT = 8999
KEY_LEN = 32
TMP_DB = f"{Path(__file__).parent.resolve()}/tmp.db"
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
        "--jwt",
        type=str,
        help="JWT key",
        default="".join(
            secrets.choice(letters + digits + punctuation) for i in range(KEY_LEN)
        ),
        metavar="JWT_KEY"
    )
    parser.add_argument(
        "--sqlite",
        nargs="?",
        type=str,
        help=f"Path to SQLite database (default: {TMP_DB})",
        const=TMP_DB,
        metavar="PATH"
    )
    parser.add_argument("--dbhost", type=str, help="SQL database host")
    parser.add_argument("--dbname", type=str, help="SQL database name")
    parser.add_argument("--dbuser", type=str, help="SQL database username")
    parser.add_argument("--dbpass", type=str, help="SQL database password")
    parser.add_argument(
        "--cors",
        type=bool,
        help="Enable CORS",
        default=True,
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

    kwargs = {
        "cors": args.cors,
        "jwt": args.jwt,
        "sqlite": args.sqlite,
        "sql": {
            "dbhost": args.dbhost,
            "dbname": args.dbname,
            "dbuser": args.dbuser,
            "dbpass": args.dbpass,
        }
        if args.dbhost
        else False,
    }
    run_args = {"host": args.host, "port": args.port, "reloader": args.reloader}
    while True:
        try:
            print(f"- Using JWT key: {args.jwt}")
            if args.sqlite == TMP_DB:
                print(f"- Creating temp database @ {TMP_DB}")
            app = BottleSuite(**kwargs)
            if args.dashboard:
                app.route("/dashboard/_nuxt/<filename>", method="GET", callback=nuxt)
                app.route(
                    ["/dashboard", "/dashboard<path:path>"],
                    method="GET",
                    callback=dashboard,
                )
                print(f"- View dashboard @ http://{args.host}:{args.port}/dashboard")
            app.run(**run_args)
            if args.sqlite == TMP_DB:
                try:
                    os.remove(TMP_DB)
                    print("\n- Deleting temp database")
                except:
                    pass
            break
        except KeyboardInterrupt:
            pass
        except sqlite3.OperationalError as e:
            print(f"{e} {args.sqlite}".capitalize())
            break
        except pymysql.err.OperationalError as e:
            print(f"{e} {args.sqlite}".capitalize())
            break
        except Exception as e:
            print(f"{type(e)} {e}")
            time.sleep(5)
