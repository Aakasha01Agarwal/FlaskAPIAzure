import pyodbc
import os
from flask import jsonify, Flask, render_template, request, redirect, url_for, session, flash
import json
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers
import re
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_deepseek import ChatDeepSeek

load_dotenv()
app = Flask(__name__)
DATABASE_NAME = "doctor-detail"
DOCTOR_BASIC_INFO_TABLE = "doctor_basic_info"
PATIENT_BASIC_INFO_TABLE = "patient_basic_info"
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

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")



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
        return jsonify({'response':[]})
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

@app.route("/get_patient_by_uid", methods = ["GET", 'POST']) 
def get_patient_by_uid():
    if request.method == "GET":
        patient_uid = request.args.get("patient_uid", "").strip()
        
    else:  # POST method
        data = request.get_json(silent=True) or {}
        patient_uid = (data.get("patient_uid") or "").strip()
    
    

    try:
        conn = get_db_connection(DATABASE_NAME)
        print('Connection established')
        cursor = conn.cursor()
        
        SQL_QUERY = f"Select * from {PATIENT_BASIC_INFO_TABLE} where patient_uid = ?"
        cursor.execute(SQL_QUERY, [patient_uid ])
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        
        if len(rows)>0:
            print("true")
            # Convert the row into a dictionary
            patient_data = dict(zip(columns, rows[0]))

            return  jsonify({"response": patient_data})
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
        SQL_QUERY = f"SELECT * FROM {DOCTOR_BASIC_INFO_TABLE} WHERE username = ? AND pwd = ?"
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


def create_prompt(patient_status="OPD"):
    examples = '''
    Example 1 (OPD Visit):
    Conversation:
    Good morning. How are you feeling today? I've had fever of 101°F since yesterday and feel weak. I also have mild headache. Have you had similar symptoms earlier? Yes, I have asthma history. Let's see your vitals. BP 130/85 mmHg, heart rate 90 bpm, oxygen saturation at 97%.
    
    Extracted JSON:
    {{
        "history_of_presenting_illness": "Fever since last night, mild headache, weakness.",
        "comorbidities": "Asthma",
        "temperature": 101.0,
        "bp": "130/85 mmHg",
        "pulse": 90,
        "spo2": 97.0
    }}

    Example 2 (Admitted Patient):
    Conversation: 
    Hi, how are you today? I have trouble breathing for two days now. No fever or chills though. I did have surgery last year for a lung issue. Okay, your BP is 118/76 mmHg, heart rate is 82 bpm, respiratory rate 20 breaths/minute, oxygen saturation is 96% on room air.

    Extracted JSON:
    {{
        "history_of_presenting_illness": "Trouble breathing for two days, no fever or chills.",
        "operative_history": "Lung surgery last year",
        "bp": "118/76 mmHg",
        "pulse": 82,
        "rr": 20,
        "spo2": 96.0
    }}
    '''

    schema_opd = """
    {{
        "history_of_presenting_illness": "",
        "treatment_history": "",
        "addiction_history": "",
        "family_history": "",
        "history_of_similar_complaints": "",
        "comorbidities": "",
        "operative_history": "",
        "temperature": "",
        "pulse": "",
        "bp": "",
        "rr": "",
        "spo2": "",
        "other_notes": ""
    }}
    """

    schema_admitted = """
    {{
        "temperature": "",
        "pulse": "",
        "bp": "",
        "rr": "",
        "spo2": "",
        "other_notes": ""
    }}
    """

    schema = schema_opd if patient_status == "OPD" else schema_admitted

    prompt_template = PromptTemplate(
        input_variables=["query"],
        template=f"""
        You're an AI assistant that extracts structured medical data from real-time conversational text between doctors and patients. The audio is transcribed directly to text without explicit speaker identification tags.

        Schema:
        {schema}

        **Extraction rules:**
        1. Only include fields if you find explicit information in the conversation.
        2. If information for a specific column isn't present, **omit that field** completely.
        3. Convert temperature to Fahrenheit if mentioned in Celsius.
        4. Place any extra clinically relevant information that doesn’t fit any column into the `other_notes` field as free text.
        5. ONLY RETURN RAW JSON WITHOUT MARKDOWN FORMATTING. Do NOT wrap the output in triple backticks or specify "json".

        Examples:
        {examples}

        Extract relevant structured data from the following real-time conversation text:
        {{query}}
        """
    )
    
    return prompt_template

def process_deepseek(prompt_template, transcription):
    
    # initialize deepseek mode
    llm = ChatDeepSeek(
        model="deepseek-chat",
        temperature=0.1,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=DEEPSEEK_API_KEY,
        streaming = True
        # other params...
    )
    print("Deepseek ChatDeepSeek initialized.")
    
    # initialize outputparser -> chain -> query_input
    output_parser = StrOutputParser()
    chain =  prompt_template | llm | output_parser
    
    # output from deepseek
    out = chain.invoke({"query": transcription})
    print(f"Output from deepseek: {out}")

    return out
  
def clean_json_output(llm_output):
    # Remove markdown JSON code blocks
    json_cleaned = re.sub(r'```(?:json)?', '', llm_output, flags=re.I).strip()
    json_cleaned = json_cleaned.strip('` \n')
    
    # Parse JSON safely
    return json.loads(json_cleaned)  

def process_transcription(transcription, patient_status="OPD"):
    prompt_template = create_prompt(patient_status)
    llm_output = process_deepseek(prompt_template, transcription)
    cleaned_output = clean_json_output(llm_output)
    return cleaned_output

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
    # webview.start()
