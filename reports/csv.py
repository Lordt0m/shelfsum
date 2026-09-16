import csv

from django.http import HttpResponse


def safe_csv_text(value):
    value = str(value)
    return f"'{value}" if value[:1] in {"=", "+", "-", "@"} else value


def csv_response(*, headings, filename, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headings)
    for row in rows:
        writer.writerow(row)
    return response
