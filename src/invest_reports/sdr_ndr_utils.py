# Utils shared by SDR and NDR
# (to be extended to support other similar models, and renamed as appropriate)

import geopandas

from invest_reports.utils import RasterPlotConfig


def build_input_raster_plot_configs(args_dict, raster_plot_tuples):
    return [RasterPlotConfig(args_dict[input_id], datatype)
            for (input_id, datatype) in raster_plot_tuples]


def build_output_raster_plot_configs(file_registry, raster_plot_tuples):
    return [RasterPlotConfig(file_registry[output_id], datatype, transform)
            for (output_id, datatype, transform) in raster_plot_tuples]


def build_intermediate_output_raster_plot_configs(
        args_dict, file_registry, raster_plot_tuples):
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
