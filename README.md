# Invest Reports

## Reports built with Marimo
```python
from invest_reports import utils
```

sdr_report.py is a `marimo` notebook. It can be opened like this,

`marimo edit sdr_report.py -- -logfile path/to/InVEST-sdr-log-2025-07-18--14_34_11.txt`

## Reports built with Jinja
To see an example:
1. Open `jinja_report_generators/ndr_report_generator.py`.
2. Change the `logfile_path` (line 23) to a valid path to an InVEST logfile.
3. Make sure you have the following dependencies installed in a Python (virtual) environment:
    - natcap.invest
    - jinja2
    - matplotlib
4. Run the report generator, e.g. on macOS: `python3 ndr_report_generator.py`.
5. Find the resulting HTML document, `ndr[_suffix].html`, which can be found in the workspace folder (alongside the logfile you specified in step 2). Open the HTML document in any web browser.
