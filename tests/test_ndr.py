import unittest
import lxml.html

from natcap.invest.ndr.ndr import MODEL_SPEC
from invest_reports import jinja_env

TEMPLATE = jinja_env.get_template('sdr-ndr-report.html')


class SDRReportTests(unittest.TestCase):
    """Unit tests for NDR report."""

    def test_render(self):
        """Basic test to make sure the template renders without error."""

        html = TEMPLATE.render(
            report_script=__file__,
            model_id=MODEL_SPEC.model_id,
            model_name=MODEL_SPEC.model_title,
            userguide_page=MODEL_SPEC.userguide,
            timestamp='',
            args_dict={},
            inputs_img_src='',
            outputs_img_src='',
            intermediate_outputs_heading='Stream Network Maps',
            intermediate_outputs_img_src='',
            ws_vector_table='',
            ws_vector_totals_table='',
            output_raster_stats_table='',
            input_raster_stats_table='',
            stats_table_note='',
            model_spec_outputs=MODEL_SPEC.outputs,
            accordions_open_on_load=True,
        )

        root = lxml.html.document_fromstring(html)

        sections = root.findall('.//section')
        self.assertEqual(len(sections), 8)

        h1 = root.find('.//h1')
        self.assertEqual(h1.text, f'InVEST Results: {MODEL_SPEC.model_title}')
