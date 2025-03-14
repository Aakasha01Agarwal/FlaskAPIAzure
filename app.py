import pyodbc
import os
from flask import jsonify, Flask, render_template, request, redirect, url_for, session, flash
import json
from dotenv import load_dotenv
from flask_cors import CORS


load_dotenv()
app = Flask(__name__)
CORS(app)



def get_db_connection():
    server_name = "tcp:talkmed-server.database.windows.net"
    db_name = "TalkMed-db"
    uid = os.environ.get("AZURE_UID")
    pwd = os.environ.get("AZURE_PASSWORD")
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
def login(recordid = '2', name = 'Akash'): 
    cursor = None
    conn = None
    try:
        conn = get_db_connection()
        print('Connection established')
        cursor = conn.cursor()
        SQL_QUERY = "SELECT RecordID, PatientName FROM PatientRecords WHERE RecordID = ? AND PatientName = ?"
        cursor.execute(SQL_QUERY, [recordid, name ])
        # columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        if len(rows)>0:
            print("true")
            return {'reponse':dict(rows)}
        else:
            print('Flase')
            return {"response": None}
        
    except Exception as e:
        
        print("i am here")
        return "There is some error", 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


     
    



if __name__ == "__main__":
    app.run(debug=True)
    # webview.start()
