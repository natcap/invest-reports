import os
import time

import geopandas
from jinja2 import Environment, PackageLoader, select_autoescape

from natcap.invest import datastack
from natcap.invest.ndr.ndr import MODEL_SPEC

import invest_reports.utils
from invest_reports.utils import RasterPlotConfig


# Locate report template.
env = Environment(
    loader=PackageLoader('invest_reports', 'jinja_templates'),
    autoescape=select_autoescape()
)
template = env.get_template('sdr-ndr-report.html')

# Define basic info.
model_spec = MODEL_SPEC
model_id = model_spec.model_id
timestamp = time.strftime('%Y-%m-%d %H:%M')
# logfile_path = '/Users/eadavis/invest-workspaces/ndr/InVEST-ndr-log-2025-10-28--13_56_40.txt'
logfile_path = '/Users/eadavis/invest-workspaces/ndr-luzon/InVEST-ndr-log-2025-10-29--14_12_04.txt'

# Get args dict, workspace path, and suffix string.
_, ds_info = datastack.get_datastack_info(logfile_path)
args_dict = ds_info.args
workspace = args_dict['workspace_dir']
suffix_str = ''
if 'results_suffix' in args_dict and args_dict['results_suffix'] != '':
    suffix_str = ('_' + args_dict['results_suffix'])

# Plot inputs.
inputs_img_src = invest_reports.utils.plot_and_base64_encode_rasters([
    RasterPlotConfig(args_dict['dem_path'], 'continuous'),
    RasterPlotConfig(args_dict['runoff_proxy_path'], 'continuous'),
    RasterPlotConfig(args_dict['lulc_path'], 'nominal')
])

# Plot primary outputs.
output_raster_plot_configs = []
if args_dict['calc_n']:
    output_raster_plot_configs.extend([
        RasterPlotConfig(
            os.path.join(workspace, f'n_surface_export{suffix_str}.tif'),
            'continuous', 'linear'),
        RasterPlotConfig(
            os.path.join(workspace, f'n_subsurface_export{suffix_str}.tif'),
            'continuous', 'linear'),
        RasterPlotConfig(
            os.path.join(workspace, f'n_total_export{suffix_str}.tif'),
            'continuous', 'linear'),
    ])
if args_dict['calc_p']:
    output_raster_plot_configs.extend([
        RasterPlotConfig(
            os.path.join(workspace, f'p_surface_export{suffix_str}.tif'),
            'continuous', 'linear'),
    ])

outputs_img_src = invest_reports.utils.plot_and_base64_encode_rasters(
    output_raster_plot_configs)

# Plot relevant intermediate outputs.
intermediate_raster_list = [
    RasterPlotConfig(os.path.join(
        workspace, 'intermediate_outputs',
        f'masked_dem{suffix_str}.tif'), 'continuous'),
    RasterPlotConfig(os.path.join(
        workspace, 'intermediate_outputs',
        f'what_drains_to_stream{suffix_str}.tif'), 'binary'),
]

# Include stream map only if not computed using D8 (D8 streams are single-pixel wide and illegible at this scale).
if args_dict['flow_dir_algorithm'] != 'D8':
    intermediate_raster_list.append(RasterPlotConfig(
        os.path.join(workspace, f'stream{suffix_str}.tif'), 'binary'))

stream_network_img_src = invest_reports.utils.plot_and_base64_encode_rasters(
    intermediate_raster_list)

# Generate HTML representation of attribute table from watershed results vector.
watershed_results_vector_path = os.path.join(
    workspace, f'watershed_results_ndr{suffix_str}.gpkg')
ws_vector = geopandas.read_file(watershed_results_vector_path)
ws_vector_table = ws_vector.drop(columns=['geometry']).to_html(
    index=False, na_rep='')

# Generate tables of raster summary stats
output_raster_stats_table = invest_reports.utils.raster_workspace_summary(
    workspace).to_html(na_rep='')
input_raster_stats_table = invest_reports.utils.raster_inputs_summary(
    args_dict).to_html(na_rep='')

# Generate HTML document.
with open(os.path.join(workspace, f'{model_id}{suffix_str}.html'),
          'w', encoding='utf-8') as target_file:
    target_file.write(template.render(
        model_id=model_id,
        model_name=model_spec.model_title,
        userguide_page=model_spec.userguide,
        timestamp=timestamp,
        args_dict=args_dict,
        inputs_img_src=inputs_img_src,
        outputs_img_src=outputs_img_src,
        intermediate_outputs_heading='Stream Network Maps',
        intermediate_outputs_img_src=stream_network_img_src,
        ws_vector_table=ws_vector_table,
        output_raster_stats_table=output_raster_stats_table,
        input_raster_stats_table=input_raster_stats_table,
        model_spec_outputs=model_spec.outputs,
        accordions_open_on_load=True,
    ))
