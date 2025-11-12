import unittest

from jinja2 import Environment, PackageLoader, select_autoescape


class JinjaTemplateUnitTests(unittest.TestCase):
    """Unit tests for partial templates."""

    env = Environment(
        loader=PackageLoader('invest_reports', 'jinja_templates'),
        autoescape=select_autoescape())

    def test_list_metadata(self):
        """Test list_metadata macro."""
        from natcap.invest.coastal_vulnerability import MODEL_SPEC

        template_str = \
            """
            <html>
                {% from 'metadata.html' import list_metadata %}
                <div>{{ list_metadata(model_spec_outputs) }}</div>
            </html>
            """
        template = self.env.from_string(template_str)
        html = template.render(model_spec_outputs=MODEL_SPEC.outputs)
        for output in MODEL_SPEC.outputs:
            self.assertIn(output.path, html)
