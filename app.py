from flask import Flask, request, send_file, jsonify, render_template_string
import pdfplumber
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
import tempfile
import os
import csv

app = Flask(__name__)

# главная страница
@app.route("/", methods=["GET"])
def index():
    crew_options = []
    ra_csv = os.path.join(os.getcwd(), "RA73331.csv")
    if os.path.exists(ra_csv):
        with open(ra_csv, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) > 0:
                    crew_options.append(row[0])

    html = """
    <h1>PDF Upload</h1>
    <form action="/process-pdf" method="post" enctype="multipart/form-data">
        <label>Загрузите файл (PDF):</label><br>
        <input type="file" name="file" required><br><br>

        <label>CAPTAIN:</label><br>
        <input type="text" name="captain" required><br><br>

        <label>CREW:</label><br>
        <select name="crew_choice" required>
            {% for option in crew_options %}
                <option value="{{ option }}">{{ option }}</option>
            {% endfor %}
        </select><br><br>

        <label>BLOCK FUEL:</label><br>
        <input type="number" name="block_fuel" required><br><br>

        <input type="submit" value="Загрузить и обработать">
    </form>
    """
    return render_template_string(html, crew_options=crew_options)


@app.route("/process-pdf", methods=["POST"])
def process_pdf():
    if "file" not in request.files:
        return jsonify({"error": "Файл не загружен"}), 400

    file = request.files["file"]
    crew_choice = request.form.get("crew_choice", "")
    captain = request.form.get("captain", "")
    block_fuel = request.form.get("block_fuel", "0")

    try:
        block_fuel_val = int(float(block_fuel))
    except ValueError:
        block_fuel_val = 0

    # временный файл для исходного pdf
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    # извлекаем строки из pdf
    lines = []
    with pdfplumber.open(tmp_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines.extend(text.splitlines())

    if len(lines) < 24:
        os.remove(tmp_path)
        return jsonify({"error": "В PDF меньше 24 строк"}), 400

    # строка 12
    line12 = lines[11].split()
    FLIGHT = line12[0] if len(line12) > 0 else ""
    REG = line12[1] if len(line12) > 1 else ""
    DATE = line12[2] if len(line12) > 2 else ""

    # строка 23
    line23 = lines[22].split()
    try:
        TAXI_FUEL = int(float(line23[2])) if len(line23) > 2 else 0
    except ValueError:
        TAXI_FUEL = 0
    DOW = line23[5] if len(line23) > 5 else ""

    # строка 24
    line24 = lines[23].split()
    try:
        TRIP_FUEL = int(float(line24[3])) if len(line24) > 3 else 0  # индекс 3
    except ValueError:
        TRIP_FUEL = 0

    EET = line24[2] if len(line24) > 2 else ""  # индекс 2

    SEATS_QUANTITY = "412"

    # --- ищем DOI по CREW в CSV ---
    CREW = crew_choice
    DOI = ""
    csv_path = os.path.join(os.getcwd(), f"{REG}.csv")
    if os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) > 0 and row[0] == CREW:
                    DOI = row[5] if len(row) > 5 else ""
                    break

    # --- TAKE OF FUEL ---
    TAKE_OF_FUEL = block_fuel_val - TAXI_FUEL

    # --- итоговые данные ---
    ordered_data = [
        ("FLIGHT", FLIGHT),
        ("A/C", "B - 772"),
        ("REG", REG),
        ("CAPTAIN", captain),
        ("CREW", CREW),
        ("DOW", DOW),
        ("DOI", DOI),
        ("BLOCK FUEL", block_fuel_val),
        ("TAXI FUEL", TAXI_FUEL),
        ("TAKE OF FUEL", TAKE_OF_FUEL),
        ("TRIP FUEL", TRIP_FUEL),
        ("EET", EET),
        ("SEATS QUANTITY", SEATS_QUANTITY),
        ("DATE", DATE),
    ]

    # создаем новый PDF
    output_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    doc = SimpleDocTemplate(output_pdf.name, pagesize=A4)

    data = [[k, v] for k, v in ordered_data]  # без шапки Key/Value

    table = Table(data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))

    doc.build([table])

    os.remove(tmp_path)

    return send_file(output_pdf.name, as_attachment=True, download_name="result.pdf")


if __name__ == "__main__":
    app.run(debug=True)
