# Invest Reports

## Reports are built with Jinja
To see an example:
1. Open `jinja_report_generators/ndr_report_generator.py`.
2. Change the `logfile_path` to a valid path to an InVEST logfile.
3. Check pyproject.toml for dependencies.
4. Run the report generator, e.g. on macOS: `python3 ndr_report_generator.py`.
5. Find the resulting HTML document, `ndr[_suffix].html`, which can be found in the workspace folder (alongside the logfile you specified in step 2). Open the HTML document in any web browser.
