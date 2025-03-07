from flask import Flask, render_template, request, send_file
import pandas as pd
import numpy as np
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Folder to store uploaded files
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
ALLOWED_EXTENSIONS = {"xlsx", "xlsm", "csv"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER

# Ensure upload and output folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Check file format
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to clean data
def clean_data(file_path):
    # Read file
    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path, engine="openpyxl")

    # Backup original columns
    original_headers = df.columns.tolist()

    # Standardized header mapping
    header_mapping = {
        "Sample_ID": "Sample ID",
        "Test_Date": "Test Date",
        "Temp (°C)": "Temperature (°C)",
        "Result_Value": "Result Value"
    }

    # Apply header mapping if necessary
    df.rename(columns=header_mapping, inplace=True)

    # Convert date columns
    for col in df.columns:
        if "date" in col.lower():
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Convert numeric columns
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].replace({"N/A": np.nan, "NA": np.nan, "<0.3": np.nan})
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Handle missing values (fill with mean for numeric, mode for categorical)
    for col in df.columns:
        if df[col].dtype == "float64" or df[col].dtype == "int64":
            df[col].fillna(df[col].mean(), inplace=True)
        else:
            df[col].fillna(df[col].mode()[0], inplace=True)

    # Remove duplicates
    df.drop_duplicates(inplace=True)

    # Generate Metadata Report
    metadata = {
        "Original Headers": original_headers,
        "Mapped Headers": [header_mapping.get(h, h) for h in original_headers],
        "Column Types": df.dtypes.astype(str).tolist(),
        "Missing Values": df.isnull().sum().tolist(),
        "Unique Values": df.nunique().tolist()
    }
    metadata_df = pd.DataFrame(metadata, index=df.columns)

    # Save cleaned data & metadata to Excel
    output_file = os.path.join(OUTPUT_FOLDER, "cleaned_data.xlsx")
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Cleaned Data", index=False)
        metadata_df.to_excel(writer, sheet_name="Metadata Report")

    return output_file  # Return the path of cleaned file

# Flask Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return "No file part"

    file = request.files["file"]
    if file.filename == "":
        return "No selected file"

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        # Process file
        cleaned_file = clean_data(file_path)

        return f"File uploaded and cleaned successfully! <a href='/download'>Download cleaned file</a>"

    return "Invalid file format"

@app.route("/download")
def download_file():
    file_path = os.path.join(OUTPUT_FOLDER, "cleaned_data.xlsx")
    return send_file(file_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
