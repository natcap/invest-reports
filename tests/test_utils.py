import os
import shutil
import tempfile
import unittest

import matplotlib.testing.compare
from matplotlib.testing.exceptions import ImageComparisonFailure
import numpy
import pygeoprocessing
from osgeo import osr

import invest_reports.utils
from invest_reports.utils import MPL_SAVE_FIG_KWARGS


def save_figure(fig, filepath):
    fig.savefig(filepath, **MPL_SAVE_FIG_KWARGS)


def make_simple_raster(target_filepath, shape):
    projection = osr.SpatialReference()
    projection.ImportFromEPSG(3857)
    projection_wkt = projection.ExportToWkt()

    array = numpy.linspace(0, 1, num=numpy.multiply(*shape)).reshape(*shape)
    pygeoprocessing.numpy_array_to_raster(
        array, target_nodata=None, pixel_size=(1, 1), origin=(0, 0),
        projection_wkt=projection_wkt, target_path=target_filepath)


def compare_snapshots(reference, actual):
    ref, ext = os.path.splitext(reference)
    new_reference = f'{ref}_fail{ext}'
    try:
        comparison = matplotlib.testing.compare.compare_images(
            reference, actual, 1e-6)
    except OSError:
        shutil.copy(actual, reference)
        raise OSError(
            f'Reference image did not exist. '
            f'Now it does. Re-run this test and also run '
            f'`git add {reference}`')
    except ImageComparisonFailure as error:
        # Raised if the images are different sizes, for example.
        shutil.copy(actual, new_reference)
        raise AssertionError(
            str(error), f'actual image saved to {new_reference}')

    # If comparison is not None, then the images are not identical.
    if comparison is None:
        return
    shutil.copy(actual, new_reference)
    raise AssertionError(comparison, f'actual image saved to {new_reference}')


class RasterPlotLayoutTests(unittest.TestCase):
    """Unit tests for matplotlib utilities."""

    def setUp(self):
        """Override setUp function to create temp workspace directory."""
        self.workspace_dir = tempfile.mkdtemp()
        self.refs_dir = os.path.join('tests', 'refs')
        self.raster_config = invest_reports.utils.RasterPlotConfig(
            os.path.join(self.workspace_dir, 'foo.tif'),
            'continuous', 'linear')

    def tearDown(self):
        """Override tearDown function to remove temporary directory."""
        shutil.rmtree(self.workspace_dir)

    def test_plot_raster_list_square_aoi(self):
        """Test figure has 1 row and 3 columns."""
        figname = 'plot_raster_list_square_aoi.png'
        reference = os.path.join(self.refs_dir, figname)
        shape = (4, 4)
        make_simple_raster(self.raster_config.raster_path, shape)

        config_list = [self.raster_config]*3
        fig = invest_reports.utils.plot_raster_list(config_list)
        actual_png = os.path.join(self.workspace_dir, figname)
        save_figure(fig, actual_png)
        compare_snapshots(reference, actual_png)

    def test_plot_raster_list_wide_aoi(self):
        """Test figure has 2 rows and 2 columns."""
        figname = 'plot_raster_list_wide_aoi.png'
        reference = os.path.join(self.refs_dir, figname)
        shape = (2, 8)
        make_simple_raster(self.raster_config.raster_path, shape)

        config_list = [self.raster_config]*3
        fig = invest_reports.utils.plot_raster_list(config_list)
        actual_png = os.path.join(self.workspace_dir, figname)
        save_figure(fig, actual_png)
        compare_snapshots(reference, actual_png)

    def test_plot_raster_list_tall_aoi(self):
        """Test figure has 1 rows and 3 columns."""
        figname = 'plot_raster_list_tall_aoi.png'
        reference = os.path.join(self.refs_dir, figname)
        shape = (8, 2)
        make_simple_raster(self.raster_config.raster_path, shape)

        config_list = [self.raster_config]*3
        fig = invest_reports.utils.plot_raster_list(config_list)
        actual_png = os.path.join(self.workspace_dir, figname)
        save_figure(fig, actual_png)
        compare_snapshots(reference, actual_png)
