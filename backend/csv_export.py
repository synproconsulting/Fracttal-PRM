"""Sprint 16 / FPRM-262 - shared CSV export helper.

All list endpoints that support ``?export=csv`` call ``csv_response`` from
here. Keeps the date-stamped filename and Content-Disposition consistent
across every export.

CSV downloads MUST be issued via fetch + Blob from the frontend (never
``window.location.href``) so the Authorization header is sent (AD-18).
"""
import csv
import io
from datetime import date
from typing import Iterable, Sequence

from fastapi.responses import Response


def csv_response(filename_base: str, header: Sequence, rows: Iterable[Sequence]) -> Response:
    """Render a CSV body and return a FastAPI Response with the right headers.

    Args:
        filename_base: e.g. ``"deals_export"``. Today's ISO date and ``.csv``
            are appended automatically.
        header: list of column header strings (written as the first row).
        rows: iterable of row sequences. Each item is written as-is via
            ``csv.writer.writerow`` - so strings/numbers/None all work.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    filename = f"{filename_base}_{date.today().isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
