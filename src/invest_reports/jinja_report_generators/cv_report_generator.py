import json
import os
import time

import altair
import geopandas
import pandas
from jinja2 import Environment, PackageLoader, select_autoescape
import natcap.invest.utils
import natcap.invest.datastack
from natcap.invest.coastal_vulnerability import MODEL_SPEC

import invest_reports.utils
from invest_reports.utils import RasterPlotConfig

# perform transformations before embedding
# data in the chart's spec in order to conserve space
# altair.data_transformers.enable("vegafusion")
# default max rows is 5000. This seems to have no impact
# when using the vegafusion transformer though.
altair.data_transformers.disable_max_rows()

# Locate report template.
env = Environment(
    loader=PackageLoader('invest_reports', 'jinja_templates'),
    autoescape=select_autoescape()
)
template = env.get_template('coastal_vulnerability.html')

# Define basic info.
model_name = 'Coastal Vulnerability'
timestamp = time.strftime('%Y-%m-%d %H:%M')

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
    'gradientLength': 100
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


def chart_wave_energy(wave_energy_geo):
    base_points = chart_base_points(wave_energy_geo)

    points = base_points.mark_circle(
        filled=point_fill,
        strokeWidth=stroke_width,
    ).encode(
        color='max_E_type:N',
        size='wave:Q'
    )

    return points


def chart_habitat_map(habitat_protection_csv, exposure_geo, landmass):
    habitat_df = pandas.read_csv(habitat_protection_csv)
    habitat_geo = exposure_geo[['shore_id', 'geometry', 'habitat_role']].join(
        habitat_df.set_index('shore_id'), on='shore_id')
    habitats = set(habitat_df.columns).difference(set(['shore_id', 'R_hab']))

    def concat_habitats(row):
        hab_list = []
        for h in habitats:
            if row[h] != 5:
                hab_list.append(h)
        return ','.join(hab_list)
    habitat_geo['hab_presence'] = habitat_geo.apply(concat_habitats, axis=1)

    habitat_radio = altair.binding_radio(
        options=['All'] + list(habitats),
        labels=['All'] + list(habitats),
        name='Show points protected by each habitat:'
    )
    hab_param = altair.param(value='All', bind=habitat_radio)

    # TODO: can all maps reference the same json point dataset to save space?
    # Charts that are concatenated into the same specification will. Charts spread
    # across specs will not. Perhaps charts spread across specs could, but it
    # probably requires ditching altair and constructing the vegalite specs another way.
    habitat_base_points = chart_base_points(habitat_geo)

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
        color=altair.Color('habitat_role:Q').scale(scheme='viridis', reverse=True),
        tooltip=altair.Tooltip(list(habitats), format='.2f')
    )

    habitat_map = landmass + habitat_points
    habitat_map = habitat_map.properties(
        width=map_width,
        height=map_width / xy_ratio,
        title='The role of habitat in reducing coastal exposure'
    ).configure_legend(**legend_config)
    return habitat_map


def report(logfile_path):
    _, ds_info = natcap.invest.datastack.get_datastack_info(logfile_path)
    args_dict = ds_info.args
    workspace = args_dict['workspace_dir']
    suffix_str = natcap.invest.utils.make_suffix_string(args_dict, 'results_suffix')
    images_dir = os.path.join(workspace, '_images')
    if not os.path.exists(images_dir):
        os.mkdir(images_dir)

    with open(os.path.join(workspace, 'file_registry.json'), 'r') as file:
        file_registry = json.loads(file.read())

    rank_vars = ['R_hab', 'R_wind', 'R_wave', 'R_surge', 'R_relief']
    exposure_geo = geopandas.read_file(file_registry['coastal_exposure'])
    landmass_geo = geopandas.read_file(
        file_registry['clipped_projected_landmass'])
    extent_feature, xy_ratio = get_geojson_bbox(exposure_geo)
    landmass = chart_landmass(
        landmass_geo, clip=True, extent_feature=extent_feature)
    base_points = chart_base_points(exposure_geo)
    
    tooltip_vars = ['exposure'] + rank_vars
    if 'R_geomorph' in exposure_geo:
        rank_vars.append('R_geomorph')
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

    exposure_points = base_points.transform_filter(
        altair.expr.isValid(altair.datum.exposure)
    ).mark_circle(
        filled=point_fill,
        strokeWidth=stroke_width,
    ).encode(
        size=point_size_conditional,
        color=altair.Color(
            'exposure:Q',
            legend=altair.Legend(title='exposure')
        ).scale(scheme='plasma', reverse=True).bin(maxbins=4),
        tooltip=tooltip
    ).add_params(scale_population)

    _null_points = base_points.add_params(
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

    exposure_map = landmass + _null_points + exposure_points
    exposure_map = exposure_map.properties(
        width=map_width,
        height=map_width / xy_ratio,
        title='coastal exposure'
    ).configure_legend(**legend_config)
    exposure_map_json = exposure_map.to_json()

    habitat_map = chart_habitat_map(
        file_registry['habitat_protection'],
        exposure_geo,
        landmass)
    habitat_map_json = habitat_map.to_json()

    habitat_params_df = pandas.read_csv(args_dict['habitat_table_path'])
    habitat_table_description = f'Rank = {MODEL_SPEC.get_input(
        'habitat_table_path').get_column('rank').about}'

    exposure_histogram = altair.Chart(exposure_geo).mark_bar().encode(
        x=altair.X('exposure:Q', title='coastal exposure').bin(step=0.2),
        y='count()',
        color=altair.Color(
            'exposure:Q',
            legend=None,
        ).scale(scheme='plasma', reverse=True).bin(maxbins=4)
    ).properties(
        width=map_width,
        height=200
    )
    exposure_histogram_json = exposure_histogram.to_json()

    base_rank_vars_spec = base_points.mark_circle(
        filled=point_fill,
        strokeWidth=stroke_width,
        size=point_size
    )
    rank_vars_spec_list = []
    for var in rank_vars:
        point_spec = base_rank_vars_spec.encode(
            color=altair.Color(f'{var}:Q').scale(scheme='plasma', reverse=True),
        )
        rank_vars_spec_list.append(
            altair.layer(landmass, point_spec).properties(
                title=var))
    
    n_cols = len(rank_vars) // 2
    rank_vars_figure = altair.vconcat(
        altair.hconcat(*rank_vars_spec_list[:n_cols]),
        altair.hconcat(*rank_vars_spec_list[n_cols:])
    )
    rank_vars_figure_json = rank_vars_figure.to_json()

    intermediate_vars = ['relief', 'wind', 'wave', 'surge']
    intermediate_df = pandas.read_csv(file_registry['intermediate_exposure_csv'])
    facetted_histograms = altair.Chart(intermediate_df).mark_bar().encode(
        altair.X(
            altair.repeat('column'),
            type='quantitative',
            bin=altair.Bin(nice=True)),
        y='count()'
    ).repeat(
        column=intermediate_vars,
    )
    facetted_histograms_json = facetted_histograms.to_json()

    wave_energy_geo = geopandas.read_file(file_registry['wave_energies'])
    wave_energy_geo = wave_energy_geo.join(
        intermediate_df[['shore_id', 'wave']].set_index('shore_id'), on='shore_id')
    wave_points = chart_wave_energy(wave_energy_geo)
    wave_energy_map = landmass + wave_points
    wave_energy_map = wave_energy_map.properties(
        width=map_width,
        height=map_width / xy_ratio,
        title='Exposure to wind-driven waves vs. open ocean waves'
    ).configure_legend(**legend_config)
    wave_energy_map_json = wave_energy_map.to_json()

    # # Plot inputs.
    # inputs_img_src = invest_reports.utils.plot_and_base64_encode_rasters([
    #     RasterPlotConfig(args_dict['dem_path'], 'continuous'),
    #     RasterPlotConfig(args_dict['runoff_proxy_path'], 'continuous'),
    #     RasterPlotConfig(args_dict['lulc_path'], 'nominal')
    # ])

    # Generate HTML document.
    with open(os.path.join(workspace, f'{model_name.lower()}{suffix_str}.html'),
              'w', encoding='utf-8') as target_file:
        target_file.write(template.render(
            page_title=f'InVEST Results: {model_name}',
            model_name=model_name,
            timestamp=timestamp,
            args_dict=args_dict,
            exposure_map_json=exposure_map_json,
            habitat_map_json=habitat_map_json,
            habitat_params_table=habitat_params_df.to_html(),
            habitat_table_description=habitat_table_description,
            exposure_histogram_json=exposure_histogram_json,
            facetted_histograms_json=facetted_histograms_json,
            rank_vars_figure_json=rank_vars_figure_json,
            wave_energy_map_json=wave_energy_map_json,
            accordions_open_on_load=True,
            accent_color='lemonchiffon'
        ))


if __name__ == '__main__':
    logfile_path = 'C:/Users/dmf/projects/forum/cv/mar/sample_200m_12k_fetch/InVEST-coastal_vulnerability-log-2025-10-03--11_55_19.txt'
    # logfile_path = 'C:/Users/dmf/projects/forum/cv/sampledata/InVEST-coastal_vulnerability-log-2025-10-07--16_11_00.txt'
    report(logfile_path)
