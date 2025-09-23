import marimo

__generated_with = "0.14.11"
app = marimo.App(width="full")


@app.cell
def _():
    import os

    import altair
    import geopandas
    import marimo as mo
    from natcap.invest import datastack
    import natcap.invest.utils
    import numpy
    import pandas

    from invest_reports import utils

    # altair.data_transformers.enable("vegafusion")
    altair.data_transformers.disable_max_rows()
    altair.renderers.enable("browser")
    return altair, datastack, geopandas, mo, os, pandas


@app.cell
def _(datastack, mo):
    logfile_path = mo.cli_args().get('logfile')
    logfile_path = 'C:/Users/dmf/projects/forum/cv/mar/sample_200m/InVEST-coastal_vulnerability-log-2025-09-12--11_38_58.txt'
    _, ds_info = datastack.get_datastack_info(logfile_path)
    args_dict = ds_info.args
    workspace = args_dict['workspace_dir']
    # suffix_str = natcap.invest.utils.make_suffix_string(args_dict, 'results_suffix')
    return (workspace,)


@app.cell
def _(os, pandas, workspace):
    rank_vars = ['R_hab', 'R_wind', 'R_wave', 'R_surge', 'R_relief']
    exposure_data = pandas.read_csv(os.path.join(workspace, 'coastal_exposure.csv'))
    if 'R_geomorph' in exposure_data:
        rank_vars.append('R_geomorph')
    exposure_data
    return exposure_data, rank_vars


@app.cell
def _(altair, exposure_data):
    _chart = altair.Chart(exposure_data).mark_bar().encode(
        altair.X('exposure').bin(step=0.1),
        y='count()'
    )
    _chart
    return


@app.cell
def _(altair, exposure_data, rank_vars):
    _chart = altair.Chart(exposure_data).mark_bar().encode(
        altair.X(altair.repeat('column')).bin(step=0.2),
        y='count()'
    ).properties(
        width=200,
        height=200
    ).repeat(
        column=['exposure'] + rank_vars
    )
    _chart
    return


@app.cell
def _(geopandas, os, workspace):
    exposure_geo = geopandas.read_file(os.path.join(workspace, 'coastal_exposure.gpkg'))
    landmass_geo = geopandas.read_file(os.path.join(workspace, 'intermediate/shore_points/clipped_projected_landmass.gpkg'))
    fetch_rays_geo = geopandas.read_file(os.path.join(workspace, 'intermediate/wind_wave/fetch_rays.gpkg'))
    wave_energy_geo = geopandas.read_file(os.path.join(workspace, 'intermediate/wind_wave/wave_energies.gpkg'))
    return exposure_geo, fetch_rays_geo, landmass_geo, wave_energy_geo


@app.cell
def _():
    return


@app.cell
def _():
    # landmass_geo.plot()
    return


@app.cell
def _(altair, exposure_geo, landmass_geo, rank_vars):
    slider = altair.binding_range(min=1, max=5, step=0.1)
    cutoff = altair.param(bind=slider, value=4)
    predicate = altair.datum.exposure < cutoff

    domain = [1, 2, 3, 4, 5]
    range_ = ['#9cc8e2', '#9cc8e2', 'red', '#5ba3cf', '#125ca4']

    xmin, ymin, xmax, ymax = exposure_geo.total_bounds
    # fit object should be a GeoJSON-like Feature or FeatureCollection
    extent_feature = {
        "type": "Feature",
        "geometry": {"type": "Polygon",
                     "coordinates": [[
                         [xmax, ymax],
                         [xmax, ymin],
                         [xmin, ymin],
                         [xmin, ymax],
                         [xmax, ymax]]]},
        "properties": {}
    }
    _landmass = altair.Chart(landmass_geo).mark_geoshape(
        clip=True,
        fill='lightgrey'
    ).project(
        type='identity',
        reflectY=True, # Canvas and SVG treats positive y as down
        fit=extent_feature
    ).properties(
        # width=900
        height=800
    )
    # _landmass

    _pt_size_slider = altair.binding_range(min=8, max=40, step=2, name='point size')
    _pt_size = altair.param(bind=_pt_size_slider, value=12)

    _null_checkbox = altair.binding_checkbox(name='show null')
    _param_checkbox = altair.param(bind=_null_checkbox)

    _points = altair.Chart(exposure_geo).transform_calculate(
        lon="datum.geometry.coordinates[0]",
        lat="datum.geometry.coordinates[1]"
    ).mark_circle(
        filled=False,
        strokeWidth=0.5,
        size=_pt_size,
        invalid=altair.condition(_param_checkbox,
            'show', 'filter')
    ).project(
        type='identity',
        reflectY=True # Canvas and SVG treats positive y as down
    ).encode(
        longitude='lon:Q',
        latitude='lat:Q',
        # color='exposure:Q'
        # color=altair.Color('exposure:Q').scale(scheme='plasma', reverse=True).bin(maxbins=4),
        color=altair.condition(
            'isValid(datum.exposure)',
            altair.Color('exposure:Q').scale(scheme='plasma', reverse=True).bin(maxbins=4),
            altair.value('gray'),
        ),
        # color=altair.when(predicate).then(altair.value('blue')).otherwise(altair.value('red')),
        tooltip=altair.Tooltip(
            ['exposure'] + rank_vars, format='.2f')
    ).add_params(_pt_size, _param_checkbox)# .interactive()

    # _null_points = _points.encode(
    #     color=altair.Color('exposure:O').scale(altair.Scale(range=['gray']))
    # ).transform_filter(
    #     '!isValid(datum.exposure)'
    # )

    _map = _landmass + _points
    _map

    # _histogram = altair.Chart(exposure_geo).mark_bar().encode(
    #     altair.X('exposure'), # .bin(step=0.1),
    #     y='count()',
    #     color=altair.when(predicate).then(altair.value('blue')).otherwise(altair.value('red'))
    # ).properties(
    #     width=200,
    #     # height=100
    # ).add_params(cutoff)
    # _histogram | _map
    return


@app.cell(disabled=True)
def _(altair, fetch_rays_geo, landmass_geo, wave_energy_geo):
    _xmin, _ymin, _xmax, _ymax = fetch_rays_geo.total_bounds
    # fit object should be a GeoJSON-like Feature or FeatureCollection
    _extent_feature = {
        "type": "Feature",
        "geometry": {"type": "Polygon",
                     "coordinates": [[
                         [_xmax, _ymax],
                         [_xmax, _ymin],
                         [_xmin, _ymin],
                         [_xmin, _ymax],
                         [_xmax, _ymax]]]},
        "properties": {}
    }
    _landmass = altair.Chart(landmass_geo).mark_geoshape(
        clip=True,
        fill='lightgrey'
    ).project(
        type='identity',
        reflectY=True, # Canvas and SVG treats positive y as down
        fit=_extent_feature
    )

    _points = altair.Chart(wave_energy_geo).mark_geoshape(
        filled=False,
        strokeWidth=1,
        # size=0.5  # must use mark_circle with x,y encoding instead.
    ).project(
        type='identity',
        reflectY=True # Canvas and SVG treats positive y as down
    ).encode(
        color='max_E_type:N',
        # tooltip=altair.Tooltip(
        #     ['exposure'] + rank_vars, format='.2f')
    )

    _rays = altair.Chart(fetch_rays_geo).mark_geoshape(
        filled=False,
        strokeWidth=0.2,
        stroke='gray'
        # size=0.5  # must use mark_circle with x,y encoding instead.
    ).project(
        type='identity',
        reflectY=True # Canvas and SVG treats positive y as down
    )
    _landmass + _rays + _points
    return


if __name__ == "__main__":
    app.run()
