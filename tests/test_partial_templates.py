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

    def test_caption_with_text_string_and_list(self):
        """Test caption macro with string and list."""

        template_str = \
            """
            <html>
                {% from 'caption.html' import caption %}
                <div>{{ caption(text, source_list) }}</div>
            </html>
            """
        text = 'description'
        source_list = ['/foo/bar']
        template = jinja_env.from_string(template_str)
        html = template.render(
            text=text,
            source_list=source_list)
        self.assertIn(text, html)
        for source in source_list:
            self.assertIn(source, html)

    def test_caption_with_text_list(self):
        """Test caption macro with list of text."""

        template_str = \
            """
            <html>
                {% from 'caption.html' import caption %}
                <div>{{ caption(text) }}</div>
            </html>
            """
        text_list = ['description', 'paragraph']
        template = jinja_env.from_string(template_str)
        html = template.render(text=text_list)
        for text in text_list:
            self.assertIn(text, html)
        self.assertNotIn('Sources', html)
