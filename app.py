import os
import csv
from flask import Flask, render_template, request, flash, redirect, url_for
import pdfplumber

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "secret")

RA_CSV = os.path.join(os.getcwd(), "RA73331.csv")

def load_crew_list():
    """Загружает список CREW из RA73331.csv (первый столбец)"""
    crew = []
    if os.path.exists(RA_CSV):
        try:
            with open(RA_CSV, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) > 0 and row[0].strip():
                        crew.append(row[0].strip())
        except Exception:
            pass
    return crew

@app.route("/", methods=["GET"])
def index():
    crew_list = load_crew_list()
    return render_template("index.html", crew_list=crew_list)

@app.route("/process-pdf", methods=["POST"])
def process_pdf():
    pdf_file = request.files.get("pdf")
    captain = request.form.get("captain", "")
    crew_choice = request.form.get("crew", "")
    block_fuel_raw = request.form.get("block_fuel", "")

    if not pdf_file:
        flash("No PDF uploaded")
        return redirect(url_for("index"))

    try:
        block_fuel = int(float(block_fuel_raw))
    except Exception:
        block_fuel = 0

    # Чтение первой страницы PDF
    try:
        with pdfplumber.open(pdf_file) as pdf:
            page = pdf.pages[0]
            text = page.extract_text() or ""
            lines = [ln for ln in text.splitlines()] if text else []
    except Exception:
        flash("Failed to read PDF")
        return redirect(url_for("index"))

    if len(lines) < 12:
        flash("PDF doesn't contain enough lines")
        return redirect(url_for("index"))

    def split_line(idx):
        try:
            return lines[idx].split()
        except Exception:
            return []

    # 12 строка
    line12 = split_line(11)
    FLIGHT = line12[0] if len(line12) > 0 else ""
    REG = line12[1] if len(line12) > 1 else ""
    DATE = line12[2] if len(line12) > 2 else ""
    DESTINATION = line12[3][-4:] if len(line12) > 3 else ""

    # TAXI и TRIP FUEL
    line_taxi = []
    line_trip = []
    for ln in lines:
        parts = ln.split()
        if not parts:
            continue
        if len(parts) > 0 and parts[0].upper() == "TAXI" and not line_taxi:
            line_taxi = parts
        if len(parts) > 1 and parts[0].upper() == "TRIP" and parts[1].upper() == "FUEL" and not line_trip:
            line_trip = parts
        if line_taxi and line_trip:
            break

    TAXI_FUEL = line_taxi[2] if len(line_taxi) > 2 else "0"
    DOW = line_taxi[5] if len(line_taxi) > 5 else ""
    EET = line_trip[1] if len(line_trip) > 1 else ""
    TRIP_FUEL = line_trip[3] if len(line_trip) > 3 else "0"  # индекс 4

    def to_int_safe(x):
        try:
            return int(float(x))
        except Exception:
            return 0

    TAXI_FUEL_INT = to_int_safe(TAXI_FUEL)
    TRIP_FUEL_INT = to_int_safe(TRIP_FUEL)
    BLOCK_FUEL_INT = block_fuel
    TAKE_OFF_FUEL = BLOCK_FUEL_INT - TAXI_FUEL_INT

    DOI = ""
    csv_by_reg = os.path.join(os.getcwd(), f"{REG}.csv")
    if os.path.exists(csv_by_reg) and crew_choice:
        try:
            with open(csv_by_reg, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) > 0 and row[0].strip() == crew_choice:
                        DOI = row[5] if len(row) > 5 else ""
                        break
        except Exception:
            DOI = ""

    ordered = [
        ("FLIGHT", FLIGHT),
        ("A/C", "B - 772"),
        ("REG", REG),
        ("CAPTAIN", captain),
        ("CREW", crew_choice),
        ("DOW", DOW),
        ("DOI", DOI),
        ("DESTINATION", DESTINATION),
        ("BLOCK FUEL", BLOCK_FUEL_INT),
        ("TAXI FUEL", TAXI_FUEL_INT),
        ("TAKE OFF FUEL", TAKE_OFF_FUEL),
        ("TRIP FUEL", TRIP_FUEL_INT),
        ("EET", EET),
        ("SEATS QUANTITY", 412),
        ("DATE", DATE),
    ]

    return render_template("result.html", ordered=ordered)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
