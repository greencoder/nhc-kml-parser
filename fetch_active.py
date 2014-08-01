import datetime
import dateutil.parser
import json
import os
import pytz
import re
import requests
import sys
import urlparse
import xml.etree.ElementTree

from parser import Parser

CUR_DIR = os.path.dirname(os.path.realpath(__file__))

if __name__ == "__main__":

    parser = Parser()

    # Parse the XML
    url = 'http://www.nhc.noaa.gov/gis/kml/nhc_active.kml'
    parser.log("Requesting Main URL: %s" % url)
    request = requests.get(url)
    root = xml.etree.ElementTree.fromstring(request.text)

    # Find the Folder elements in the XML. These are going to contain storm data
    # and storm forecasts. (Also wind speeds, but we ignore this)
    ns = '{http://www.opengis.net/kml/2.2}'
    folder_els = root.findall(ns + "Document/" + ns + "Folder")

    folders = {}

    # Iterate over the <Folder> elements
    for folder_el in folder_els:

        # Get the ID attribute and the <name> element of the folder
        storm_id = folder_el.attrib['id']
        name = folder_el.find(ns + 'name').text

        # Skip windspeeds
        if storm_id in ['wsp']:
            continue

        # Find the <ExtendedData> element
        ext_data_els = folder_el.find(ns + 'ExtendedData')

        # Under the <ExtendedData> element we have a bunch of <Data> elements
        data = {}
        data['storm_type'] = parser.get_element_text(ext_data_els, ns + 'Data[@name="tcType"]/' + ns + 'value')
        data['storm_name'] = parser.get_element_text(ext_data_els, ns + 'Data[@name="tcName"]/' + ns + 'value')
        data['wallet'] = parser.get_element_text(ext_data_els, ns + 'Data[@name="wallet"]/' + ns + 'value')
        data['atcf_id'] = parser.get_element_text(ext_data_els, ns + 'Data[@name="wallet"]/' + ns + 'value')
        data['latitude_str'] = parser.get_element_text(ext_data_els, ns + 'Data[@name="centerLat"]/' + ns + 'value')
        data['longitude_str'] = parser.get_element_text(ext_data_els, ns + 'Data[@name="centerLon"]/' + ns + 'value')
        data['datetime_str'] = parser.get_element_text(ext_data_els, ns + 'Data[@name="dateTime"]/' + ns + 'value')
        data['movement'] = parser.get_element_text(ext_data_els, ns + 'Data[@name="movement"]/' + ns + 'value')
        data['min_pressure_str'] = parser.get_element_text(ext_data_els, ns + 'Data[@name="minimumPressure"]/' + ns + 'value')
        data['max_winds'] = parser.get_element_text(ext_data_els, ns + 'Data[@name="maxSustainedWind"]/' + ns + 'value')
        data['headline'] = parser.get_element_text(ext_data_els, ns + 'Data[@name="headline"]/' + ns + 'value')

        # Title case the storm name and storm type
        data['storm_name'] = data['storm_name'].title()
        data['storm_type'] = data['storm_type'].title()

        # Cast the lat/long into floats
        data['latitude'] = float(data['latitude_str'])
        data['longitude'] = float(data['longitude_str'])
        data.pop('latitude_str')
        data.pop('longitude_str')

        # Cast the datetime into an ISO format. This is particularly nasty
        dt_str = data['datetime_str']
        replaced_datetime_str = parser.replace_timezone_code_with_utc(dt_str)
        data['datetime'] = dateutil.parser.parse(replaced_datetime_str).isoformat()

        # Cast the pressure
        data['pressure_mb'] = float(data['min_pressure_str'].replace(" mb", ""))
        data.pop('min_pressure_str')

        # Parse and cast the winds
        data['max_winds_mph'] = int(data['max_winds'].replace(" mph", ""))
        data.pop('max_winds')

        # Add this to our dictionary for the current storm
        folders[storm_id] = data

        # Figure out what region this is in
        if data['wallet'].startswith('A'):
            data['region'] = "Atlantic"
        elif data['wallet'].startswith('E'):
            data['region'] = "Pacific"
        else:
            data['region'] = None
        
        # Find the best track link. It will be a link to a KMZ file
        network_link_el = folder_el.find(ns + 'NetworkLink')

        # If the file exists, we need to get its content and extract the KML from it
        # (KMZ is a zipped file containing a KML file and PNGs)
        if network_link_el.attrib['id'].endswith('bt'):
            url_best_track = network_link_el.find(ns + 'Link/' + ns + 'href').text
            parser.log("Requesting Best Track URL: %s" % url_best_track)
            request = requests.get(url_best_track)
            best_track_kml = parser.extract_kml_from_kmz_file_contents(request.content)
            data['best_track_points'] = parser.extract_best_track_points_from_kml(best_track_kml)

        # Find the nested <Folder id="[storm_id]forecast"> element
        forecast_folder_el = folder_el.find(ns + 'Folder[@id="%sforecast"]' % storm_id)

        # Set default values in case the forecast does not exist
        data['forecast_track_points'] = []
        data['forecast_cone_72_hour'] = []
        data['forecast_cone_120_hour'] = []
        data['url_forecast_watches'] = []

        if forecast_folder_el is not None:

            # Get the link to the forecast track, then get the forecast track points
            forecast_track_el = forecast_folder_el.find(ns + 'NetworkLink[@id="%sforecastTRACK"]' % storm_id)
            if forecast_track_el is not None:
                link_el = forecast_track_el.find(ns + 'Link')
                url_forecast_track = parser.get_element_text(link_el, ns + 'href')
                parser.log("Requesting Forecast Track URL: %s" % url_forecast_track)
                request = requests.get(url_forecast_track)
                forecast_track_kml = parser.extract_kml_from_kmz_file_contents(request.content)
                data['forecast_track_points'] = parser.extract_forecast_track_points_from_kml(forecast_track_kml)

            # Get the link to the forecast cone, then get the forecast cone
            forecast_cone_el = forecast_folder_el.find(ns + 'NetworkLink[@id="%sforecastCONE"]' % storm_id)
            if forecast_cone_el is not None:
                link_el = forecast_cone_el.find(ns + 'Link')
                url_forecast_cone = parser.get_element_text(link_el, ns + 'href')
                parser.log("Requesting Forecast Cone URL: %s" % url_forecast_cone)
                request = requests.get(url_forecast_cone)
                forecast_cone_kml = parser.extract_kml_from_kmz_file_contents(request.content)
                data['forecast_cone_72_hour'] = parser.extract_forecast_cone_from_kml(forecast_cone_kml, 72)
                data['forecast_cone_120_hour'] = parser.extract_forecast_cone_from_kml(forecast_cone_kml, 120)

    # Write out the files
    for storm_id, storm_dict in folders.items():

        features = []

        # Create a point feature for each best track point
        for item_dict in storm_dict['best_track_points']:
            props = {
                'type': 'track_point',
                'id': storm_id,
            }
            joined_props = dict(props.items() + item_dict.items())
            new_feature = parser.create_point_feature(item_dict['longitude'], item_dict['latitude'], joined_props)
            features.append(new_feature)

        # Create a linestring feature for the best track points
        points = [(d['longitude'], d['latitude']) for d in storm_dict['best_track_points']]
        props = {
            'type': 'track_line',
            'id': storm_id,
        }
        best_track_linestring_feature = parser.create_linestring_feature(points, props)
        features.append(best_track_linestring_feature)

        # Create a point feature for each forecast track point
        for item_dict in storm_dict['forecast_track_points']:
            props = {
                'type': 'forecast_track_point',
                'id': storm_id,
            }
            joined_props = dict(props.items() + item_dict.items())
            new_feature = parser.create_point_feature(item_dict['longitude'], item_dict['latitude'], joined_props)
            features.append(new_feature)

        # Create the linestring feature for the track points
        points = [(d['longitude'], d['latitude']) for d in storm_dict['forecast_track_points']]
        props = {
            'type': 'forecast_line',
            'id': storm_id,
        }
        forecast_linestring_feature = parser.create_linestring_feature(points, props)
        features.append(forecast_linestring_feature)

        # Create the polygon for the 72-hour cone of uncertainty
        props = { 
            'hours': 72, 
            'description': 
            '72-hour cone of uncertainty',
            'type': 'cone',
            'id': storm_id,
        }
        cone_72_polygon_feature = parser.create_polygon_feature(storm_dict['forecast_cone_72_hour'], props)

        # We might not get a feature back
        if cone_72_polygon_feature is not None:
            features.append(cone_72_polygon_feature)

        # Create the polygon for the 120-hour cone of uncertainty
        props = { 
            'hours': 120, 
            'description': '120-hour cone of uncertainty',
            'type': 'cone',
            'id': storm_id,
        }
        cone_120_polygon_feature = parser.create_polygon_feature(storm_dict['forecast_cone_120_hour'], props)
        
        # If there isn't a 120 polygon, we won't get a feature back
        if cone_120_polygon_feature is not None:
            features.append(cone_120_polygon_feature)

        # Create a metadata property
        metadata = {
            'storm_type': storm_dict['storm_type'],
            'storm_name': storm_dict['storm_name'],
            'wallet': storm_dict['wallet'],
            'atcf_id': storm_dict['atcf_id'],
            'latitude': storm_dict['latitude'],
            'longitude': storm_dict['longitude'],
            'datetime_str': storm_dict['datetime_str'],
            'datetime': storm_dict['datetime'],
            'movement': storm_dict['movement'],
            'pressure_mb': storm_dict['pressure_mb'],
            'max_winds_mph': storm_dict['max_winds_mph'],
            'headline': storm_dict['headline'],
        }

        # Create the output dict
        output = {
            "metadata": metadata,
            "type": "FeatureCollection",
            "features": features
        }
        
        # Write out the geojson file
        filepath = os.path.join(CUR_DIR, 'output/storm_%s.geojson' % storm_id)
        with open(filepath, 'w') as f:
            f.write(json.dumps(output, indent=4))

    # Note that we are finished
    parser.log("-- Finished Parsing Run --")