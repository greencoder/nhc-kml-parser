import datetime
import dateutil.parser
import pytz
import StringIO
import xml.etree.ElementTree
import zipfile

class Parser():
    
    def __init__(self):
        pass

    def log(self, message):
        with open('log.txt', 'a') as f:
            now = datetime.datetime.now()
            f.write("%s\t%s\n" % (now, message))

    def get_element_text(self, element, name, default_value=''):
        el = element.find(name)
        if el is not None and el.text:
            return el.text.strip()
        else:
            return default_value

    def get_element_int(self, element, name, default_value=None):
        el = element.find(name)
        if el is not None and el.text:
            try:
                return int(el.text.strip())
            except ValueError:
                return default_value
        else:
            return default_value

    def get_element_float(self, element, name, default_value=None):
        el = element.find(name)
        if el is not None and el.text:
            try:
                return float(el.text.strip())
            except ValueError:
                return default_value
        else:
            return default_value

    def get_element_datetime(self, element, name, format_str, timezone, default_value=None):
        el = element.find(name)
        if el is not None and el.text:
            try:
                dt_string = el.text.strip()
                datetime_obj = datetime.datetime.strptime(dt_string, format_str)
                datetime_tz_obj = datetime_obj.replace(tzinfo=timezone)
                return datetime_tz_obj
            except ValueError, e:
                return default_value
        else:
            return default_value

    def get_element_attr(self, element, attr_name, default_value=''):
        if element is not None and element.attrib.has_key(attr_name):
            return element.attrib[attr_name].strip()
        else:
            return default_value

    def extract_kml_from_kmz_file_contents(self, file_contents):

        # Extract the KML from the KMZ
        zfile = zipfile.ZipFile(StringIO.StringIO(file_contents))
        kml_filenames = [f for f in zfile.namelist() if f.endswith('.kml')]
        kml_filehandle = zfile.open(kml_filenames[0])

        # Return the contents as a string
        kml_contents = kml_filehandle.read().strip()
        return kml_contents

    def extract_best_track_points_from_kml(self, kml_string):

        # Turn the KML into a document tree
        root = xml.etree.ElementTree.fromstring(kml_string)

        # Find all the placemarks
        ns = "{http://earth.google.com/kml/2.2}"
        placemark_els = root.findall(ns + 'Document/' + ns + 'Folder/[@id=\'data\']' + ns + 'Placemark')

        placemarks = []
        for placemark_el in placemark_els:

            placemark = {}
            placemark['latitude'] = self.get_element_float(placemark_el, ns + 'lat')
            placemark['longitude'] = self.get_element_float(placemark_el, ns + 'lon')
            placemark['name'] = self.get_element_text(placemark_el, ns + 'stormName')
            placemark['number'] = self.get_element_int(placemark_el, ns + 'stormNum')
            placemark['region'] = self.get_element_text(placemark_el, ns + 'basin')
            placemark['intensity_mph'] = self.get_element_int(placemark_el, ns + 'intensityMPH')
            placemark['intensity_kph'] = self.get_element_int(placemark_el, ns + 'intensityKPH')
            placemark['pressure'] = self.get_element_int(placemark_el, ns + 'minSeaLevelPres')

            # Get the date string and cast it
            datetime_str = self.get_element_text(placemark_el, ns + 'atcfdtg')
            dt_obj = datetime.datetime.strptime(datetime_str, '%Y%m%d%H')
            placemark['datetime'] = dt_obj.replace(tzinfo=pytz.utc).isoformat()

            # Add it to the list
            placemarks.append(placemark)

        # Return the array
        return placemarks

    def extract_forecast_cone_from_kml(self, kml_string, period):

        # Turn the KML into a document tree
        root = xml.etree.ElementTree.fromstring(kml_string)

        # Find all the <Placemark> elements
        ns = "{http://www.opengis.net/kml/2.2}"
        placemark_els = root.findall(ns + 'Document/' + ns + 'Folder/' + ns + 'Placemark')

        # Find the placemark for the period we want
        for placemark_el in placemark_els:
            extended_data_el = placemark_el.find(ns + 'ExtendedData')
            period_value = self.get_element_int(extended_data_el, ns + 'Data[@name="fcstpd"]/' + ns + 'value')

            # Find the period we are looking for
            if period_value != period:
                continue

            # Extract the <coordinates> value
            linear_ring_el = placemark_el.find(ns + 'Polygon/' + ns + 'outerBoundaryIs/' + ns + 'LinearRing')
            coordinates_str = self.get_element_text(linear_ring_el, ns + 'coordinates')

            # Parse the coordinates into lat/lng pairs
            coordinates = []
            for item in coordinates_str.split(" "):
                lat_str, lng_str, elev_str = item.split(",")
                lat = float(lat_str)
                lng = float(lng_str)
                coordinates.append((lat,lng))

            # Return the array
            return coordinates

    def extract_forecast_track_line_from_kml(self, kml_string):

        # Turn the KML into a document tree
        root = xml.etree.ElementTree.fromstring(kml_string)

        # Find all the <Placemark> elements
        ns = "{http://www.opengis.net/kml/2.2}"
        placemark_els = root.findall(ns + 'Document/' + ns + 'Folder[@id=\'Forecast Track\']/' + ns + 'Placemark')

        for placemark_el in placemark_els:

            # We need to see if this is the placemark that contains the linestring or the points
            if placemark_el.find(ns + 'LineString') is None:
                continue

            # We need to find the <coordinates> element
            linestring_el = placemark_el.find(ns + 'LineString/')
            coordinates_str = self.get_element_text(placemark_el, ns + 'LineString/' + ns + 'coordinates')

            # Parse the coordinates into lat/long pairs
            coordinates = []
            for item in coordinates_str.split(" "):
                lat_str, lng_str, elev_str = item.split(",")
                lat = float(lat_str)
                lng = float(lng_str)
                coordinates.append((lat,lng))

            # Return the array
            return coordinates

    def extract_forecast_track_points_from_kml(self, kml_string):

        # Turn the KML into a document tree
        root = xml.etree.ElementTree.fromstring(kml_string)

        # Find all the <Placemark> elements
        ns = "{http://www.opengis.net/kml/2.2}"
        placemark_els = root.findall(ns + 'Document/' + ns + 'Folder[@id=\'Forecast Track\']/' + ns + 'Placemark')

        placemarks = []
        for placemark_el in placemark_els:

            # We need to see if this is the placemark that contains the linestring or the points
            if placemark_el.find(ns + 'Point') is None:
                continue

            # Fine the <ExtendedData> element
            extended_data_el = placemark_el.find(ns + 'ExtendedData')

            placemark = {}

            placemark['tc_speed'] = self.get_element_int(extended_data_el, ns + 'Data[@name="tcSpd"]' + ns + 'value')
            placemark['latitude'] = self.get_element_float(extended_data_el, ns + 'Data[@name="lat"]' + ns + 'value')
            placemark['longitude'] = self.get_element_float(extended_data_el, ns + 'Data[@name="lon"]' + ns + 'value')
            placemark['storm_type'] = self.get_element_text(extended_data_el, ns + 'Data[@name="stormType"]' + ns + 'value')
            placemark['expected_speed'] = self.get_element_int(extended_data_el, ns + 'Data[@name="fctspd"]' + ns + 'value')
            placemark['atcf_id'] = self.get_element_text(extended_data_el, ns + 'Data[@name="atcfid"]' + ns + 'value')
            placemark['storm_number'] = self.get_element_int(extended_data_el, ns + 'Data[@name="stormNum"]' + ns + 'value')
            placemark['storm_name'] = self.get_element_text(extended_data_el, ns + 'Data[@name="storm"]' + ns + 'value')
            placemark['label'] = self.get_element_text(extended_data_el, ns + 'Data[@name="dateLbl"]' + ns + 'value')
            placemark['region'] = self.get_element_text(extended_data_el, ns + 'Data[@name="basin"]' + ns + 'value')
            placemark['advisory_number'] = self.get_element_text(extended_data_el, ns + 'Data[@name="advisoryNum"]' + ns + 'value')
            placemark['direction'] = self.get_element_int(extended_data_el, ns + 'Data[@name="tcDir"]' + ns + 'value')
            placemark['dvlp'] = self.get_element_text(extended_data_el, ns + 'Data[@name="TcDvlp"]' + ns + 'value')
            placemark['movement'] = self.get_element_text(extended_data_el, ns + 'Data[@name="movement"]' + ns + 'value')
            placemark['timezone'] = self.get_element_text(extended_data_el, ns + 'Data[@name="timezone"]' + ns + 'value')
            placemark['wind_gust'] = self.get_element_text(extended_data_el, ns + 'Data[@name="wndGust"]' + ns + 'value')
            placemark['pressure'] = self.get_element_float(extended_data_el, ns + 'Data[@name="mslp"]' + ns + 'value')
            placemark['tau'] = self.get_element_text(extended_data_el, ns + 'Data[@name="tau"]' + ns + 'value')
            placemark['max_wind'] = self.get_element_text(extended_data_el, ns + 'Data[@name="maxWnd"]' + ns + 'value')

            advisory_dt_str = self.get_element_text(extended_data_el, ns + 'Data[@name="advisoryDate"]' + ns + 'value')
            dt_obj = datetime.datetime.strptime(advisory_dt_str, '%y%m%d/%H%M %Z')
            placemark['advisory_datetime'] = dt_obj.replace(tzinfo=pytz.utc).isoformat()

            # Add it to the list
            placemarks.append(placemark)

        # Return the array
        return placemarks

    def linestring_feature_for_points(self, points_array):
        points = [(d['longitude'], d['latitude']) for d in points_array]
        feature = {
            'type': 'Feature',
            'properties': {},
            'geometry': {
                'type': 'LineString',
                'coordinates': points,
            }
        }
        return feature

    def create_polygon_feature(self, points, props_dict):
        feature = {
            'type': 'Feature',
            'properties': props_dict,
            'geometry': {
                'type': 'Polygon',
                'coordinates': (points,)
            }
        }
        if points is not None:
            return feature
        else:
            return None

    def create_linestring_feature(self, points, props_dict):
        feature = {
            'type': 'Feature',
            'properties': props_dict,
            'geometry': {
                'type': 'LineString',
                'coordinates': points,
            }
        }
        return feature

    def create_point_feature(self, longitude, latitude, props_dict):
        return {
            'type': "Feature",
            'properties': props_dict,
            'geometry': {
                'type': 'Point',
                'coordinates': (longitude, latitude),
            }
        }

    def point_features_for_points(self, points_array):
        points = []
        for point_dict in points_array:
             points.append({
                'type': "Feature",
                'properties': point_dict,
                'geometry': {
                    'type': 'Point',
                    'coordinates': (point_dict['longitude'], point_dict['latitude']),
                }
            })
        return points
    
    def replace_timezone_code_with_utc(self, dt_str):
        if 'AST' in dt_str:
            dt_str = dt_str.replace('AST', 'UTC-4')
        elif 'EST' in dt_str:
            dt_str = dt_str.replace('EST', 'UTC-5')
        elif 'EDT' in dt_str:
            dt_str = dt_str.replace('EDT', 'UTC-4')
        elif 'CST' in dt_str:
            dt_str = dt_str.replace('CST', 'UTC-6')
        elif 'CDT' in dt_str:
            dt_str = dt_str.replace('CDT', 'UTC-5')
        elif 'MST' in dt_str:
            dt_str = dt_str.replace('MST', 'UTC-7')
        elif 'MDT' in dt_str:
            dt_str = dt_str.replace('MDT', 'UTC-6')
        elif 'PST' in dt_str:
            dt_str = dt_str.replace('PST', 'UTC-8')
        elif 'PDT' in dt_str:
            dt_str = dt_str.replace('PDT', 'UTC-7')
        elif 'AKST' in dt_str:
            dt_str = dt_str.replace('AKST', 'UTC-9')
        elif 'AKDT' in dt_str:
            dt_str = dt_str.replace('AKDT', 'UTC-8')
        elif 'HST' in dt_str:
            dt_str = dt_str.replace('EDT', 'UTC-10')
        elif 'HAST' in dt_str:
            dt_str = dt_str.replace('EDT', 'UTC-10')
        elif 'HADT' in dt_str:
            dt_str = dt_str.replace('EDT', 'UTC-9')
        elif 'SST' in dt_str:
            dt_str = dt_str.replace('SST', 'UTC-11')
        elif 'SDT' in dt_str:
            dt_str = dt_str.replace('SDT', 'UTC-10')
        elif 'CHST' in dt_str:
            dt_str = dt_str.replace('CHST', 'UTC+10')
        return dt_str

if __name__ == "__main__":
    pass