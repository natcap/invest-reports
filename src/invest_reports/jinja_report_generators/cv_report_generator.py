import json
import logging
import os
import sys
import time

import altair
import geopandas
import pandas

from invest_reports import jinja_env

LOGGER = logging.getLogger(__name__)

TEMPLATE = jinja_env.get_template('coastal_vulnerability.html')

# vegafusion (`altair.data_transformers.enable("vegafusion")`)
# can perform transformations before embedding
# data in the chart's spec in order to conserve space.
# But vegafusion does not support geodataframe data - and geometries are
# not something we transform anyway. Plus, vegafusion seems incompatible
# with `disable_max_rows()` and there is no guarantee that the vegafusion
# transforms will get under the 5000 row default limit. So disabling
# the row limit is the only option.
altair.data_transformers.disable_max_rows()

stroke_width = 0.75
# When points are low-density, fill is nicer, or a thicker stroke.
# But when high-density, there's too much overplotting
# and no fill is better with a thinner stroke
# TODO: solve for this somehow? Or add a widget?
point_fill = False
if not point_fill:
    stroke_width = 1.5

point_size = 20
map_width = 450  # pixels

legend_config = {
    'labelFontSize': 14,
    'titleFontSize': 14,
    'orient': 'left',
    'gradientLength': 150
}
axis_config = {
    'labelFontSize': 14,
    'titleFontSize': 14,
}


def get_geojson_bbox(geodataframe):
    xmin, ymin, xmax, ymax = geodataframe.total_bounds
    xy_ratio = (xmax - xmin) / (ymax - ymin)
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
    return extent_feature, xy_ratio


def chart_landmass(geodataframe, clip=False, extent_feature=None):
    landmass = altair.Chart(geodataframe).mark_geoshape(
        clip=clip,
        fill='lightgrey'
    ).project(
        type='identity',
        reflectY=True,  # Canvas and SVG treats positive y as down
        fit=extent_feature
    )
    return landmass


def chart_base_points(geodataframe):
    # Plot points using mark_circle instead of mark_geoshape
    # so that they can get a size encoding later if needed.
    base_points = altair.Chart(
        geodataframe
    ).transform_calculate(
        lon="datum.geometry.coordinates[0]",
        lat="datum.geometry.coordinates[1]",
    ).project(
        type='identity',
        reflectY=True  # Canvas and SVG treats positive y as down
    ).mark_circle().encode(
        longitude='lon:Q',
        latitude='lat:Q',
    )
    return base_points


def chart_habitat_map(habitat_protection_csv, exposure_geodf, landmass_chart):
    habitat_df = pandas.read_csv(habitat_protection_csv)
    habitat_geodf = exposure_geodf[['shore_id', 'geometry', 'habitat_role']].join(
        habitat_df.set_index('shore_id'), on='shore_id')
    habitats = set(habitat_df.columns).difference(set(['shore_id', 'R_hab']))

    def concat_habitats(row):
        hab_list = []
        for h in habitats:
            if row[h] != 5:  # 5 is the model's code for no habitat present
                hab_list.append(h)
        return ','.join(hab_list)
    habitat_geodf['hab_presence'] = habitat_geodf.apply(concat_habitats, axis=1)

    habitat_radio = altair.binding_radio(
        options=['All'] + list(habitats),
        labels=['All'] + list(habitats),
        name='Show points protected by each habitat:'
    )
    hab_param = altair.param(value='All', bind=habitat_radio)

    habitat_base_points = chart_base_points(habitat_geodf)

    habitat_points = habitat_base_points.add_params(
        hab_param
    ).transform_filter(
        (hab_param == 'All') |
        altair.expr.test(hab_param, altair.datum.hab_presence)
    ).mark_circle(
        filled=point_fill,
        strokeWidth=stroke_width,
        size=point_size
    ).encode(
        color=altair.Color('habitat_role').scale(scheme='viridis', reverse=True),
        tooltip=altair.Tooltip(list(habitats), format='.2f')
    )

    _, xy_ratio = get_geojson_bbox(exposure_geodf)
    habitat_map = landmass_chart + habitat_points
    habitat_map = habitat_map.properties(
        width=map_width,
        height=map_width / xy_ratio,
        title='The role of habitat in reducing coastal exposure'
    ).configure_legend(**legend_config).configure_axis(**axis_config)
    return habitat_map


def report(file_registry, args_dict, model_spec, target_html_filepath):
    """Generate an html summary of Coastal Vulnerability results.

    Args:
        file_registry (dict): The ``natcap.invest.FileRegistry.registry``
            that was returned by ``natcap.invest.coastal_vulnerability.execute``.
        args_dict (dict): The arguments that were passed to
            ``natcap.invest.coastal_vulnerability.execute``.
        model_spec (natcap.invest.spec.ModelSpec):
            ``natcap.invest.coastal_vulnerability.MODEL_SPEC``
        target_html_filepath (str): path to an html file generated by this
            function.

    Returns:
        None
    """
    images_dir = os.path.join(args_dict['workspace_dir'], '_images')
    if not os.path.exists(images_dir):
        os.mkdir(images_dir)

    rank_vars = ['R_hab', 'R_wind', 'R_wave', 'R_surge', 'R_relief']
    exposure_geo = geopandas.read_file(file_registry['coastal_exposure'])
    if 'R_geomorph' in exposure_geo:
        rank_vars.append('R_geomorph')
    tooltip_vars = ['exposure'] + rank_vars

    landmass_geo = geopandas.read_file(
        file_registry['clipped_projected_landmass'])
    extent_feature, xy_ratio = get_geojson_bbox(exposure_geo)
    landmass_chart = chart_landmass(
        landmass_geo, clip=True, extent_feature=extent_feature)
    base_points = chart_base_points(exposure_geo)

    scale_population = altair.param(value=False)
    if 'population' in exposure_geo:
        # Population is used to scale point size in exposure maps,
        # but it is an optional input to the model.
        # If population is missing we still want to plot the point.
        exposure_geo.population = exposure_geo.population.fillna(-1)
        tooltip_vars.append('population')
        population_checkbox = altair.binding_checkbox(name='scale by population')
        scale_population = altair.param(value=True, bind=population_checkbox)

    tooltip = altair.Tooltip(tooltip_vars, format='.2f')
    null_checkbox = altair.binding_checkbox(name='show null')
    show_null = altair.param(value=False, bind=null_checkbox)

    point_size_conditional = altair.condition(
        scale_population,
        'population:Q',
        altair.value(point_size))

    exposure_points_chart = base_points.transform_filter(
        altair.expr.isValid(altair.datum.exposure)
    ).mark_circle(
        filled=point_fill,
        strokeWidth=stroke_width,
    ).encode(
        size=point_size_conditional,
        color=altair.Color(
            'exposure',
            legend=altair.Legend(
                title='exposure', 
                values=[1, 2, 3, 4, 5],  # force these values and labels
                labelExpr="datum.value",  # value refers to the list above.
            )
        ).scale(scheme='plasma', reverse=True).bin(extent=[1.0, 5.0]),
        tooltip=tooltip
    ).add_params(scale_population)

    null_points_chart = base_points.add_params(
        show_null
    ).transform_filter(
        show_null & ~altair.expr.isValid(altair.datum.exposure)
    ).mark_circle(
        filled=point_fill,
        strokeWidth=stroke_width,
        color='gray',
        invalid='show'
    ).encode(
        size=point_size_conditional,
        tooltip=tooltip
    ).add_params(scale_population)

    exposure_map = landmass_chart + null_points_chart + exposure_points_chart
    exposure_map = exposure_map.properties(
        width=map_width,
        height=map_width / xy_ratio,
        title='coastal exposure'
    ).configure_legend(**legend_config)
    exposure_map_json = exposure_map.to_json()

    habitat_map = chart_habitat_map(
        file_registry['habitat_protection'],
        exposure_geo,
        landmass_chart)
    habitat_map_json = habitat_map.to_json()

    habitat_params_df = pandas.read_csv(args_dict['habitat_table_path'])
    habitat_table_description = f'Rank = {model_spec.get_input(
        'habitat_table_path').get_column('rank').about}'

    exposure_histogram = altair.Chart(exposure_geo).mark_bar().encode(
        x=altair.X('exposure', title='coastal exposure').bin(step=0.2),
        y='count()',
        color=altair.Color(
            'exposure',
            legend=None,
        ).scale(scheme='plasma', reverse=True).bin(maxbins=4)
    ).properties(
        width=map_width,
        height=200
    ).configure_axis(**axis_config)
    exposure_histogram_json = exposure_histogram.to_json()

    base_rank_vars_chart = base_points.mark_circle(
        filled=point_fill,
        strokeWidth=stroke_width,
        size=point_size
    )
    rank_vars_chart_list = []
    for var in rank_vars:
        point_chart = base_rank_vars_chart.encode(
            color=altair.Color(
                f'{var}',
                legend=altair.Legend(title='rank')
            ).scale(scheme='plasma', reverse=True),
        )
        rank_vars_chart_list.append(
            altair.layer(landmass_chart, point_chart).properties(
                title=var))
    
    n_cols = len(rank_vars) // 2
    rank_vars_figure = altair.vconcat(
        altair.hconcat(*rank_vars_chart_list[:n_cols]),
        altair.hconcat(*rank_vars_chart_list[n_cols:])
    ).configure_axis(**axis_config)
    rank_vars_figure_json = rank_vars_figure.to_json()

    csv_spec = model_spec.get_output('intermediate_exposure_csv')
    intermediate_vars = ['relief', 'wind', 'wave', 'surge']
    units = [natcap.invest.spec.format_unit(csv_spec.get_column(var).units)
             for var in intermediate_vars]
    renamed_vars = [f'{var} {u}'
                    for var, u in zip(intermediate_vars, units)]
    intermediate_df = pandas.read_csv(file_registry['intermediate_exposure_csv'])
    variable_label_lookup = {var: new_var for var, new_var 
                             in zip(intermediate_vars, renamed_vars)}
    intermediate_df.rename(
        columns=variable_label_lookup, inplace=True)
    facetted_histograms = altair.Chart(intermediate_df).mark_bar().encode(
        altair.X(
            altair.repeat('column'),
            type='quantitative',
            bin=altair.Bin(nice=True)),
        y='count()'
    ).properties(
        width=map_width // 2
    ).repeat(
        column=renamed_vars,
    ).configure_axis(**axis_config)
    facetted_histograms_json = facetted_histograms.to_json()

    wave_energy_geo = geopandas.read_file(file_registry['wave_energies'])
    wave_var = variable_label_lookup['wave']
    wave_energy_geo = wave_energy_geo.join(
        intermediate_df[['shore_id', wave_var]].set_index(
            'shore_id'), on='shore_id')
    base_wave_points = chart_base_points(wave_energy_geo)
    wave_points_chart = base_wave_points.mark_circle(
        filled=point_fill,
        strokeWidth=stroke_width,
    ).encode(
        color=altair.Color(
            'max_E_type:N',
            legend=altair.Legend(title='dominant wave type')
        ),
        size=altair.Size(wave_var)
    )
    wave_energy_map = landmass_chart + wave_points_chart
    wave_energy_map = wave_energy_map.properties(
        width=map_width + 30,  # extra space for legend
        height=map_width / xy_ratio,
        title='local wind-driven waves vs. open ocean waves'
    ).configure_legend(**legend_config)
    wave_energy_map_json = wave_energy_map.to_json()

    # later this may be in model_spec
    model_description = \
        """
        The Coastal Vulnerability model calculates a coastal exposure index,
        which represents the relative exposure of different coastline segments
        to erosion and inundation caused by storms within the region of interest.
        The index values range from 1 (least exposed) to 5 (most exposed) and
        are calculated as the geometric mean of up to seven bio-geophysical
        variables.
        """
    # Generate HTML document.
    model_name = model_spec.model_title
    
    with open(target_html_filepath, 'w', encoding='utf-8') as target_file:
        target_file.write(TEMPLATE.render(
            report_script=__file__,
            timestamp=time.strftime('%Y-%m-%d %H:%M'),
            page_title=f'InVEST Results: {model_name}',
            model_id=model_spec.model_id,
            model_name=model_name,
            model_description=model_description,
            userguide_page=model_spec.userguide,
            args_dict=args_dict,
            exposure_map_json=exposure_map_json,
            habitat_map_json=habitat_map_json,
            habitat_params_table=habitat_params_df.to_html(),
            habitat_table_description=habitat_table_description,
            exposure_histogram_json=exposure_histogram_json,
            facetted_histograms_json=facetted_histograms_json,
            rank_vars_figure_json=rank_vars_figure_json,
            wave_energy_map_json=wave_energy_map_json,
            model_spec_outputs=model_spec.outputs,
            accordions_open_on_load=True,
        ))
    LOGGER.info(f'Created {target_html_filepath}')


if __name__ == '__main__':
    from natcap.invest.coastal_vulnerability import MODEL_SPEC
    import natcap.invest.datastack
    handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    # logfile_path = 'C:/Users/dmf/projects/forum/cv/mar/sample_200m_12k_fetch/InVEST-coastal_vulnerability-log-2025-10-03--11_55_19.txt'
    logfile_path = 'C:/Users/dmf/projects/forum/cv/sampledata/InVEST-coastal_vulnerability-log-2025-10-07--16_11_00.txt'
    _, ds_info = natcap.invest.datastack.get_datastack_info(logfile_path)
    args_dict = MODEL_SPEC.preprocess_inputs(ds_info.args)
    file_registry_path = os.path.join(
        args_dict['workspace_dir'],
        f'file_registry{args_dict['results_suffix']}.json')

    with open(file_registry_path, 'r') as file:
        file_registry = json.loads(file.read())

    target_filepath = os.path.join(
        args_dict['workspace_dir'],
        f'{MODEL_SPEC.model_id.lower()}_report{args_dict['results_suffix']}.html')
    report(file_registry, args_dict, MODEL_SPEC, target_filepath)
