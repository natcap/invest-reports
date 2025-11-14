import unittest

from invest_reports import jinja_env


class JinjaTemplateUnitTests(unittest.TestCase):
    """Unit tests for partial templates."""

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
        template = jinja_env.from_string(template_str)
        html = template.render(model_spec_outputs=MODEL_SPEC.outputs)
        for output in MODEL_SPEC.outputs:
            self.assertIn(output.path, html)
