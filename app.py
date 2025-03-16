import pyodbc
import os
from flask import jsonify, Flask, render_template, request, redirect, url_for, session, flash
import json
from dotenv import load_dotenv


load_dotenv()
app = Flask(__name__)
DB_DOCTOR = "doctor-details"
DB_PATIENT = "TalkMed-db"


def get_db_connection(DATABASE):
    server_name = "tcp:talkmed-server.database.windows.net"
    
    uid = os.environ.get("AZURE_UID")
    pwd = os.environ.get("AZURE_PASSWORD")
    
    print(uid, pwd)

 
    server = "Server="+str(server_name)
    db = "Database="+str(DATABASE)
    uid_str = "Uid="+uid
    pwd_str = "PwD="+pwd
    connection_string = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"{server};{db};{uid_str};{pwd_str};Trusted_connection=no"
    )
    return pyodbc.connect(connection_string)


@app.route("/search_name", methods=["GET", "POST"])
def search_patient_by_name():
    if request.method == "GET":
        patient_name = request.args.get('name')
    else:  # POST request
        data = request.json
        patient_name = data.get('name')

    if not patient_name:
        return jsonify({"error": "Patient name is required"}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection(DB_PATIENT)
        cursor = conn.cursor()
        
        # Convert patient_name to lowercase to perform case-insensitive search
        SQL_QUERY = "SELECT * FROM PatientRecords WHERE LOWER(PatientName) = LOWER(?)"
        cursor.execute(SQL_QUERY, [patient_name])
        rows = cursor.fetchall()

        if not rows:
            return jsonify({"response": "No patient found with this name"}), 404

        # Define column names based on database schema
        columns = [
            "RecordID", "PatientID", "PatientName", "Age", "Sex", "AdmissionDate",
            "AdmissionTime", "AdmissionStatus", "BloodPressure", "HeartRate",
            "RespiratoryRate", "OxygenSaturation", "Temperature", "Headache",
            "Fatigue", "Fever"
        ]
        
        # Convert rows to dictionary format
        patients = []
        for row in rows:
            patient_data = dict(zip(columns, row))
            
            # Convert DATE and TIME fields to string
            if isinstance(patient_data["AdmissionDate"], (pyodbc.Date, pyodbc.Timestamp)):
                patient_data["AdmissionDate"] = str(patient_data["AdmissionDate"])
            if isinstance(patient_data["AdmissionTime"], pyodbc.Time):
                patient_data["AdmissionTime"] = str(patient_data["AdmissionTime"])

            patients.append(patient_data)
        
        return jsonify({"response": patients})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

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
        conn = get_db_connection(DB_DOCTOR)
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
