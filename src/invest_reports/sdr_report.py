# /// script
# dependencies = [
#   geopandas,
#   matplotlib
# ]
# ///

import marimo

__generated_with = "0.14.11"
app = marimo.App(width="medium", app_title="SDR explore")


@app.cell
def _():
    import os

    import geopandas
    import marimo as mo
    from natcap.invest import datastack
    import natcap.invest.utils

    from invest_reports import utils
    return datastack, geopandas, mo, natcap, os, utils


@app.cell
def _(datastack, mo):
    logfile_path = mo.cli_args().get('logfile')
    # logfile_path = 'C:/Users/dmf/projects/forum/sdr_ndr_swy_luzon/sdr_example/InVEST-sdr-log-2025-07-21--14_04_29.txt'
    # logfile_path = 'C:/Users/dmf/projects/forum/sdr/sample_report3/InVEST-sdr-log-2025-07-18--14_34_11.txt'
    _, ds_info = datastack.get_datastack_info(logfile_path)
    args_dict = ds_info.args
    mo.accordion({'SDR model arguments': args_dict})
    return (args_dict,)


@app.cell
def _(args_dict, natcap):
    workspace = args_dict['workspace_dir']
    suffix_str = natcap.invest.utils.make_suffix_string(args_dict, 'results_suffix')
    return suffix_str, workspace


@app.cell
def _(geopandas, os, suffix_str, workspace):
    watershed_results_vector_path = os.path.join(workspace, f'watershed_results_sdr{suffix_str}.shp')
    ws_vector = geopandas.read_file(watershed_results_vector_path)
    return watershed_results_vector_path, ws_vector


@app.cell
def _(ws_vector):
    ws_vector.explore()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""## Results by Watershed""")
    return


@app.cell
def _(mo, ws_vector):
    _table = ws_vector.drop(columns=['geometry'])
    mo.ui.table(_table)
    return


@app.cell
def _(utils, watershed_results_vector_path):
    utils.table_description_to_md(watershed_results_vector_path)
    return


@app.cell
def _(mo, utils, ws_vector):
    # No reason for choropleth when there is only one feature
    if len(ws_vector) > 1:
        _fields = ["usle_tot", "sed_export", "sed_dep", "avoid_exp", "avoid_eros"]
        mo.output.replace(utils.plot_choropleth(ws_vector, _fields))
    return


@app.cell
def _(mo, os, suffix_str, utils, workspace):
    _raster_dtype_list = (
        (os.path.join(workspace, f'avoided_erosion{suffix_str}.tif'), 'continuous', 'linear'),
        (os.path.join(workspace, f'avoided_export{suffix_str}.tif'), 'continuous', 'log'),
        (os.path.join(workspace, f'sed_deposition{suffix_str}.tif'), 'continuous', 'log'),
        (os.path.join(workspace, f'sed_export{suffix_str}.tif'), 'continuous', 'log'),
        (os.path.join(workspace, f'rkls{suffix_str}.tif'), 'continuous', 'linear'),
        (os.path.join(workspace, f'usle{suffix_str}.tif'), 'continuous', 'log')
    )

    _tif_list, _dtype_list, _transform_list = zip(*_raster_dtype_list)

    _figure = utils.plot_raster_list(
        _tif_list,
        datatype_list=_dtype_list,
        transform_list=_transform_list,
    )

    mo.accordion({'Raster Results': _figure})
    return


@app.cell
def _(args_dict, mo, os, suffix_str, utils, workspace):
    _raster_dtype_list = [
        (os.path.join(workspace, 'intermediate_outputs', f'pit_filled_dem{suffix_str}.tif'), 'continuous'),
        (os.path.join(workspace, 'intermediate_outputs', f'what_drains_to_stream{suffix_str}.tif'), 'binary'),
    ]

    # D8 streams are single pixel wide and illegible at this scale
    if args_dict['flow_dir_algorithm'] != 'D8':
        _raster_dtype_list.append((os.path.join(workspace, f'stream{suffix_str}.tif'), 'binary'))

    _tif_list, _dtype_list, = zip(*_raster_dtype_list)

    _figure = utils.plot_raster_list(
        _tif_list,
        datatype_list=_dtype_list)
    mo.accordion({'Stream Network Maps': _figure})
    return


@app.cell
def _(args_dict, mo, utils, workspace):
    _output_raster_stats = utils.raster_workspace_summary(workspace)
    _input_raster_stats = utils.raster_inputs_summary(args_dict)
    mo.accordion({
        'Output Raster Stats': _output_raster_stats,
        'Input Raster Stats': _input_raster_stats,
    }, multiple=True)
    return


@app.cell
def _(args_dict, mo, utils):
    _raster_dtype_list = (
        (args_dict['dem_path'], 'continuous'),
        (args_dict['erodibility_path'], 'continuous'),
        (args_dict['erosivity_path'], 'continuous'),
        (args_dict['lulc_path'], 'nominal')
    )

    # This arg is optional and may not exist
    if args_dict['drainage_path']:
        _raster_dtype_list.append(args_dict['drainage_path'], 'binary')

    _tif_list, _dtype_list, = zip(*_raster_dtype_list)

    _figure = utils.plot_raster_list(
        _tif_list,
        datatype_list=_dtype_list,
    )

    mo.accordion({'Input Maps': _figure})
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
    ## *
    Raster plots with an __*__ were resampled to lower resolution for plotting. Full resolution rasters are available in the output workspace.
    """
    )
    return


if __name__ == "__main__":
    app.run()
