from jinja2 import Environment, PackageLoader, select_autoescape
import os
import time

from natcap.invest import datastack
import natcap.invest.utils

import invest_reports.utils
from invest_reports.utils import RasterPlotConfig


# Locate report template.
env = Environment(
    loader=PackageLoader('invest_reports', 'jinja_templates'),
    autoescape=select_autoescape()
)
template = env.get_template('report.html')

# Define basic info.
model_name = 'NDR'
timestamp = time.strftime('%Y-%m-%d %H:%M')
# @TODO: get logfile path programmatically
logfile_path = '/Users/eadavis/invest-workbench/invest-workspaces/ndr/InVEST-ndr-log-2025-08-22--17_26_24.txt'

# Get args dict, workspace path, and suffix string.
_, ds_info = datastack.get_datastack_info(logfile_path)
args_dict = ds_info.args
workspace = args_dict['workspace_dir']
suffix_str = natcap.invest.utils.make_suffix_string(args_dict, 'results_suffix')

# Plot inputs.
inputs_img_src = invest_reports.utils.plot_and_base64_encode_rasters([
    RasterPlotConfig(args_dict['dem_path'], 'continuous'),
    RasterPlotConfig(args_dict['runoff_proxy_path'], 'continuous'),
    RasterPlotConfig(args_dict['lulc_path'], 'nominal')
])

# Plot primary outputs.
outputs_img_src = invest_reports.utils.plot_and_base64_encode_rasters([
    RasterPlotConfig(
        os.path.join(workspace, f'n_surface_export{suffix_str}.tif'),
        'continuous', 'linear'),
    RasterPlotConfig(
        os.path.join(workspace, f'n_subsurface_export{suffix_str}.tif'),
        'continuous', 'linear'),
    RasterPlotConfig(
        os.path.join(workspace, f'n_total_export{suffix_str}.tif'),
        'continuous', 'linear'),
    RasterPlotConfig(
        os.path.join(workspace, f'p_surface_export{suffix_str}.tif'),
        'continuous', 'linear'),
])

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

# Generate HTML document.
with open(f'../html/{model_name.lower()}.html', 'w') as target_file:
    target_file.write(template.render(
        page_title=f'InVEST Results: {model_name}',
        model_name=model_name,
        timestamp=timestamp,
        args_dict=args_dict,
        inputs_img_src=inputs_img_src,
        outputs_img_src=outputs_img_src,
        intermediate_outputs_heading='Stream Network Maps',
        intermediate_outputs_img_src=stream_network_img_src,
        accordions_open_on_load=True,
        accent_color='lemonchiffon'
    ))
