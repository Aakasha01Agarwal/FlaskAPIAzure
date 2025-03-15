import pyodbc
import os
from flask import jsonify, Flask, render_template, request, redirect, url_for, session, flash
import json
from dotenv import load_dotenv


load_dotenv()
app = Flask(__name__)



def get_db_connection():
    server_name = "tcp:talkmed-server.database.windows.net"
    db_name = "doctor-details"
    uid = os.environ.get("AZURE_UID")
    pwd = os.environ.get("AZURE_PASSWORD")
    
    print(uid, pwd)

    uid_hard = "CloudSAce057eeb"
    pwdhard = "Gbsssrdjk@#6"
    print(uid_hard, pwdhard)

    server = "Server="+str(server_name)
    db = "Database="+str(db_name)
    uid_str = "Uid="+uid
    pwd_str = "PwD="+pwd
    connection_string = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"{server};{db};{uid_str};{pwd_str};Trusted_connection=no"
    )
    return pyodbc.connect(connection_string)

@app.route("/login", methods=["GET", "POST"])
def login(): 

    if request.method == "GET":
        username = request.args.get('username')
        password = request.args.get('password')
    else:  # POST method
        data = request.json
        username = data.get('username')
        password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400


    # username = request.args.get('username')
    # password = request.args.get('password')
    print(username, password, '=========================')
    cursor = None
    conn = None
    try:
        conn = get_db_connection()
        print('Connection established')
        cursor = conn.cursor()
        SQL_QUERY = "SELECT * FROM doctors WHERE username = ? AND password = ?"
        cursor.execute(SQL_QUERY, [username, password ])
        # columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        
        if len(rows)>0:
            print("true")
            columns = ["id", "username", "password", "email_id", "mobile", "first_name", "middle_name", "last_name", "role"]
            # Convert the row into a dictionary
            doctor_data = dict(zip(columns, rows[0]))

            return  jsonify({"response": doctor_data})
        else:
            print('False')
            return jsonify({"response": None})
        
    except Exception as e:
        
        
        return "There is some error", 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


     
    



if __name__ == "__main__":
    app.run(debug=True)
    # webview.start()
