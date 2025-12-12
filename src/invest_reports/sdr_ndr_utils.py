# Utils shared by SDR and NDR
# (to be extended to support other similar models, and renamed as appropriate)

import geopandas
import pandas

from invest_reports.utils import RasterPlotConfig

TABLE_PAGINATION_THRESHOLD = 10


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


def generate_results_table_from_vector(filepath, cols_to_sum):
    vector_df = geopandas.read_file(filepath)
    vector_df = vector_df.drop(columns=['geometry'])

    css_classes = ['datatable']
    (num_rows, _) = vector_df.shape
    if num_rows > TABLE_PAGINATION_THRESHOLD:
        css_classes.append('paginate')

    html_table_totals = None
    if num_rows > 1:
        totals_df = pandas.DataFrame()
        totals_df.loc['Totals', cols_to_sum] = vector_df.sum(axis=0)
        html_table_totals = totals_df.to_html(
            index=True, index_names=True, na_rep='', classes='full-width')

    html_table_main = vector_df.to_html(
        index=False, na_rep='', classes=css_classes)

    return (html_table_main, html_table_totals)
