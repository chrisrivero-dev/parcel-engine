from flask import Flask, request, send_file, render_template_string
import tempfile
import os

from transcription.parser_v2 import parse_legal_description
from geometry.builder import build_geometry
from exporters.dxf import export_dxf

app = Flask(__name__)

HTML = """
<html>
<head>
<title>Parcel Builder</title>
</head>
<body>
<h2>Legal Description → Parcel DXF</h2>

<form method="post">
<textarea name="legal" rows="10" cols="60"></textarea><br><br>
<button type="submit">Build Parcel</button>
</form>

</body>
</html>
"""

@app.route("/", methods=["GET","POST"])
def index():

    if request.method == "POST":

        text = request.form["legal"]

        calls, _ties, errors, _ignored = parse_legal_description(text)

        if errors:
            return f"Parse Errors: {errors}"

        result = build_geometry(
            start_point=(0.0,0.0),
            calls=calls
        )

        points = result["points"]

        tmp = tempfile.NamedTemporaryFile(delete=False,suffix=".dxf")

        export_dxf(points,tmp.name)

        return send_file(tmp.name,as_attachment=True)

    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(port=5050)