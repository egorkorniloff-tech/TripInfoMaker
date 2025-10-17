import os
import csv
from io import BytesIO
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
import pdfplumber
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "secret")

# Путь к CSV с именами CREW для выпадающего списка
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

    # Читаем первую страницу PDF
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

    # Функция для безопасного сплита строки
    def split_line(idx):
        try:
            return lines[idx].split()
        except Exception:
            return []

    # Извлекаем 12 строку
    line12 = split_line(11)
    FLIGHT = line12[0] if len(line12) > 0 else ""
    REG = line12[1] if len(line12) > 1 else ""
    DATE = line12[2] if len(line12) > 2 else ""
    DESTINATION = line12[3][-4:] if len(line12) > 3 else ""

    # --- Логика для TAXI и TRIP FUEL (поиск по содержимому строк) ---
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

    # Если не найдено, присваиваем дефолты
    TAXI_FUEL = line_taxi[2] if len(line_taxi) > 2 else "0"
    DOW = line_taxi[5] if len(line_taxi) > 5 else ""

    # <-- изменено: TRIP_FUEL теперь берётся из индекса 4 -->
    EET = line_trip[1] if len(line_trip) > 1 else ""
    TRIP_FUEL = line_trip[3] if len(line_trip) > 3 else "0"

    def to_int_safe(x):
        try:
            return int(float(x))
        except Exception:
            return 0

    TAXI_FUEL_INT = to_int_safe(TAXI_FUEL)
    TRIP_FUEL_INT = to_int_safe(TRIP_FUEL)
    BLOCK_FUEL_INT = block_fuel
    TAKE_OF_FUEL = BLOCK_FUEL_INT - TAXI_FUEL_INT

    # --- Ищем DOI в CSV с именем REG ---
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

    # --- Формируем PDF ---
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
        ("TAKE OF FUEL", TAKE_OF_FUEL),
        ("TRIP FUEL", TRIP_FUEL_INT),
        ("EET", EET),
        ("SEATS QUANTITY", 412),
        ("DATE", DATE),
    ]

    pdf_out = FPDF()
    pdf_out.set_auto_page_break(auto=True, margin=15)
    pdf_out.add_page()
    pdf_out.set_font("helvetica", size=12)

    pdf_out.cell(0, 10, "Flight data", ln=True, align="C")
    pdf_out.ln(4)

    col1_w = 60
    for key, val in ordered:
        pdf_out.set_font("helvetica", size=11)
        pdf_out.cell(col1_w, 9, f"{key}", border=1)
        pdf_out.cell(0, 9, str(val), border=1, ln=True)

    # Генерация PDF в память
    pdf_bytes = pdf_out.output(dest="S").encode("latin1")
    output = BytesIO(pdf_bytes)
    output.seek(0)

    return send_file(output, as_attachment=True, download_name="result.pdf", mimetype="application/pdf")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
