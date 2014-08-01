import BeautifulSoup
import json
import os
import pytz
import requests
import sys
import xml.etree.ElementTree

from parser import Parser

CUR_DIR = os.path.dirname(os.path.realpath(__file__))

if __name__ == "__main__":
    
    # Instantiate our parser
    parser = Parser()
    
    # This is the main page that lists all the closed storms
    list_url = "http://www.nhc.noaa.gov/gis/archive_besttrack_results.php?year=2014"
    request = requests.get(list_url)
    html_contents = request.text

    # Parse the lists with beautifulsoup to find the kmz links
    soup = BeautifulSoup.BeautifulSoup(html_contents)

    # Find all the kmz hyperlinks in the HTML results
    kmz_links = []
    for link in soup.findAll('a'):
        if link.has_key('href') and link['href'].endswith('kmz'):
            kmz_links.append('http://www.nhc.noaa.gov/gis/' + link['href'])

    # Request each kmz file and extract the KML
    for storm_url in kmz_links:

        print 'Requesting URL: %s' % storm_url
        request = requests.get(storm_url)
        kml_contents = parser.extract_kml_from_kmz_file_contents(request.content)

        # Turn the KML into an XML tree
        ns = '{http://earth.google.com/kml/2.2}'
        root = xml.etree.ElementTree.fromstring(kml_contents)
        
        # Get the storm identifier
        storm_id_el = root.find(ns + 'Document/' + ns + 'name')
        if storm_id_el is not None:
            storm_id = storm_id_el.text.strip()
        else:
            sys.exit("Could not find element for the storm name.")
        
        # Find all the placemarks and create points
        features = []
        points = []
        
        for placemark_el in root.findall('.//' + ns + 'Placemark'):
            
            # Extract the data from the XML nodes
            data = {}
            data['title'] = parser.get_element_text(placemark_el, ns + 'name')
            data['lat'] = parser.get_element_float(placemark_el, ns + 'lat')
            data['lng'] = parser.get_element_float(placemark_el, ns + 'lon')
            data['storm_name'] = parser.get_element_text(placemark_el, ns + 'stormName')
            data['storm_number'] = parser.get_element_text(placemark_el, ns + 'stormNum')
            data['basin'] = parser.get_element_text(placemark_el, ns + 'basin')
            data['storm_type'] = parser.get_element_text(placemark_el, ns + 'stormType')
            data['intensity_mph'] = parser.get_element_float(placemark_el, ns + 'intensityMPH')
            data['intensity_kph'] = parser.get_element_float(placemark_el, ns + 'intensityKPH')
            data['pressure'] = parser.get_element_float(placemark_el, ns + 'minSeaLevelPres')
            data['datetime'] = parser.get_element_datetime(placemark_el, ns + 'atcfdtg', '%Y%m%d%H', pytz.utc).isoformat()
            points.append(data)
            
            # Create a point feature
            point_feature = parser.create_point_feature(data['lng'], data['lat'], data)
            features.append(point_feature)

        # Create a linestring feature from the points
        points_list = [(d['lng'], d['lat']) for d in points]
        line_feature = parser.create_linestring_feature(points_list, {})
        features.append(line_feature)

        #### Write out the GeoJSON file ###

        # Create the output dict
        output = {
            "type": "FeatureCollection",
            "features": features,
        }
    
        filename = '%s.geojson' % (storm_id.lower().replace(" ", "_"))
        print 'Creating File: %s' % filename
        
        # Write out file
        filepath = os.path.join(CUR_DIR, 'output/%s' % filename)
        with open(filepath, 'w') as f:
            f.write(json.dumps(output, indent=4))

    print "Done."