#!/usr/bin/env python
# coding: utf-8

import joblib
import numpy as np
import pandas as pd

from bokeh.layouts import column, row, gridplot
from bokeh.models import (ColumnDataSource, CustomJS, LinearColorMapper,
                          GeoJSONDataSource, Panel, Tabs,
                          FixedTicker, ColorBar, Select,
                          Slider, TextInput, NumeralTickFormatter)
from bokeh.plotting import figure, curdoc
from bokeh.themes import Theme
from bokeh.io import show, output_notebook, reset_output
from bokeh.palettes import YlOrRd9

from flask import Flask, render_template
from threading import Thread
from bokeh.embed import server_document
from bokeh.server.server import Server
from tornado.ioloop import IOLoop
from bokeh.embed import components

app = Flask(__name__)

@app.route('/')
def bkapp():
    # --- data ---
    # these were calculated on foe-linux: at the bottom of emulator_plots.ipynb
    path = '/home/emulator/data'

    source_dfs_exposure = joblib.load(f'{path}/source_dfs_exposure_scaled.joblib.compressed')
    source_dfs_mort = joblib.load(f'{path}/source_dfs_mort_scaled.joblib.compressed')
    options = joblib.load(f'{path}/options.joblib.compressed')

    results_china = joblib.load(f'{path}/results_compare_china_scaled.joblib.compressed')

    sources = {}
    for key, source_df in source_dfs_exposure.items():
        sources.update({key: ColumnDataSource(source_df)})

    for key, source_df in source_dfs_mort.items():
        sources.update({key: ColumnDataSource(source_df)})

    # --- formatting ---
    variables = {
        'exposure': 'Exposure',
        'mort': 'MORT',
        'dalys_rate': 'Rate of DALYs'
    }
    output_verbages = {
        'PM2_5_DRY': u'PM\u2082.\u2085',
        'o3_6mDM8h': u'O\u2083'
    }
    units_outcome = {
        'exposure_PM2_5_DRY': '\u03BCg/m\u00b3',
        'exposure_o3_6mDM8h': 'ppb',
        'mort': 'deaths',
        'dalys_rate': 'DALYs per 100,000'
    }

    # --- functions ---
    def create_plot(source, output, outcome):
        variable = variables[outcome]
        output_verbage = output_verbages[output]

        if outcome == 'exposure':
            if output == 'PM2_5_DRY':
                low = 0
                high = 90
            elif output == 'o3_6mDM8h':
                low = 24
                high = 60
            round_to = 1
            units = units_outcome[f'exposure_{output}']
        elif outcome == 'mort':
            low = 0
            round_to = -2
            units = units_outcome[outcome]
            if output == 'PM2_5_DRY':
                high = 150_000
            elif output == 'o3_6mDM8h':
                high = 2_700
        elif outcome =='dalys_rate':
            low = 0
            high = 200
            round_to = 1
            units = units_outcome[outcome]

        ticks = FixedTicker(ticks=np.linspace(low, high, 10))

        if outcome == 'mort':
            round_to = -2
        if outcome == 'dalys_rate':
             round_to = 1

        #palette = Viridis10
        palette = YlOrRd9[::-1]
        color_mapper = LinearColorMapper(
            palette=palette,
            low=low,
            high=high)

        value_mean = int(round(results_china[output][outcome]['mean']['RES1.0_IND1.0_TRA1.0_AGR1.0_ENE1.0'], round_to))

        plot = figure(
            plot_height=400,
            plot_width=600,
            title=f"{variable} from {output_verbage} in China = {value_mean:,} {units}",
            tools="pan,wheel_zoom,reset,hover,save",
            x_axis_location=None,
            y_axis_location=None,
            tooltips=[
                ("State", "@location"),
                (variable, "@scenario_variable{0,0}" + " " + units),
                ("(Lon, Lat)", "($x, $y)")])
        plot.grid.grid_line_color = None
        plot.hover.point_policy = "follow_mouse"
        plot.multi_polygons(
            'xs', 'ys', source=source,
            fill_color={'field': 'scenario_variable', 'transform': color_mapper},
            fill_alpha=0.7, line_color="grey", line_width=0.5)
        color_bar = ColorBar(
            color_mapper=color_mapper, ticker=ticks,
            label_standoff=12, border_line_color=None, location=(0,0),
            formatter=NumeralTickFormatter(format="0,0"))
        plot.add_layout(color_bar, 'right')
        return plot


    # --- plot ---
    source_exposure_PM2_5_DRY = sources['PM2_5_DRY_exposure_mean']
    source_exposure_o3_6mDM8h = sources['o3_6mDM8h_exposure_mean']
    source_mort_PM2_5_DRY = sources['PM2_5_DRY_mort_mean']
    source_mort_o3_6mDM8h = sources['o3_6mDM8h_mort_mean']

    plot_exposure_PM2_5_DRY = create_plot(source_exposure_PM2_5_DRY, 'PM2_5_DRY', 'exposure')
    plot_exposure_o3_6mDM8h = create_plot(source_exposure_o3_6mDM8h, 'o3_6mDM8h', 'exposure')
    plot_mort_PM2_5_DRY = create_plot(source_mort_PM2_5_DRY, 'PM2_5_DRY', 'mort')
    plot_mort_o3_6mDM8h = create_plot(source_mort_o3_6mDM8h, 'o3_6mDM8h', 'mort')

    slider_mort_res = Slider(start=0.0, end=1.4, value=1.0, step=0.2, title="Fractional residential emissions", format='0.f')
    slider_mort_ind = Slider(start=0.0, end=1.4, value=1.0, step=0.2, title="Fractional industrial emissions", format='0.f')
    slider_mort_tra = Slider(start=0.0, end=1.4, value=1.0, step=0.2, title="Fractional land transport emissions", format='0.f')
    slider_mort_agr = Slider(start=0.0, end=1.4, value=1.0, step=0.2, title="Fractional agricultural emissions", format='0.f')
    slider_mort_ene = Slider(start=0.0, end=1.4, value=1.0, step=0.2, title="Fractional power generation emissions", format='0.f')
    slider_labels = {
        '0': '0.0',
        '0.2': '0.2',
        '0.4': '0.4',
        '0.6': '0.6',
        '0.8': '0.8',
        '1': '1.0',
        '1.2': '1.2',
        '1.4': '1.4'}
    text_input = TextInput(title="Add graph title", value='')
    callback_mort = CustomJS(
        args={
            'source_exposure_PM2_5_DRY': source_exposure_PM2_5_DRY,
            'source_exposure_o3_6mDM8h': source_exposure_o3_6mDM8h,
            'source_mort_PM2_5_DRY': source_mort_PM2_5_DRY,
            'source_mort_o3_6mDM8h': source_mort_o3_6mDM8h,
            'slider_mort_res': slider_mort_res,
            'slider_mort_ind': slider_mort_ind,
            'slider_mort_tra': slider_mort_tra,
            'slider_mort_agr': slider_mort_agr,
            'slider_mort_ene': slider_mort_ene,
            'slider_labels': slider_labels,
            'title_exposure_PM2_5_DRY': plot_exposure_PM2_5_DRY.title,
            'title_exposure_o3_6mDM8h': plot_exposure_o3_6mDM8h.title,
            'title_mort_PM2_5_DRY': plot_mort_PM2_5_DRY.title,
            'title_mort_o3_6mDM8h': plot_mort_o3_6mDM8h.title,
            'text_input': text_input,
            'results_china': results_china,
            'variables': variables,
            'output_verbages': output_verbages,
            'units_outcome': units_outcome},
        code="""
        const new_data_exposure_PM2_5_DRY = Object.assign({}, source_exposure_PM2_5_DRY.data);
        const new_data_exposure_o3_6mDM8h = Object.assign({}, source_exposure_o3_6mDM8h.data);
        const new_data_mort_PM2_5_DRY = Object.assign({}, source_mort_PM2_5_DRY.data);
        const new_data_mort_o3_6mDM8h = Object.assign({}, source_mort_o3_6mDM8h.data);

        var s1 = "RES";
        var s2 = "_IND";
        var s3 = "_TRA";
        var s4 = "_AGR";
        var s5 = "_ENE";

        var res = slider_labels[slider_mort_res.value.toString()];
        var ind = slider_labels[slider_mort_ind.value.toString()];
        var tra = slider_labels[slider_mort_tra.value.toString()];
        var agr = slider_labels[slider_mort_agr.value.toString()];
        var ene = slider_labels[slider_mort_ene.value.toString()];

        var sim = s1.concat(res, s2, ind, s3, tra, s4, agr, s5, ene);

        new_data_exposure_PM2_5_DRY.scenario_variable = source_exposure_PM2_5_DRY.data[sim];
        new_data_exposure_o3_6mDM8h.scenario_variable = source_exposure_o3_6mDM8h.data[sim];
        new_data_mort_PM2_5_DRY.scenario_variable = source_mort_PM2_5_DRY.data[sim];
        new_data_mort_o3_6mDM8h.scenario_variable = source_mort_o3_6mDM8h.data[sim];

        source_exposure_PM2_5_DRY.data = new_data_exposure_PM2_5_DRY;
        source_exposure_o3_6mDM8h.data = new_data_exposure_o3_6mDM8h;
        source_mort_PM2_5_DRY.data = new_data_mort_PM2_5_DRY;
        source_mort_o3_6mDM8h.data = new_data_mort_o3_6mDM8h;

        var value_china_exposure_PM2_5_DRY = Math.round(results_china["PM2_5_DRY"]["exposure"]["mean"][sim]*10)/10;
        var value_china_exposure_o3_6mDM8h = Math.round(results_china["o3_6mDM8h"]["exposure"]["mean"][sim]*10)/10;
        var value_china_mort_PM2_5_DRY = Math.round(results_china["PM2_5_DRY"]["mort"]["mean"][sim]/100)*100;
        var value_china_mort_o3_6mDM8h = Math.round(results_china["o3_6mDM8h"]["mort"]["mean"][sim]/100)*100;

        title_exposure_PM2_5_DRY.text = variables["exposure"] + " from " + output_verbages["PM2_5_DRY"] + " in China = " + value_china_exposure_PM2_5_DRY.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",") + " " + units_outcome["exposure_PM2_5_DRY"];
        title_exposure_o3_6mDM8h.text = variables["exposure"] + " from " + output_verbages["o3_6mDM8h"] + " in China = " + value_china_exposure_o3_6mDM8h.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",") + " " + units_outcome["exposure_o3_6mDM8h"];
        title_mort_PM2_5_DRY.text = variables["mort"] + " from " + output_verbages["PM2_5_DRY"] + " in China = " + value_china_mort_PM2_5_DRY.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",") + " " + units_outcome["mort"];
        title_mort_o3_6mDM8h.text = variables["mort"] + " from " + output_verbages["o3_6mDM8h"] + " in China = " + value_china_mort_o3_6mDM8h.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",") + " " + units_outcome["mort"];
            """)
    slider_mort_res.js_on_change('value', callback_mort)
    slider_mort_ind.js_on_change('value', callback_mort)
    slider_mort_tra.js_on_change('value', callback_mort)
    slider_mort_agr.js_on_change('value', callback_mort)
    slider_mort_ene.js_on_change('value', callback_mort)

    grid = gridplot(
        [[column(slider_mort_res, slider_mort_ind, slider_mort_tra, slider_mort_agr, slider_mort_ene)],
         [plot_exposure_PM2_5_DRY, plot_exposure_o3_6mDM8h],
         [plot_mort_PM2_5_DRY, plot_mort_o3_6mDM8h]],
        plot_width=400, plot_height=300) # , sizing_mode='scale_both'

    script, div = components(grid)
    return render_template("embed.html", script=script, div=div)


if __name__ == '__main__':
    app.run()
