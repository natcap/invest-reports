import jinja2

jinja_env = jinja2.Environment(
    loader=jinja2.PackageLoader('invest_reports', 'jinja_templates'),
    autoescape=jinja2.select_autoescape(),
    undefined=jinja2.StrictUndefined
)
