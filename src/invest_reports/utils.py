import base64
import math
import os
from io import BytesIO

import geometamaker
import numpy
import pygeoprocessing
import matplotlib
import matplotlib.pyplot as plt
import pandas
import yaml
from osgeo import gdal


MATPLOTLIB_PARAMS = {
    'legend.fontsize': 'small',
    'axes.titlesize': 'small',
    'xtick.labelsize': 'small',
    'ytick.labelsize': 'small'
    }
plt.rcParams.update(MATPLOTLIB_PARAMS)

# We set report container max width to 80rem.
# img is set to width:100%, but it's best if figures are sized to
# fill the container with minimal rescaling, as they contain rasterized text.
# Other variables:
#   root font size (default 16px)
#   savefig with tight bbox layout shrinks the figure after it is sized
FIGURE_WIDTH = 14.5  # inches; by trial & error


class RasterPlotConfig:
    def __init__(self,
                 raster_path: str,
                 datatype: str,
                 transform: str | None = None):
        self.raster_path = raster_path
        self.datatype = datatype
        self.transform = transform if not None else 'linear'


def read_masked_array(filepath, resample_method):
    info = pygeoprocessing.get_raster_info(filepath)
    nodata = info['nodata'][0]
    resampled = False
    if os.path.getsize(filepath) > 4e6:
        resampled = True
        raster = gdal.OpenEx(filepath)
        band = raster.GetRasterBand(1)
        if band.GetOverviewCount() == 0:
            pygeoprocessing.build_overviews(
                filepath,
                internal=False,
                resample_method=resample_method,
                overwrite=False, levels='auto')

        raster = gdal.OpenEx(filepath)
        band = raster.GetRasterBand(1)
        n = band.GetOverviewCount()
        array = band.GetOverview(n - 1).ReadAsArray()
        raster = band = None
    else:
        array = pygeoprocessing.raster_to_numpy_array(filepath)
    masked_array = numpy.where(array == nodata, numpy.nan, array)
    return (masked_array, resampled)


# Mapping 'datatype' to colormaps and resampling algorithms
COLORMAPS = {
    'continuous': 'viridis',
    'divergent': 'BrBG',
    'nominal': 'Set3',
    'binary': 'binary',
}
RESAMPLE_ALGS = {
    'continuous': 'bilinear',
    'divergent': 'bilinear',
    'nominal': 'nearest',
    'binary': 'nearest',
}


def _choose_n_rows_n_cols(map_bbox, n_plots):
    xy_ratio = (map_bbox[2] - map_bbox[0]) / (map_bbox[3] - map_bbox[1])
    if xy_ratio <= 1:
        n_cols = 3
    elif xy_ratio > 4:
        n_cols = 1
    elif xy_ratio > 1:
        n_cols = 2

    if n_cols > n_plots:
        n_cols = n_plots
    n_rows = int(math.ceil(n_plots / n_cols))
    return n_rows, n_cols, xy_ratio


def _figure_subplots(map_bbox, n_plots):
    n_rows, n_cols, xy_ratio = _choose_n_rows_n_cols(map_bbox, n_plots)

    sub_width = FIGURE_WIDTH / n_cols
    sub_height = (sub_width / xy_ratio) + 0.5  # in; expand vertically for title
    return plt.subplots(
        n_rows, n_cols, figsize=(FIGURE_WIDTH, n_rows*sub_height))


def plot_choropleth(gdf, field_list):
    n_plots = len(field_list)
    fig, axes = _figure_subplots(gdf.total_bounds, n_plots)
    for ax, field in zip(axes.flatten(), field_list):
        gdf.plot(ax=ax, column=field, cmap="Greens", edgecolor='lightgray')
        ax.set(title=f"{field}")
    [ax.set_axis_off() for ax in axes.flatten()]
    return fig


def plot_raster_list(tif_list, datatype_list, transform_list=None):
    """Plot a list of rasters.

    Args:
        tif_list (list): list of filepaths to rasters
        datatype_list (list): list of strings describing the data
            of each raster. One of,
            ('continuous', 'divergent', 'nominal', 'binary').
        transform_list (list): list of strings describing the
            transformation to apply to the colormap.
            Either 'linear' or 'log'.

    """
    raster_info = pygeoprocessing.get_raster_info(tif_list[0])
    bbox = raster_info['bounding_box']
    n_plots = len(tif_list)

    fig, axes = _figure_subplots(bbox, n_plots)

    if transform_list is None:
        transform_list = ['linear'] * n_plots
    for ax, tif, dtype, transform in zip(
            axes.flatten(), tif_list, datatype_list, transform_list):
        cmap = COLORMAPS[dtype]
        if dtype == 'divergent':
            if transform == 'log':
                transform = matplotlib.colors.SymLogNorm(linthresh=0.03)
            else:
                transform = matplotlib.colors.CenteredNorm()
        arr, resampled = read_masked_array(tif, RESAMPLE_ALGS[dtype])
        mappable = ax.imshow(arr, cmap=cmap, norm=transform)
        ax.set(title=f"{os.path.basename(tif)}{'*' if resampled else ''}")
        fig.colorbar(mappable, ax=ax)
    [ax.set_axis_off() for ax in axes.flatten()]
    # fig.tight_layout()
    return fig


def base64_encode(figure):
    """Encode a Matplotlib-generated figure as a base64 string.

    Args:
        figure (matplotlib.Figure): the figure to encode.

    Returns:
        A string representing the figure as a base64-encoded PNG.
    """
    figfile = BytesIO()
    figure.savefig(figfile, format='png', bbox_inches='tight')
    figfile.seek(0)  # rewind to beginning of file
    return base64.b64encode(figfile.getvalue()).decode('utf-8')


def base64_encode_file(filepath):
    """Encode a binary file as a base64 string.

    Args:
        filepath (str): the file to encode.

    Returns:
        A string representing the file as a base64-encoded string.
    """
    with open(filepath, 'rb') as file:
        s = base64.b64encode(file.read()).decode('utf-8')
    return s


def plot_and_base64_encode_rasters(raster_list: list[RasterPlotConfig]) -> str:
    """Plot and base-64-encode a list of rasters.

    Args:
        raster_dtype_list (list[RasterPlotConfig]): a list of RasterPlotConfig
            objects, each of which contains the path to a raster, the type
            of data in the raster ('continuous', 'divergent', 'nominal', or
            'binary'), and the transformation to apply to the colormap
            ('linear' or 'log').

    Returns:
        A string representing a base64-encoded PNG in which each of the
            provided rasters is plotted as a subplot.
    """
    raster_path_list = [x.raster_path for x in raster_list]
    datatype_list = [x.datatype for x in raster_list]
    transform_list = [x.transform for x in raster_list]

    figure = plot_raster_list(
        raster_path_list,
        datatype_list,
        transform_list
    )

    return base64_encode(figure)


def plot_raster_facets(tif_list, datatype, transform=None, subtitle_list=None):
    """Plot a list of rasters that will all share a fixed colorscale.

    When all the rasters have the same shape and represent the same variable,
    it's useful to scale the colorbar to the global min/max values across
    all rasters, so that the colors are visually comparable across the maps.
    All rasters share a datatype and a transform.

    Args:
        tif_list (list): list of filepaths to rasters
        datatype (str): string describing the datatype of rasters. One of,
            ('continuous', 'divergent', 'nominal', 'binary').
        transform (str): string describing the transformation to apply
            to the colormap. Either 'linear' or 'log'.

    """
    raster_info = pygeoprocessing.get_raster_info(tif_list[0])
    bbox = raster_info['bounding_box']
    n_plots = len(tif_list)
    fig, axes = _figure_subplots(bbox, n_plots)

    cmap_str = COLORMAPS[datatype]
    if transform is None:
        transform = 'linear'
    arr, resampled = read_masked_array(tif_list[0], RESAMPLE_ALGS[datatype])
    ndarray = numpy.empty((n_plots, *arr.shape))
    ndarray[0] = arr
    for i, tif in enumerate(tif_list):
        # We already got the first one to initialize the ndarray with correct shape
        if i == 0:
            continue
        arr, resampled = read_masked_array(tif, RESAMPLE_ALGS[datatype])
        ndarray[i] = arr
    # Perhaps this could be optimized by reading min/max from tif metadata
    # instead of storing all arrays in memory
    vmin = numpy.nanmin(ndarray)
    vmax = numpy.nanmax(ndarray)
    cmap = plt.cm.get_cmap(cmap_str)
    if datatype == 'divergent':
        if transform == 'log':
            normalizer = matplotlib.colors.SymLogNorm(linthresh=0.03, vmin=vmin, vmax=vmax)
        else:
            normalizer = matplotlib.colors.CenteredNorm(vmin=vmin, vmax=vmax)
    if transform == 'log':
        if numpy.isclose(vmin, 0.0):
            vmin = 1e-6
        normalizer = matplotlib.colors.LogNorm(vmin=vmin, vmax=vmax)
        cmap.set_under(cmap.colors[0])  # values below vmin (0s) get this color
    else:
        normalizer = plt.Normalize(vmin=vmin, vmax=vmax)
    for arr, ax, subtitle in zip(ndarray, axes.flatten(), subtitle_list):
        mappable = ax.imshow(arr, cmap=cmap, norm=normalizer)
        ax.set(
            title=f"{os.path.basename(tif)}{'*' if resampled else ''}\n{subtitle}")
        fig.colorbar(mappable, ax=ax)
    [ax.set_axis_off() for ax in axes.flatten()]
    return fig


# TODO: this will probably end up in the geometamaker API
def geometamaker_load(filepath):
    with open(filepath, 'r') as file:
        yaml_string = file.read()
        yaml_dict = yaml.safe_load(yaml_string)
        if not yaml_dict or ('metadata_version' not in yaml_dict
                             and 'geometamaker_version' not in yaml_dict):
            message = (f'{filepath} exists but is not compatible with '
                       f'geometamaker.')
            raise ValueError(message)

    return geometamaker.geometamaker.RESOURCE_MODELS[yaml_dict['type']](**yaml_dict)


STATS_LIST = ['STATISTICS_VALID_PERCENT', 'STATISTICS_MINIMUM', 'STATISTICS_MAXIMUM', 'STATISTICS_MEAN']


def raster_workspace_summary(workspace):
    raster_summary = {}
    for path, dirs, files in os.walk(workspace):
        for file in files:
            if file.endswith('.yml'):
                filepath = os.path.join(path, file)
                try:
                    resource = geometamaker_load(filepath)
                except Exception as err:
                    print(filepath)
                    raise err
                if isinstance(resource, geometamaker.models.RasterResource):
                    name = os.path.basename(resource.path)
                    band = resource.get_band_description(1)
                    raster_summary[name] = {
                        k: v for k, v in band.gdal_metadata.items()
                        if k in STATS_LIST}
                    raster_summary[name]['units'] = band.units
    return pandas.DataFrame(raster_summary).T


def raster_inputs_summary(args_dict):
    raster_summary = {}
    for k, v in args_dict.items():
        if isinstance(v, str) and os.path.isfile(v):
            resource = geometamaker.describe(v, compute_stats=True)
            if isinstance(resource, geometamaker.models.RasterResource):
                name = os.path.basename(resource.path)
                band = resource.get_band_description(1)
                raster_summary[name] = {
                    k: v for k, v in band.gdal_metadata.items()
                    if k in STATS_LIST}
                raster_summary[name]['units'] = band.units
    return pandas.DataFrame(raster_summary).T


def table_description_to_md(filepath):
    resource = geometamaker.describe(filepath)
    fields = resource._get_fields()
    md_list = []
    for field in fields:
        if field.description:
            md_list.append(
                f"""
                **{field.name}** (units: {field.units})
                {field.description}
                """)
    return mo.md(''.join(md_list))
