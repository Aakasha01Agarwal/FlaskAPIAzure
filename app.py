import pyodbc
import os
from flask import jsonify, Flask, render_template, request, redirect, url_for, session, flash
import json
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers


load_dotenv()
app = Flask(__name__)
DATABASE_NAME = "doctor-detail"
# DB_PATIENT = "TalkMed-db"
ELASTIC_SEARCH_API = os.environ.get("ELASTIC_SEARCH_API")
ELASTIC_SEARCH_ENDPOINT = os.environ.get("ELASTIC_SEARCH_ENDPOIT")
ELASTIC_SEARCH_INDEX_NAME_PATIENT_SEARCH = "patient_search"
ELASTIC_SEARCH_MAPPING_PATIENT_SEARCH = {
    "properties": {
        "text": {
            "type": "text"
        }
    }
}
PATIENT_SEARCH_ALLOWED_SEARCH =  set(["patient_name", "patient_uid"])




def get_db_connection(DATABASE):
    server_name = "tcp:talkmedserver.database.windows.net"
    
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




# API to search patient by name (supports partial and case-insensitive matching)
# @app.route("/search_name", methods=["GET", "POST"])
# def search_patient_by_name():
#     if request.method == "GET":
#         patient_name = request.args.get('name')
#     else:  # POST request
#         data = request.json
#         patient_name = data.get('name')

#     if not patient_name:
#         return jsonify({"error": "Patient name is required"}), 400

#     conn = None
#     cursor = None
#     try:
#         conn = get_db_connection(DB_PATIENT)
#         cursor = conn.cursor()
        
#         # Use LIKE with % for partial matching (case-insensitive)
#         SQL_QUERY = "SELECT * FROM PatientRecords WHERE LOWER(PatientName) LIKE LOWER(?)"
#         cursor.execute(SQL_QUERY, [f"%{patient_name}%"])
#         rows = cursor.fetchall()

#         if not rows:
#             return jsonify({"response": "No patient found with this name"}), 404

#         # Define column names based on database schema
#         columns = [
#             "RecordID", "PatientID", "PatientName", "Age", "Sex", "AdmissionDate",
#             "AdmissionTime", "AdmissionStatus", "BloodPressure", "HeartRate",
#             "RespiratoryRate", "OxygenSaturation", "Temperature", "Headache",
#             "Fatigue", "Fever"
#         ]
        
#         # Convert rows to dictionary format
#         patients = []
#         for row in rows:
#             patient_data = dict(zip(columns, row))
            
#             # Convert DATE and TIME fields to string
#             if isinstance(patient_data["AdmissionDate"], (pyodbc.Date, pyodbc.Timestamp)):
#                 patient_data["AdmissionDate"] = str(patient_data["AdmissionDate"])
#             if isinstance(patient_data["AdmissionTime"], pyodbc.Time):
#                 patient_data["AdmissionTime"] = str(patient_data["AdmissionTime"])

#             patients.append(patient_data)
        
#         return jsonify({"response": patients})

#     except Exception as e:
#         print(f"Error: {e}")
#         return jsonify({"error": "Internal Server Error"}), 500
#     finally:
#         if cursor:
#             cursor.close()
#         if conn:
#             conn.close()



@app.route("/filter_patients", methods = ["GET", 'POST'])
def filter_patients():

    '''
    
    Takes two params based on the frontend, 
    Text: Input Text query based on what we have to search
    selected_option:  patient_name or patient_uid 
     
    '''

    if request.method == "GET":
        patient_query_text = request.args.get("text", "").strip()
        selected_option = request.args.get("selected_option", "").strip()
    else:  # POST method
        data = request.get_json(silent=True) or {}
        patient_query_text = (data.get("text") or "").strip()
        selected_option = (data.get("selected_option") or "").strip()

    print(patient_query_text, 'this is patient query')
    print(selected_option, 'This is selected option')

    if not patient_query_text:
        return jsonify({"error": "Search query cannot be empty"}), 400
    if selected_option not in PATIENT_SEARCH_ALLOWED_SEARCH:
        return jsonify({"error": "Invalid selected_option"}), 400
    
    client = Elasticsearch(ELASTIC_SEARCH_ENDPOINT,
                           api_key=ELASTIC_SEARCH_API
                            )

    # mapping_response = client.indices.put_mapping(index=ELASTIC_SEARCH_INDEX_NAME_PATIENT_SEARCH, body=ELASTIC_SEARCH_MAPPING_PATIENT_SEARCH)
    patient_query_text = "*"+patient_query_text+"*"
    query = {"query":
         {
             "wildcard":
             {
                 selected_option:
                 {
                     "value" : f"*{patient_query_text}*", 
                     "case_insensitive":True
                 }
             }
         }
         }
    resp = client.search(index=ELASTIC_SEARCH_INDEX_NAME_PATIENT_SEARCH, body=query)
    hits = resp.get("hits", {}).get("hits", [])

    # Extract Results
    result_hits = [hit["_source"] for hit in hits]
   
    print(result_hits)
    
    return jsonify({'response':result_hits})

    # return jsonify(hit["_source"])

    

    


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

    print(username, password, '=========================')
    cursor = None
    conn = None
    try:
        conn = get_db_connection(DATABASE_NAME)
        print('Connection established')
        cursor = conn.cursor()
        SQL_QUERY = "SELECT * FROM doctor_basic_info WHERE username = ? AND pwd = ?"
        cursor.execute(SQL_QUERY, [username, password ])
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        
        if len(rows)>0:
            print("true")
            # Convert the row into a dictionary
            doctor_data = dict(zip(columns, rows[0]))

            return  jsonify({"response": doctor_data})
        else:
            print('False')
            return jsonify({"response": None})
        
    except Exception as e:
        
        return "There is some error", e
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


     
    



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
    # webview.start()
