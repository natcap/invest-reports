import json
import os
import time

import altair
from jinja2 import Environment, PackageLoader, select_autoescape
import natcap.invest.utils
from natcap.invest import datastack
import invest_reports.utils
from invest_reports.utils import RasterPlotConfig
import geopandas
import pandas


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
point_fill = True
point_size = 20
map_width = 600  # pixels


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


def report(logfile_path):
    _, ds_info = datastack.get_datastack_info(logfile_path)
    args_dict = ds_info.args
    workspace = args_dict['workspace_dir']
    suffix_str = natcap.invest.utils.make_suffix_string(args_dict, 'results_suffix')
    images_dir = os.path.join(workspace, '_images')
    if not os.path.exists(images_dir):
        os.mkdir(images_dir)

    with open(os.path.join(workspace, 'file_registry.json'), 'r') as file:
        file_registry = json.loads(file.read())

    rank_vars = ['R_hab', 'R_wind', 'R_wave', 'R_surge', 'R_relief']
    tooltip_vars = ['exposure'] + rank_vars
    exposure_geo = geopandas.read_file(file_registry['coastal_exposure'])
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

    landmass_geo = geopandas.read_file(
        file_registry['clipped_projected_landmass'])
    extent_feature, xy_ratio = get_geojson_bbox(exposure_geo)
    landmass = chart_landmass(
        landmass_geo, clip=True, extent_feature=extent_feature)
    base_points = chart_base_points(exposure_geo)

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
        height=map_width / xy_ratio
    ).configure_legend(
        orient='left',
        gradientVerticalMaxLength=100,
    )
    # exposure_map_svg_src = os.path.join(images_dir, 'exposure_map.svg')
    # exposure_map_html_path = os.path.join(images_dir, 'exposure_map.html')
    # exposure_map.save(exposure_map_svg_src)
    # exposure_map.save(exposure_map_html_path)
    exposure_map_json = exposure_map.to_json()

    habitat_df = pandas.read_csv(file_registry['habitat_protection'])
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
        name='Filter habitats:'
    )
    hab_param = altair.param(value='All', bind=habitat_radio)

    # TODO: can all maps reference the same json point dataset to save space?
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
        height=map_width / xy_ratio
    ).configure_legend(
        orient='left',
        gradientVerticalMaxLength=100,
    )
    habitat_map_json = habitat_map.to_json()

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
            accordions_open_on_load=True,
            accent_color='lemonchiffon'
        ))


if __name__ == '__main__':
    logfile_path = 'C:/Users/dmf/projects/forum/cv/sampledata/InVEST-coastal_vulnerability-log-2025-10-01--15_17_00.txt'
    report(logfile_path)
