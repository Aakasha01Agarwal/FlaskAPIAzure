import pyodbc
import os
from flask import jsonify, Flask, render_template, request, redirect, url_for, session, flash
import json
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers
import re
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
import datetime
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from flask_cors import CORS

load_dotenv()
app = Flask(__name__)
# CORS(app)   
CORS(app, resources={r"/*": {"origins": "*"}})

DATABASE_NAME = "doctor-detail"
DOCTOR_BASIC_INFO_TABLE = "doctor_basic_info"
PATIENT_BASIC_INFO_TABLE = "patient_basic_info"
OPD_RECORDS_TABLE = "opd_records"
ADMITTED_PATIENT_RECORDS_TABLE = "admitted_patient_records"
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

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Create a thread pool for database operations
db_pool = ThreadPoolExecutor(max_workers=5)

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
        4. Place any extra clinically relevant information that doesn't fit any column into the `other_notes` field as free text.
        5. ONLY RETURN RAW JSON WITHOUT MARKDOWN FORMATTING. Do NOT wrap the output in triple backticks or specify "json".

        Examples:
        {examples}

        Extract relevant structured data from the following real-time conversation text:
        {{query}}
        """
    )
    
    return prompt_template

def process_llm(prompt_template, transcription):
    
    # initialize OpenAI mode
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.1,
        # max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key=OPENAI_API_KEY,
        streaming = True
        # other params...
    )
    print("OpenAI model initialized.")
    
    # initialize outputparser -> chain -> query_input
    output_parser = StrOutputParser()
    chain =  prompt_template | llm | output_parser
    
    # output from OpenAI
    out = chain.invoke({"query": transcription})
    print(f"Output from OpenAI: {out}")

    return out
  
def clean_json_output(llm_output):
    # Remove markdown JSON code blocks
    json_cleaned = re.sub(r'```(?:json)?', '', llm_output, flags=re.I).strip()
    json_cleaned = json_cleaned.strip('` \n')
    
    # Parse JSON safely
    return json.loads(json_cleaned)  

def get_transcription_json(transcription, patient_status="OPD"):
    prompt_template = create_prompt(patient_status)
    llm_output = process_llm(prompt_template, transcription)
    cleaned_output = clean_json_output(llm_output)
    return cleaned_output

def insert_transript_data(transcription_json, selected_option, created_at, cursor, conn):
    print("inserting data")
    try:
        if selected_option == "opd":
            transcription_json['visit_timestamp'] = created_at
            insert_query = f"""
            INSERT INTO {OPD_RECORDS_TABLE} (
                patient_id, doctor_id, visit_timestamp, history_of_presenting_illness
                , treatment_history, addiction_history, family_history, history_of_similar_complaints,
                comorbidities, operative_history, temperature, pulse, bp, rr, spo2, other_notes
            ) VALUES ( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            values = (
                transcription_json.get("patient_id"),
                transcription_json.get("doctor_id"),
                transcription_json.get("visit_timestamp"),
                transcription_json.get("history_of_presenting_illness", ""),
                transcription_json.get("treatment_history", ""),
                transcription_json.get("addiction_history", ""),
                transcription_json.get("family_history", ""),
                transcription_json.get("history_of_similar_complaints", ""),
                transcription_json.get("comorbidities", ""),
                transcription_json.get("operative_history", ""),
                transcription_json.get("temperature", ""),
                transcription_json.get("pulse", ""),
                transcription_json.get("bp", ""),
                transcription_json.get("rr", ""),
                transcription_json.get("spo2", ""),
                transcription_json.get("other_notes", "")
            )
        else:
            transcription_json['admission_timestamp'] = created_at
            insert_query = f"""
            INSERT INTO {ADMITTED_PATIENT_RECORDS_TABLE} (
                patient_id, doctor_id, admission_timestamp, temperature, pulse, bp, rr, spo2, other_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            values = (
                transcription_json.get("patient_id"),
                transcription_json.get("doctor_id"),
                transcription_json.get("admission_timestamp"),
                transcription_json.get("temperature", ""),    
                transcription_json.get("pulse", ""),
                transcription_json.get("bp", ""),
                transcription_json.get("rr", ""),
                transcription_json.get("spo2", ""),
                transcription_json.get("other_notes", "")
            )
        
        cursor.execute(insert_query, values)
        conn.commit()
        print(f"Inserted record successfully in {selected_option} table")
        return True, None  # Success, no error
        
    except Exception as e:
        print(f"error in inserting data: {e}")
        try:
            print("rolling back")
            conn.rollback()  # Rollback the transaction on error
        except:
            pass  # If rollback fails, we still want to report the original error
        return False, str(e)  # Failure, with error message

def validate_field_data_type(field_name, value):
    """
    Validates the data type of a field and returns (processed_value, error_message)
    Always returns a valid value, with any issues noted in error_message
    """
    if value is None or value == "":
        return value, None

    ##out of str datatype cols, adding only bp as it is the only that can be float

    validation_rules = {
        "temperature": {
            "type": float,
            "range": (80, 120),
            "default": 0.0, # to signify an error has occurred;
            "error": "Temperature must be between 80°F and 120°F"
        },
        "pulse": {
            "type": int,
            "range": (0, 1000),
            "default": 0, # to signify an error has occurred;
            "error": "Pulse must be between 0 and 1000 bpm"
        },
        "rr": {
            "type": int,
            "range": (0, 100), 
            "default": 0, # to signify an error has occurred;
            "error": "Respiratory rate must be between 0 and 100"
        },
        "spo2": {
            "type": float,
            "range": (0, 100),
            "default": 0.0, # to signify an error has occurred;
            "error": "SpO2 must be between 0% and 100%"
        },
        "bp": {
            "type": str,
            #"pattern": r'^\d{2,3}/\d{2,3}\s*(?:mmHg)?$',
            "default": "NA", # to signify an error has occurred;
            #"error": "Blood pressure must be in format '120/80 mmHg'"
        }
    }

    if field_name in validation_rules:
        rule = validation_rules[field_name]
        processed_value = value
        # Type validation with default value
        try:
            if rule["type"] == str:
                processed_value = str(value)
            elif rule["type"] == float:
                processed_value = float(value)
            elif rule["type"] == int:
                processed_value = int(value)  # Handle decimal strings
        except (ValueError, TypeError):
            print(value, '=========================')
            processed_value = rule["default"]
            return processed_value, f"{field_name} must be a {rule['type'].__name__}, using default value {rule['default']}"

        # Range validation for numeric fields
        ## currently defaulting to 0 for all invalid values as there is some 
        ##range predefined in AzureSQL. Getting overflow error otherwise.

        if "range" in rule:
            if not (rule["range"][0] <= processed_value <= rule["range"][1]):
                processed_value = rule["default"]
                return processed_value, rule["error"] + f", using default value {rule['default']}"

        # Pattern validation for string fields
        # if "pattern" in rule:
        #     if not re.match(rule["pattern"], processed_value):
        #         processed_value = rule["default"]
        #         return processed_value, rule["error"] + f", using default value {rule['default']}"

        return processed_value, None

    # For non-validated fields, return as is
    return value, None

def validate_transcription_data(transcription_json, selected_option):
    """
    Validates the transcription data and returns (processed_data, validation_notes)
    Always processes the data, with any issues noted in validation_notes
    """
    processed_data = {}
    validation_notes = []

    # Validate all fields that are present
    for field, value in transcription_json.items():
        processed_value, error_msg = validate_field_data_type(field, value)
        processed_data[field] = processed_value
        
        if error_msg:
            validation_notes.append(error_msg)
    print(processed_data, '=========================')
    # Add validation notes to other_notes if any
    if validation_notes:
        existing_notes = transcription_json.get("other_notes", "")
        processed_data["other_notes"] = (
            f"{existing_notes}\nValidation Notes: " + 
            "; ".join(validation_notes)
        ).strip()

    return processed_data, validation_notes

@app.route("/process_transcription", methods = ["GET", 'POST']) 
def process_transcription():
    # Input validation
    if request.method == "GET":
        patient_transcription = request.args.get("text", "").strip()
        selected_option = request.args.get("selected_option", "").strip()
        patient_id = request.args.get("patient_id", "").strip()
        doctor_id = request.args.get("doctor_id", "").strip()
    else:  # POST method
        data = request.get_json(silent=True) or {}
        # Ensure strings are stripped
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = value.strip()
            else:
                data[key] = str(value).strip()
    
    # List the required fields
    required_fields = ["text", "selected_option", "patient_id", "doctor_id"]

    # Check for missing/empty required fields
    for field in required_fields:
        if not data.get(field):  # Empty string or None
            return jsonify({"error": f"Field '{field}' is required"}), 400
    
    patient_transcription = data.get("text")
    selected_option = data.get("selected_option").lower()
    patient_id = data.get("patient_id")
    doctor_id = data.get("doctor_id") 
    created_at = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f") + "0"
    created_at = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%f0")

    if selected_option not in ["opd", "admitted"]:
        return jsonify({"error": f"Invalid selected_option: {selected_option}. Must be either 'OPD' or 'admitted'"}), 400

    if len(patient_transcription) == 0:
        return jsonify({"error": "Patient transcription text is required"}), 400
    
    if len(patient_id) == 0:
        return jsonify({"error": "Patient ID is required"}), 400

    if not patient_id.isdigit():
        return jsonify({"error": "Patient ID must be a valid integer"}), 400
    
    if len(doctor_id) == 0:
        return jsonify({"error": "Doctor ID is required"}), 400

    if not doctor_id.isdigit():
        return jsonify({"error": "Doctor ID must be a valid integer"}), 400

    conn = None
    cursor = None
    transcription_json = {}
    try:
        # Run transcription processing and database connection in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as executor:
            transcription_future = executor.submit(
                get_transcription_json,
                patient_transcription,
                selected_option
            )
            
            db_future = executor.submit(
                get_db_connection,
                DATABASE_NAME
            )
            
            # Get results from both futures
            transcription_json = transcription_future.result()
            conn = db_future.result()

        print('Connection established')
        cursor = conn.cursor()
        print(f"Transcription JSON: {transcription_json}")

        # Validate the transcription data
        processed_data, validation_notes = validate_transcription_data(
            transcription_json, 
            selected_option
        )

        print(f"Validation notes: {validation_notes}")
        # Add metadata to processed data
        processed_data['patient_id'] = patient_id
        processed_data['doctor_id'] = doctor_id
        # processed_data['created_at'] = created_at

        # Insert the processed data
        success, error = insert_transript_data(
            processed_data,
            selected_option,
            created_at,
            cursor,
            conn
        )

        if not success:
            return jsonify({
                "status": "error",
                "message": "Failed to insert record",
                "error": error,
                "processed_data": processed_data,
                "validation_notes": validation_notes
            }), 500

        return jsonify({
            "status": "success",
            "message": "Patient record processed and inserted successfully",
            "data": processed_data,
            "validation_notes": validation_notes
        }), 200
        
    except Exception as e:
        print(f"Error processing transcription: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Failed to process transcription",
            "error": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@app.route("/add_new_patient", methods = ["GET", 'POST'])
def add_new_patient():
    '''
    Add new patient APO
    Inserts a new patient record into the PATIENT_BASIC_INFO_TABLE in the database.
    
    params:
    - patient_uid: (string) Required. (ADHAAR?UID)
    - occupation: (string) Optional. 
    - income: (string) Optional.
    - contact: (string) Required. 
    - addr: (string) Optional.
    - patient_name: (string) Required. 
    - age: (string) Required. 
    - gender: (string) Required. 

    '''
    if request.method == "GET":
        data = {
            "patient_uid": request.args.get("patient_uid", "").strip(),   #required (AADHAR)
            "occupation": request.args.get("occupation", " ").strip(),
            "income": request.args.get("income", " ").strip(),
            "contact": request.args.get("contact", " ").strip(),  #required
            "addr": request.args.get("addr", " ").strip(),
            "patient_name": request.args.get("patient_name", " ").strip(),   #required
            "age": request.args.get("age", " ").strip(),    #  required (i think curr not requried in table)
            "gender": request.args.get("gender", " ").strip(),  # required
        }
    else:  # POST method
        data = request.get_json(silent=True) or {}
        # Ensure strings are stripped
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = value.strip()
    
     # List the required fields
    required_fields = ["patient_uid", "contact", "patient_name", "age", "gender"]

    # Check for missing/empty required fields
    for field in required_fields:
        if not data.get(field):  # Empty string or None
            return jsonify({"error": f"Field '{field}' is required"}), 400
    
    patient_name = data["patient_name"]
    patient_uid = data.get("patient_uid")   # not null but can be empty
    occupation = data.get("occupation") or ""
    contact = data.get("contact") or ""
    addr = data.get("addr") or ""
    gender = data.get("gender")
    income = data.get("income") or " "

     # Age
    age_val = data.get("age") or None
    if age_val:
        try:
            age_val = int(age_val)
        except ValueError:
            return jsonify({"error": "age must be a valid integer"}), 400

     # Income
    income_val = data.get("income") or None
    if income_val:
        try:
            income_val = float(income_val)  # or decimal.Decimal(...)
        except ValueError:
            return jsonify({"error": "income must be a valid decimal/float"}), 400
        
    # Set created_at and updated_at to now if not supplied
    created_at = datetime.datetime.now()
    updated_at = datetime.datetime.now()

    # Build a response dict
    new_patient = {
        "id": patient_uid,
        "patient_uid": patient_uid,
        "occupation": occupation,
        "income": income_val,
        "contact": contact,
        "addr": addr,
        "patient_name": patient_name,
        "age": age_val,
        "gender": gender,
        "created_at": created_at,
        "updated_at": updated_at
    }
    

    print(type(new_patient["created_at"]))
    conn = None
    cursor = None

    try:
        conn = get_db_connection(DATABASE_NAME)
        cursor = conn.cursor()
        print(cursor)

        # Check if a patient with the given patient_uid already exists
        select_query = f"SELECT * FROM {PATIENT_BASIC_INFO_TABLE} WHERE patient_uid = ?"
        cursor.execute(select_query, (patient_uid,))
        row = cursor.fetchone()
        if row:
            columns = [col[0] for col in cursor.description]
            existing_patient = dict(zip(columns, row))
            return jsonify({
                "status": "error",
                "message": "Patient already present",
                "data": existing_patient
            }), 400
        
        
        insert_query = f"""
            INSERT INTO {PATIENT_BASIC_INFO_TABLE} (
                patient_uid,
                occupation,
                income,
                contact,
                addr,
                patient_name,
                age,
                gender,
                created_at,
                updated_at
            ) VALUES ( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        values = (
            patient_uid,
            occupation,
            income_val,
            contact,
            addr,
            patient_name,
            age_val,
            gender,
            created_at,
            updated_at
        )

        cursor.execute(insert_query, values)
        conn.commit()

        

        return jsonify({
            "status": "success",
            "message": "New patient added successfully",
            "data": new_patient
        }), 200

    except Exception as e:
        
        if conn:
            try:
                conn.rollback()
            except Exception as rb_err:
                print("Rollback failed:", rb_err)
        return jsonify({
            "status": "error",
            "message": "Failed to add new patient",
            "error": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()




@app.route("/get_latest_patient_details", methods = ["GET", 'POST']) 
def get_latest_patient_details():
    # Input validation
    if request.method == "GET":
        patient_id = request.args.get("patient_id", "").strip()
        selected_option = request.args.get("selected_option", "").strip()
    else:  # POST method
        data = request.get_json(silent=True) or {}
        patient_id = (data.get("patient_id") or "").strip()
        selected_option = (data.get("selected_option") or "").strip()

    # Validate required fields
    if not patient_id:
        return jsonify({"error": "Patient ID is required"}), 400
    if not selected_option:
        return jsonify({"error": "Selected option is required"}), 400
    
    # Validate selected_option
    if selected_option not in ["OPD", "admitted"]:
        return jsonify({"error": "Invalid selected_option. Must be either 'OPD' or 'admitted'"}), 400

    # Set table and timestamp based on selected option
    if selected_option == "OPD":
        table_name = OPD_RECORDS_TABLE
        timestamp_column = "visit_timestamp"
    else:
        table_name = ADMITTED_PATIENT_RECORDS_TABLE
        timestamp_column = "admission_timestamp"

    conn = None
    cursor = None
    try:
        conn = get_db_connection(DATABASE_NAME)
        print('Connection established')
        cursor = conn.cursor()
        
        # Using TOP 1 instead of LIMIT for SQL Server
        SQL_QUERY = f"""
            SELECT TOP 1 * 
            FROM {table_name} 
            WHERE patient_id = ? 
            ORDER BY {timestamp_column} DESC
        """
        cursor.execute(SQL_QUERY, [patient_id])
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        
        if len(rows) > 0:
            # Convert the row into a dictionary
            patient_data = dict(zip(columns, rows[0]))
            
            # Convert any datetime objects to string for JSON serialization
            for key, value in patient_data.items():
                if isinstance(value, (datetime.date, datetime.datetime)):
                    patient_data[key] = value.isoformat()

            return jsonify({
                "status": "success",
                "message": "Latest patient record retrieved successfully",
                "data": patient_data
            }), 200
        else:
            return jsonify({
                "status": "success",
                "message": "No records found for this patient",
                "data": None
            }), 404
        
    except Exception as e:
        print(f"Error retrieving patient details: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Failed to retrieve patient details",
            "error": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug = True)
    # webview.start()
