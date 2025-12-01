# Dictionary lookups and utils shared by SDR and NDR
# (to be extended to support other similar models, and renamed as appropriate)

import geopandas

from invest_reports.utils import RasterPlotConfig

INPUT_RASTER_PLOT_TUPLES = {
  'ndr': [
      ('dem_path', 'continuous'),
      ('runoff_proxy_path', 'continuous'),
      ('lulc_path', 'nominal')
  ],
  'sdr': [
    ('dem_path', 'continuous'),
    ('erodibility_path', 'continuous'),
    ('erosivity_path', 'continuous'),
    ('lulc_path', 'nominal'),
  ],
}

OUTPUT_RASTER_PLOT_TUPLES = {
    'ndr': {
        'calc_n': [
            ('n_surface_export', 'continuous', 'linear'),
            ('n_subsurface_export', 'continuous', 'linear'),
            ('n_total_export', 'continuous', 'linear'),
        ],
        'calc_p': [
            ('p_surface_export', 'continuous', 'linear')
        ],
    },
    'sdr': [
        ('avoided_erosion', 'continuous', 'linear'),
        ('avoided_export', 'continuous', 'log'),
        ('sed_deposition', 'continuous', 'log'),
        ('sed_export', 'continuous', 'log'),
        ('rkls', 'continuous', 'linear'),
        ('usle', 'continuous', 'log'),
    ],
}

INTERMEDIATE_OUTPUT_RASTER_PLOT_TUPLES = {
    'ndr': [
        ('masked_dem', 'continuous'),
        ('what_drains_to_stream', 'binary'),
    ],
    'sdr': [
        ('pit_filled_dem', 'continuous'),
        ('what_drains_to_stream', 'binary'),
    ],
}


def get_input_raster_plot_configs(model_id, args_dict):
    raster_plot_tuples = INPUT_RASTER_PLOT_TUPLES[model_id]
    return [RasterPlotConfig(args_dict[input_id], datatype)
            for (input_id, datatype) in raster_plot_tuples]


def get_output_raster_plot_configs(model_id, args_dict, file_registry):
    raster_plot_tuples = []
    if model_id == 'ndr':
        if args_dict['calc_n']:
            raster_plot_tuples.extend(
                OUTPUT_RASTER_PLOT_TUPLES[model_id]['calc_n'])
        if args_dict['calc_p']:
            raster_plot_tuples.extend(
                OUTPUT_RASTER_PLOT_TUPLES[model_id]['calc_p'])
    else:
        raster_plot_tuples = OUTPUT_RASTER_PLOT_TUPLES[model_id]
    return [RasterPlotConfig(file_registry[output_id], datatype, transform)
            for (output_id, datatype, transform) in raster_plot_tuples]


def get_intermediate_output_raster_plot_configs(
        model_id, args_dict, file_registry):
    raster_plot_tuples = INTERMEDIATE_OUTPUT_RASTER_PLOT_TUPLES[model_id]
    if args_dict['flow_dir_algorithm'] != 'D8':
        raster_plot_tuples.append(('stream', 'binary'))
    return [RasterPlotConfig(file_registry[output_id], datatype)
            for (output_id, datatype) in raster_plot_tuples]


def generate_watershed_results_table(model_id, file_registry):
    ws_vector_id = f'watershed_results_{model_id}'
    ws_vector = geopandas.read_file(file_registry[ws_vector_id])
    ws_vector_table = ws_vector.drop(columns=['geometry']).to_html(
        index=False, na_rep='')
    return ws_vector_table
