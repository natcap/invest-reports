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
    # altair.renderers.enable("browser")
    return altair, datastack, geopandas, mo, os, pandas


@app.cell
def _(datastack, mo):
    logfile_path = mo.cli_args().get('logfile')
    # logfile_path = 'C:/Users/dmf/projects/forum/cv/mar/sample_200m/InVEST-coastal_vulnerability-log-2025-09-12--11_38_58.txt'
    logfile_path = 'C:/Users/dmf/projects/forum/cv/sampledata/InVEST-coastal_vulnerability-log-2025-09-10--10_57_52.txt'
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
    if 'population' in exposure_geo:
        exposure_geo.population = exposure_geo.population.fillna(-1)
    return (exposure_geo,)


@app.cell
def _(geopandas, os, pandas, workspace):
    landmass_geo = geopandas.read_file(os.path.join(workspace, 'intermediate/shore_points/clipped_projected_landmass.gpkg'))
    fetch_rays_geo = geopandas.read_file(os.path.join(workspace, 'intermediate/wind_wave/fetch_rays.gpkg'))
    wave_energy_geo = geopandas.read_file(os.path.join(workspace, 'intermediate/wind_wave/wave_energies.gpkg'))
    habitat_df = pandas.read_csv(os.path.join(workspace, 'intermediate/habitats/habitat_protection.csv'))
    return fetch_rays_geo, habitat_df, landmass_geo, wave_energy_geo


@app.cell
def _(altair, exposure_geo, landmass_geo, rank_vars):
    # slider = altair.binding_range(min=1, max=5, step=0.1)
    # cutoff = altair.param(bind=slider, value=4)
    # predicate = altair.datum.exposure < cutoff

    # domain = [1, 2, 3, 4, 5]
    # range_ = ['#9cc8e2', '#9cc8e2', 'red', '#5ba3cf', '#125ca4']
    stroke_width = 0.75
    point_fill = False
    point_size = 20

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

    def chart_landmass(dataframe, clip=False, extent_feature=None):
        _landmass = altair.Chart(dataframe).mark_geoshape(
            clip=clip,
            fill='lightgrey'
        ).project(
            type='identity',
            reflectY=True, # Canvas and SVG treats positive y as down
            fit=extent_feature
        ).properties(
            # width=900
            height=800
        )
        return _landmass

    landmass = chart_landmass(landmass_geo, clip=True, extent_feature=extent_feature)

    _pt_size_slider = altair.binding_range(min=8, max=40, step=2, name='point size')
    _pt_size = altair.param(bind=_pt_size_slider, value=12)

    _null_checkbox = altair.binding_checkbox(name='show null')
    _show_null = altair.param(value=False, bind=_null_checkbox)

    _population_checkbox = altair.binding_checkbox(name='scale by population')
    _scale_population = altair.param(value=False, bind=_population_checkbox)

    tooltip = altair.Tooltip(
        ['exposure', 'population'] + rank_vars, format='.2f')

    def chart_base_points(dataframe):
        base_points = altair.Chart(
            dataframe
        ).transform_calculate(
            lon="datum.geometry.coordinates[0]",
            lat="datum.geometry.coordinates[1]",
        ).project(
            type='identity',
            reflectY=True # Canvas and SVG treats positive y as down
        ).mark_circle().encode(
            longitude='lon:Q',
            latitude='lat:Q',
        )
        return base_points

    base_points = chart_base_points(exposure_geo)

    point_size_conditional = altair.condition(
        _scale_population,
        'population:Q',
        altair.value(point_size))

    _points = base_points.transform_filter(
        altair.expr.isValid(altair.datum.exposure)
    ).mark_circle(
        filled=point_fill,
        strokeWidth=stroke_width,
    ).encode(
        size=point_size_conditional,
        color=altair.Color('exposure:Q').scale(scheme='plasma', reverse=True).bin(maxbins=4),
        tooltip=tooltip
    ).add_params(_scale_population)

    _null_points = base_points.add_params(
        _show_null
    ).transform_filter(
        _show_null & ~altair.expr.isValid(altair.datum.exposure)
    ).mark_circle(
        filled=point_fill,
        strokeWidth=stroke_width,
        color='gray',
        invalid='show'
    ).encode(
        size=point_size_conditional,
        tooltip=tooltip
    ).add_params(_scale_population)

    _map = landmass + _null_points + _points
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
    return (
        chart_base_points,
        chart_landmass,
        landmass,
        point_fill,
        point_size,
        stroke_width,
    )


@app.cell
def _(exposure_geo, habitat_df):
    habitat_geo = exposure_geo[['shore_id', 'geometry', 'habitat_role']].join(habitat_df.set_index('shore_id'), on='shore_id')
    habitats = set(habitat_df.columns).difference(set(['shore_id', 'R_hab']))

    def concat_habitats(row):
        hab_list = []
        for h in habitats:
            if row[h] != 5:
                hab_list.append(h)
        return ','.join(hab_list)
    habitat_geo['hab_presence'] = habitat_geo.apply(concat_habitats, axis=1)
    habitat_geo
    return habitat_geo, habitats


@app.cell
def _(
    altair,
    chart_base_points,
    habitat_geo,
    habitats,
    landmass,
    point_fill,
    point_size,
    stroke_width,
):
    _radio = altair.binding_radio(
        options=['All'] + list(habitats),
        labels=['All'] + list(habitats),
        name='Filter habitats:'
    )
    hab_param = altair.param(value='All', bind=_radio)

    _base_points = chart_base_points(habitat_geo)

    _points = _base_points.add_params(
        hab_param
    ).transform_filter(
        (hab_param == 'All') |
        altair.expr.test(hab_param, altair.datum.hab_presence)
    ).mark_circle(
        filled=point_fill,
        strokeWidth=stroke_width,
        size=point_size
    ).encode(
        color=altair.Color('habitat_role:Q').scale(scheme='viridis', reverse=True),
        tooltip=altair.Tooltip(list(habitats), format='.2f')
    )

    _map = landmass + _points
    _map
    return


@app.cell
def _(
    altair,
    chart_base_points,
    chart_landmass,
    fetch_rays_geo,
    landmass_geo,
    point_fill,
    point_size,
    stroke_width,
    wave_energy_geo,
):
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

    _landmass = chart_landmass(landmass_geo, clip=True, extent_feature=_extent_feature)
    _base_points = chart_base_points(wave_energy_geo)

    _points = _base_points.mark_circle(
        filled=point_fill,
        strokeWidth=stroke_width,
        size=point_size
    ).encode(
        color='max_E_type:N',
    )

    _rays = altair.Chart(fetch_rays_geo).mark_geoshape(
        strokeWidth=0.2,
        stroke='gray'
    ).project(
        type='identity',
        reflectY=True # Canvas and SVG treats positive y as down
    )
    _landmass + _rays + _points
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
