import base64
import collections
import logging
import math
import os
from io import BytesIO

import geometamaker
import numpy
import pygeoprocessing
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import pandas
import yaml
from osgeo import gdal


LOGGER = logging.getLogger(__name__)

# MATPLOTLIB_PARAMS = {
#     'legend.fontsize': 'small',
#     'axes.titlesize': 'small',
#     'xtick.labelsize': 'small',
#     'ytick.labelsize': 'small'
#     }
# plt.rcParams.update(MATPLOTLIB_PARAMS)

# We set report container max width to 80rem.
# img is set to width:100%, but it's best if figures are sized to
# fill the container with minimal rescaling, as they contain rasterized text.
# Other variables:
#   root font size (default 16px)
#   savefig with tight bbox layout shrinks the figure after it is sized
FIGURE_WIDTH = 14.5  # inches; by trial & error

# Globally set the float format used in DataFrames and resulting HTML tables.
# G indicates Python "general" format, which limits precision
# (default: 6 significant digits), drops trailing zeros,
# and uses scientific notation where appropriate.
pandas.set_option('display.float_format', '{:G}'.format)


class RasterPlotConfig:
    def __init__(self,
                 raster_path: str,
                 datatype: str,
                 transform: str | None = None):
        self.raster_path = raster_path
        self.datatype = datatype
        self.transform = transform if not None else 'linear'


class RasterPlotConfigGroup:
    def __init__(self,
                 inputs: list[RasterPlotConfig],
                 outputs: list[RasterPlotConfig],
                 intermediates: list[RasterPlotConfig]):
        self.inputs = inputs
        self.outputs = outputs
        self.intermediates = intermediates


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
    'nominal': 'tab20',
    # Use `binary` where `1` pixels are likely to be adjacent to white
    # background and/or `0` pixels, as in what_drains_to_stream maps, e.g.
    # This `1` color has good (but not especially high) contrast against both
    # black (the `0` color) and white (the figure background).
    'binary': ListedColormap(["#000000", "#aa44dd"]),
    # Use `binary_high_contrast` where `1` pixels are likely to be adjacent
    # to `0` pixels and other `1` pixels but _not_ to white background,
    # as in stream network maps, e.g.
    # The `1` color has very high contrast against the `0` color but
    # very low contrast against white (the figure background).
    'binary_high_contrast': ListedColormap(["#1a1a1a", "#4de4ff"]),
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
    sub_height = (sub_width / xy_ratio) + 1.0  # in; expand vertically for title & subtitle
    return plt.subplots(
        n_rows, n_cols, figsize=(FIGURE_WIDTH, n_rows*sub_height),
        layout='constrained')


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

    Returns:
        ``matplotlib.figure.Figure``
    """
    raster_info = pygeoprocessing.get_raster_info(tif_list[0])
    bbox = raster_info['bounding_box']
    n_plots = len(tif_list)

    fig, axes = _figure_subplots(bbox, n_plots)

    if transform_list is None:
        transform_list = ['linear'] * n_plots
    for ax, tif, dtype, transform in zip(
            axes.flatten(), tif_list, datatype_list, transform_list):
        resample_alg = (RESAMPLE_ALGS['binary']
                        if dtype.startswith('binary')
                        else RESAMPLE_ALGS[dtype])
        arr, resampled = read_masked_array(tif, resample_alg)
        legend = False
        imshow_kwargs = {}
        colorbar_kwargs = {}
        imshow_kwargs['norm'] = transform
        imshow_kwargs['interpolation'] = 'none'
        cmap = COLORMAPS[dtype]
        if dtype == 'divergent':
            if transform == 'log':
                transform = matplotlib.colors.SymLogNorm(linthresh=0.03)
            else:
                transform = matplotlib.colors.CenteredNorm()
            imshow_kwargs['norm'] = transform
        if dtype.startswith('binary'):
            transform = matplotlib.colors.BoundaryNorm([0, 0.5, 1], cmap.N)
            # @TODO: ¿update imshow_kwargs['norm']?
            imshow_kwargs['vmin'] = -0.5
            imshow_kwargs['vmax'] = 1.5
            colorbar_kwargs['ticks'] = [0, 1]
        mappable = ax.imshow(arr, cmap=cmap, **imshow_kwargs)
        if dtype == 'nominal':
            # typically a 'nominal' raster would be an int type, but we replaced
            # nodata with nan, so the array is now a float.
            values, counts = numpy.unique(arr[~numpy.isnan(arr)], return_counts=True)
            values = values[numpy.argsort(-counts)].astype(int)  # descending order
            colors = [mappable.cmap(mappable.norm(value)) for value in values]
            patches = [matplotlib.patches.Patch(
                color=colors[i], label=f'{values[i]}') for i in range(len(values))]
            legend = True
        ax.set_title(
            label=f"{os.path.basename(tif)}{' (resampled)' if resampled else ''}",
            loc='left', y=1.12, pad=0,
            fontfamily='monospace', fontsize=14, fontweight=700)
        units = _get_raster_units(tif)
        if units:
            ax.text(x=0.0, y=1.0, s=f'Units: {units}', fontsize=12)
        if legend:
            leg = ax.legend(handles=patches, bbox_to_anchor=(1.02, 1), loc=2)
            leg.set_in_layout(False)
        else:
            fig.colorbar(mappable, ax=ax, **colorbar_kwargs)
    [ax.set_axis_off() for ax in axes.flatten()]
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
    resample_alg = (RESAMPLE_ALGS['binary']
                    if datatype.startswith('binary')
                    else RESAMPLE_ALGS[datatype])
    arr, resampled = read_masked_array(tif_list[0], resample_alg)
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


STATS_LIST = [
    ('STATISTICS_MINIMUM', 'Minimum'),
    ('STATISTICS_MAXIMUM', 'Maximum'),
    ('STATISTICS_MEAN', 'Mean'),
    ('STATISTICS_VALID_PERCENT', 'Valid percent'),
]


def _build_stats_table_row(resource, band):
    row = {}
    for (stat_key, display_name) in STATS_LIST:
        stat_val = band.gdal_metadata.get(stat_key)
        if stat_val is not None:
            row[display_name] = float(stat_val)
        else:
            row[display_name] = 'unknown'
    (width, height) = (
        resource.data_model.raster_size['width'],
        resource.data_model.raster_size['height'])
    row['Count'] = width * height
    row['Nodata value'] = band.nodata
    # band.units may be '', which can mean 'unitless', 'unknown', or 'other'
    # @TODO: standardize string representations to help distinguish between
    # 'unitless', 'other/multiple/it depends', and truly 'unknown'
    row['Units'] = band.units
    return row


def _get_raster_metadata(filepath):
    if isinstance(filepath, collections.abc.Mapping):
        for path in filepath.values():
            _get_raster_metadata(path)
    else:
        try:
            resource = geometamaker_load(f'{filepath}.yml')
        except (FileNotFoundError, ValueError) as err:
            LOGGER.debug(err)
            return None
        if isinstance(resource, geometamaker.models.RasterResource):
            return resource


def _get_raster_units(filepath):
    resource = _get_raster_metadata(filepath)
    return resource.get_band_description(1).units if resource else None


# @TODO tests for this function could use the same setup
# as invest's test_spec.py:TestMetadataFromSpec.
# @TODO This function's recursion through a file registry is duplicated in
# invest's metadata-generating function. We may want a FileRegistry.walk method,
# or similar.
def raster_workspace_summary(file_registry):
    raster_summary = {}

    for path in file_registry.values():
        resource = _get_raster_metadata(path)
        band = resource.get_band_description(1) if resource else None
        if band:
            filename = os.path.basename(path)
            raster_summary[filename] = _build_stats_table_row(
                resource, band)

    return pandas.DataFrame(raster_summary).T


def raster_inputs_summary(args_dict):
    raster_summary = {}
    for v in args_dict.values():
        if isinstance(v, str) and os.path.isfile(v):
            resource = geometamaker.describe(v, compute_stats=True)
            if isinstance(resource, geometamaker.models.RasterResource):
                filename = os.path.basename(resource.path)
                band = resource.get_band_description(1)
                raster_summary[filename] = _build_stats_table_row(
                    resource, band)
                # Remove 'Units' column if all units are blank
                if not any(raster_summary[filename]['Units']):
                    del raster_summary[filename]['Units']

    return pandas.DataFrame(raster_summary).T
