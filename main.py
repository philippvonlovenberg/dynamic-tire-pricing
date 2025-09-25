# coding: utf8

from config import GRAPHHOPPER_API_KEY

import requests
import json
import math
from zipfile import ZipFile
import os
import pandas as pd
import matplotlib.pyplot as plt
import mplleaflet
import time


class Coordinate:
    ################################################################################################################
    # Die Coordinate-Klasse soll die Informationen und Zustände von und zu geografischen Punkten Normen
    # Außerdem wird mit "calc_distance_to_other_point" eine Methode Angeboten, die den Abstand zu einem anderen
    # Coordinate-Objekt in km berechnen kann

    # Beim Initialisieren eines Coordinate-Objekts müssen mindestens Breiten- und Längengrad angegeben werden

    # Weitere Werte, die ein Coordinate speichern kann, sind:
    # - Informationen bzgl. der Straßenqualität. Dabei werden unterschieden:
    #       - Rohes rating ("rating_raw"): Entspricht dem Wert aus der Datenquelle, z.B. der smartroadsence-D.B.
    #       - Quelle des Rohen Ratings ("rating_raw_data_source"): Nötig für Standardisierung der Daten
    #       - Standardisiertes rating ("rating_standardised"): Standardisiertes Rating von 1(bestm.)-7(am schlechtestm.)
    # - Informationen bzgl. "Snapping" (siehe Dokumentation zu snap_ratings_to_route)
    #       - Wurden die Straßenzustände gesnapped? ("rating_is_snapped)
    #       - Entfernung der Coordinate, deren Rating übernommen wurde ("snapping_distance")
    #       - Koordinaten der Coordinate, deren Rating übernommen wurde [lat, long]
    #
    #################################################################################################################

    def __init__(self, lat, long, rating_raw=-1.0, rating_raw_data_source="-1", rating_standardised=-1.0,
                 rating_is_snapped=False, snapping_distance=-1, snapped_rating_coordinates=None):

        self.lat = float(lat)
        self.long = float(long)

        self.rating_raw = float(rating_raw)
        self.rating_raw_data_source = str(rating_raw_data_source)
        self.rating_standardised = float(rating_standardised)

        self.rating_is_snapped = bool(rating_is_snapped)
        self.snapping_distance = float(snapping_distance)
        self.snapped_rating_coordinates = snapped_rating_coordinates

        # Es soll nicht möglich sein, unstandardisierte Rohdaten zu hinterlegen, ohne die Datenquelle anzugeben
        if bool(rating_raw != -1) and bool(rating_raw_data_source == str(-1)):
            raise AttributeError("raw ratings require data source")

        # Wenn angegeben wird, dass das Rating der Coordinate "angesnapped" wurde, also 'eigentlich' von einer anderen
        # nahen Coordinate stammt, dann muss auch die Distanz dieser Punkte zueinander angegeben werden
        if rating_is_snapped and bool(snapping_distance == float(-1)):
            raise AttributeError("raw ratings require data source")

    def get_coordinates(self):
        return [self.lat, self.long]

    def get_rating(self, standardised_wanted=True, raw_with_source_wanted=False):
        if standardised_wanted:
            if self.rating_standardised != -1:
                return self.rating_standardised
            elif bool(self.rating_raw != -1) & bool(self.rating_raw_data_source != str(-1)):
                return standardize(self).get_rating()
            else:
                raise AttributeError('not possible, required values missing')
        else:
            if raw_with_source_wanted:
                return self.rating_raw, self.rating_raw_data_source
            else:
                return self.rating_raw

    def get_values(self):
        return [self.lat, self.long], [self.rating_raw, self.rating_raw_data_source, self.rating_standardised], \
               [self.rating_is_snapped, self.snapping_distance, self.snapped_rating_coordinates]

    def get_snapping_info(self):
        return self.rating_is_snapped, self.snapping_distance, self.snapped_rating_coordinates

    def set_snapping_info(self, snapping_distance, snapped_rating_coordinates, rating_is_snapped=True, ):
        self.rating_is_snapped = bool(rating_is_snapped)
        self.snapping_distance = float(snapping_distance)
        self.snapped_rating_coordinates = snapped_rating_coordinates

    def set_rating(self, rating_standardised, rating_raw=None, rating_raw_data_source=None):
        if bool(rating_raw is None) and bool(rating_raw_data_source is None):
            self.rating_standardised = rating_standardised
        else:
            self.rating_standardised = rating_standardised
            self.rating_raw = rating_raw
            self.rating_raw_data_source = rating_raw_data_source

    def calc_distance_to_other_point(self, point_b):
        # point_b ist auch ein Objekt der Coordinate Klasse
        lat2 = point_b.get_coordinates()[0]
        long2 = point_b.get_coordinates()[1]
        lat1 = self.lat
        long1 = self.long

        # Berechnen der Distanz zwischen den Breitengraden
        delta_lat = lat1 - lat2
        distance_y = 111.3 * delta_lat

        # Berechnen der Distanz zwischen den Längengraden
        conversion_factor_delta_longitude_to_km = math.cos(math.radians(lat1)) * 111.3
        delta_long = long1 - long2
        distance_x = delta_long * conversion_factor_delta_longitude_to_km

        # Satz des Pythagoras:
        # a^2 + b^2 = c^2
        distance = math.sqrt(distance_x * distance_x + distance_y * distance_y)
        return distance


# Abfragen:


def give_rated_area_ql(point_a=Coordinate(-90, -180), point_b=Coordinate(90, 180)):
    ################################################################################################################
    # Eingabeparameter:     optional: Zwei beliebige Coordinate-Objekte
    #                       Werden diese nicht gegeben, so liefert die Methode alle Datensätze zurück
    # Rückgabe:             Liste von Coordinate-Objekten mit rohen Ratings und Datenquelle 'ql'

    # Beschreibung:
    # Die Methode liefert die Datensätze aus der Queensland-Datenbank in einem von zwei Punkten aufgespannten Rechteck
    # zurück.
    # Dazu werden der maximale und minimale Längen- & Breitengrad ermittelt, und dann über eine SQL-Abfrage
    # über die API abgefragt. SQL ist hier nötig, da es über die einfachere Schnittstelle nicht möglich ist,
    # Alle Koordinaten in einem bestimmten Bereich anzufordern.
    # Die Antwort wird danach nach den benötigten Informationen gefiltert und für jeden Eintrag in der Antwort
    # ein Coordinate Objekt erstellt, welches in die coordinate_list hinzugefügt wird, solange die IRIRoughness
    # über 0 ist. Einträge mit unplausiblen Werten wie IRIRoughness = -99 werden also verworfen.
    #
    # Es kann zwischen zwei Datensätzen gewählt werden, wofür nur die ressource_id ausgetauscht werden muss.
    # Die Wahl fiel hier auf die 100m-Variante, da überproportional viel mehr Datensätze zur Verfügung stehen und
    # zusätzlich die Genauigkeit steigt.
    ################################################################################################################

    url = "https://www.data.qld.gov.au/api/3/action/datastore_search_sql"
    resource_id = "d618ce2e-7d29-4569-97bd-d97bd5831924"
    # resource_id for 1km: 66457d52-79c8-46d6-9e95-d356527a71e5
    # resource_id for 100m: d618ce2e-7d29-4569-97bd-d97bd5831924

    lat_from = min(point_a.get_coordinates()[0], point_b.get_coordinates()[0])
    lat_to = max(point_a.get_coordinates()[0], point_b.get_coordinates()[0])
    long_to = max(point_a.get_coordinates()[1], point_b.get_coordinates()[1])
    long_from = min(point_a.get_coordinates()[1], point_b.get_coordinates()[1])

    sql_request = 'SELECT "Latitude","Longitude","IRIRoughness" FROM "{}" ' \
                  'WHERE "Latitude" BETWEEN {} AND {} ' \
                  'AND "Longitude" BETWEEN {} AND {};' \
        .format(resource_id, lat_from, lat_to, long_from, long_to)

    response = requests.get(url + "?sql=" + sql_request)
    response_filtered = response.json()["result"]["records"]

    coordinate_list = []
    for c in response_filtered:
        if float(c["IRIRoughness"]) > 0:
            new_coordinate = Coordinate(c["Latitude"], c["Longitude"], c["IRIRoughness"], "ql")
            coordinate_list.append(new_coordinate)

    return coordinate_list


def update_database_srs():
    ################################################################################################################
    # Lädt die gesamte Datenbank von der SmartRoadSence Website herunter, entpackt die Zip-Datei und verstaut die
    # entpackte csv im Ordner interal als database_srs.csv
    # Nötig geworden, da die API von SmartRoadSence nicht mehr funktioniert
    ################################################################################################################

    # Download file
    r = requests.get('http://www.smartroadsense.it/open_data.zip', allow_redirects=True)
    temp_file = open("internal/temp", 'wb')
    temp_file.write(r.content)

    # extract file
    ZipFile("internal/temp", 'r').extractall()
    os.remove("internal/temp")
    os.rename("open_data.csv", "internal/database_srs.csv")


def give_rated_area_srs(point_a: Coordinate = Coordinate(-90, -180), point_b: Coordinate = Coordinate(90, 180)):
    ################################################################################################################
    # Eingabeparameter:     optional: Zwei beliebige Coordinate-Objekte
    #                       Werden diese nicht gegeben, so liefert die Methode alle Datensätze zurück
    # Rückgabe:             Liste von Coordinate-Objekten mit rohen Ratings und Datenquelle 'srs'
    #
    # Beschreibung:
    # Die Methode liefert die Datensätze aus der unter database-srs.csv gespeicherten SmartRoadSence-Datenbank in einem
    # von zwei Punkten aufgespannten Rechteck zurück.
    # Dazu wird zunächst der maximale und minimale Längen- & Breitengrad ermittelt.
    # Dann wird versucht, die database_srs.csv im Ordner internal zu öffnen.
    # Ist diese nicht vorhanden oder kann nicht geöffnet werden, wird der resultierende IOError behandelt und über
    # den Aufruf von update_database_srs eine neue csv erstellt. Danach wird fortgefahren
    # Nun werden die Daten in die variable data_filtered gespeichert, die zwischen den max. und mins. bei Breiten- &
    # Längengrad liegen
    #
    # Für jeden Eintrag in der Antwort wird nun ein Coordinate Objekt erstellt, welches in die coordinate_list
    # hinzugefügt wird, solange die ppe größer gleich 0.0000001 ist.
    # Einträge mit unplausiblen Werten wie ppe = 0 werden also verworfen.
    ################################################################################################################

    lat_from = min(point_a.get_coordinates()[0], point_b.get_coordinates()[0])
    lat_to = max(point_a.get_coordinates()[0], point_b.get_coordinates()[0])
    long_to = max(point_a.get_coordinates()[1], point_b.get_coordinates()[1])
    long_from = min(point_a.get_coordinates()[1], point_b.get_coordinates()[1])

    try:
        data = pd.read_csv("internal/database_srs.csv")[["latitude", "longitude", "ppe"]]
    except IOError:
        update_database_srs()
        data = pd.read_csv("internal/database_srs.csv")[["latitude", "longitude", "ppe"]]

    data_filtered = data[(data.latitude >= lat_from) &
                         (data.latitude <= lat_to) &
                         (data.longitude >= long_from) &
                         (data.longitude <= long_to)]

    coordinate_list = []
    for c in data_filtered.values:
        if c[2] < 0.0000001:
            pass
        else:
            new_coordinate = Coordinate(c[0], c[1], c[2], "srs")
            coordinate_list.append(new_coordinate)
    return coordinate_list


def give_coordinate_for_location(location):
    ################################################################################################################
    # Eingabeparameter:     Name eines Ortes, als Datentyp wird str angenommen
    # Rückgabe:             Coordinte Objekt, mit dem zu den Ort gehörenden Breiten- und Längengrad
    #
    # Beschreibung:
    # Diese Methode fragt für einen Ortsnamen die dazugehörigen Koordinaten über die GraphHopper API ab ('geocoding')
    # unter 'parameters' kann der API-Key geändert werden
    ################################################################################################################

    parameters = {
        "key": GRAPHHOPPER_API_KEY,
        "q": str(location),
        "locale": "en",
        "limit": "1"
    }

    request = requests.get("https://graphhopper.com/api/1/geocode", params=parameters)

    lat = request.json()["hits"][0]["point"]["lat"]
    long = request.json()["hits"][0]["point"]["lng"]

    return Coordinate(lat, long)


def find_path(start: Coordinate, destination: Coordinate, maximum_point_distance=0.11, splitter=380):
    ################################################################################################################
    # Eingabeparameter:     2x Coordinate-Objekte (Start- und Zielpunkt)
    #                       optional: Maximaler Abstand, den zwei Wegpunkte zueinander haben dürfen
    #                       splitter: s. Beschreibung
    # Rückgabe:             Liste, welche weitere Listen mit Coordinate-Objekten enthält.
    #
    # Beschreibung:
    # Diese Methode besteht aus drei Teilen

    # - Teil 1: Abfrage der Routendaten über die Graphhopper API
    #       Hier werden die hinterlegten Breiten- und Längengrade von Start und Zielpunkt genommen und die Route abgefragt
    #       Der API-Key kann unter 'parameters' geändert werden
    #       Falls keine Route gefunden werden kann, tritt beim Filtern der Ergebnisse ein Fehler auf, da
    #       eine nicht vorhandene Route natürlich auch keine "points" und "coordinates" enthält.
    #       Falls das passiert wird ein KeyError ausgelöst, der dem Nutzer angibt, dass keine Route gefunden wurde.
    #       Sonst werden für jedes Ergebnis ein Coordinate-Objekt erstellt und der Liste 'coordinates' hinzugefügt.
    #
    # - Teil 2: Zwischenpunkte hinzufügen falls nötig und gewollt
    #       Falls 'maximum_point_distance' = 0, None oder False in die Methode gegeben wurde, passiert in diesem Schritt
    #       nichts.
    #       Sonst wird hier so lange die Methode 'interpoint' aufgerufen, bis der maximale Abstand zwischen zwei
    #       Wegpunkten kleiner ist als 'maximum_point_distance'.
    #
    # - Teil 3: Aufsplitten des paths in Sektionen
    #       Falls 'splitter' = None in die Methode gegeben wurde, ist 'path' das einzige Routenstück und wird auch
    #       so (als einzelne Liste in einer Liste(('[path]')zurückgegeben
    #       Sonst wird 'path', dass ja eine Liste von Coordinate-Objekten beinhaltet, die die Route bilden, in
    #       mehrere Teilsektionen unterteilt. Das dient dazu, dass die Methoden, die später mit der Rückgabe aus dieser
    #       Methode rechnen müssen, nicht mit zu großen Strecken gleichzeitig rechnen müssen, sondern Stückchen nach
    #       Stückchen berechnen können. (v.a. da bei zunehmender auf einmal verarbeiteter Streckenlänge die Berechnungs-
    #       dauer bzw. der -aufwand ab einer gewissen Länge exponentiell steigt).
    #       Der Splitter bezeichnet die angestrebte Anzahl der Coordinate-Objekte pro Teilstück
    #       Falls die Gesamtzahl der Coordinates geteilt durch den Splitter nicht aufgeht, wo wird das sonst letzte
    #       Teilstück dem vorletzten hinzugefügt.
    #       Zur Veranschaulichung übertragen auf ints gibt dieses Vorgehen also heraus:
    #       splitter = 3
    #       x = [1, 5, 2, 3, 5, 6, 2, 6, 9, 200, 2]
    #           ==> y = [[1, 5, 2], [3, 5, 6], [2, 6, 9, 200, 2]]
    #       Falls gesplittet wurde werden diese Teilstücke nun in einer Liste zurückgegeben.

    ################################################################################################################

    # Teil 1: Abfrage der Routendaten über die Graphhopper API
    startpoint = "{}, {}".format(start.get_coordinates()[0], start.get_coordinates()[1])
    endpoint = "{}, {}".format(destination.get_coordinates()[0], destination.get_coordinates()[1])

    parameters = {
        "key": GRAPHHOPPER_API_KEY,
        "type": "json",
        "vehicle": "car",
        "points_encoded": "false",
        "instructions": "false"
    }
    url = "https://graphhopper.com/api/1/route"
    url_with_points = "{}?point={}&point={}".format(url, startpoint, endpoint)
    response = requests.get(url_with_points, params=parameters)

    try:
        response_filtered = response.json()["paths"][0]["points"]["coordinates"]

        coordinates = []

        for c in response_filtered:
            coordinates.append(Coordinate(c[1], c[0]))

        # Teil 2: Zwischenpunkte hinzufügen falls nötig und gewollt

        if maximum_point_distance is None or maximum_point_distance is False or maximum_point_distance == 0:
            path = coordinates.copy

        else:
            all_distances_above_min = False
            path = coordinates.copy()
            while all_distances_above_min is False:
                temp_1 = interpoint(path, maximum_point_distance)
                path = temp_1
                i = 0
                all_distances_above_min = True
                while i < (len(path) - 1):
                    if path[i].calc_distance_to_other_point(path[i + 1]) > maximum_point_distance:
                        all_distances_above_min = False
                    i = i + 1

        # Teil 3: Aufsplitten des paths in Sektionen

        if splitter is None:
            return [path]
        else:
            splitted = []
            line = []
            counter_in_line = 0
            line_count = 0
            for i in path:
                if counter_in_line < splitter:
                    line.append(i)
                    counter_in_line += 1

                else:
                    counter_in_line = 0
                    line_count += 1
                    splitted.append(line)
                    line = []

                    line.append(i)
                    counter_in_line += 1
                    line_count += 1

            if len(splitted) < len(path) / splitter:
                if len(line) == splitter:
                    splitted.append(line)
                else:
                    if len(splitted) != 0:
                        for e in line:
                            splitted[-1].append(e)
                    else:
                        splitted.append(line)
                line = []

            return splitted
    # zu Teil 1:
    except KeyError:
        raise KeyError("Zwischen {} und {} konnte keine Route gefunden werden, Eingabe überprüfen"
                       .format([startpoint], [endpoint]))


# Verarbeitung


def update_database_standardizer():
    ################################################################################################################
    # Beschreibung:

    # Die Methode updated die Datei 'database_standardizer.csv' im Ordner internal.
    # Diese Datei enthält statistische Informationen über die Daten in den Datensätzen über die Straßenqualität,
    # welche von der Methode 'standardized' genutzt werden, um die Daten vergleichbar zu machen (s. dort für weitere
    # Erklärungen)
    #
    # Zunächst werden dazu die gesamten Datensätze in Form einer List von Coordinate-Objekten abgerufen und gespeichert.
    # Nun wird für jede dieser Coordinate-Objekte das Rating ausgelesen und in neue Listen abgelegt.
    # Diese Listen werden nun ausgewertet und die Quantile 0.4, 0.8, 0.9, 0.95, 0.98 und 0.99 werden ermittelt
    # Diese Werte orientieren sich an der Einteilung von smartroadsence. Die Legende auf der Website unterteilt in
    # 6 Kategorien:
    #   - Grün = ppe > 0.3
    #   - Gelb = 0.3 > ppe > 0.5
    #   - Orange = 0.5 > ppe > 0.7
    #   - Hellrot = 0.7 > ppe > 1.0
    #   - Dunkelrot = 1.0 > ppe > 1.7
    #   - Braun = 1.7 > ppe
    # Nun habe ich ermittelt, welches Quantile diesen Trennwerten entspricht. Dabei kam ich zum Ergebnis:
    # ppe 0.3  -> 80%
    # ppe 0.5  -> 90%
    # ppe 0.7  -> 95%
    # ppe 1.0  -> 98%
    # ppe 1.7  -> >99%
    # Bei 80% der Straßen nicht mehr weiter zu unterscheiden, ist zu ungenau. D.h. weitere Unterteilung.
    # Quantile 0.4 / 40% entspricht ca. ppe =  0.1
    #
    # Quantiles für beide Datensätze werden dann noch formatiert und in 'database_standardizer.csv' im
    # Ordner internal gespeichert.

    # Eingangsparameter:    keine
    # Rückgabe:             keine
    ################################################################################################################
    srs_coordinates = give_rated_area_srs()
    ql_coordinates = give_rated_area_ql()
    srs_raw_ratings = []
    ql_raw_ratings = []

    for coordinate in srs_coordinates:
        srs_raw_ratings.append(coordinate.get_rating(standardised_wanted=False))
    for coordinate in ql_coordinates:
        ql_raw_ratings.append(coordinate.get_rating(standardised_wanted=False))

    srs_quantiles = []
    ql_quantiles = []

    for i in [0.4, 0.8, 0.9, 0.95, 0.98, 0.99]:
        srs_quantiles.append(pd.Series(srs_raw_ratings).quantile(i))
        ql_quantiles.append(pd.Series(ql_raw_ratings).quantile(i))
        plt.axvline(pd.Series(ql_raw_ratings).quantile(i))

    csv = pd.DataFrame(data={"quantile nr": range(1, 7), "srs_quantiles": srs_quantiles, "ql_quantiles": ql_quantiles})
    csv.to_csv("internal/database_standardizer.csv")


def interpoint(coordinates, maximum_point_distance):
    ################################################################################################################
    # Eingangsparameter:    Liste von Koordinaten
    #                       maximaler Abstand, den zwei Wegpunkte haben dürfen
    # Rückgabe:             Liste von Koordinaten, bei denen bei zu weitem Abstand zwischen zwei Coordinate-Objekten
    #                       genau jeweils ein Punkt in der Mitte eingesetzt wurden
    #
    # Beschreibung:
    # Diese Methode geht ermittelt die Abstände von jedem Punkt in der Liste ('coordinates') zum jeweils nächsten.
    # Außerdem wird die eingegebene Coordinate-Liste kopiert
    # Anschließend wird jeder dieser Distanzen geprüft, ob die Distanz länger ist als die maximal zulässige.
    # Ist dies der Fall, so wird der kopierten Coordinate-Liste an der passenden Stelle eine neue Koordinate
    # hinzugefügt, welche in der Mitte zwischen beiden Punkten ist.
    # Der 'offset_counter' zählt dazu mit, wie viele Koordinaten schon eingefügt wurden (+1), um die passende Stelle
    # zum Einfügen in der kopierten Liste zu finden
    ################################################################################################################

    distances = []
    i = 0
    while i < (len(coordinates) - 1):
        d = coordinates[i].calc_distance_to_other_point(coordinates[i + 1])
        distances.append(d)
        i = i + 1

    new_coordinates = coordinates.copy()
    offset_counter = 1
    for i in range(0, len(distances)):
        if distances[i] > maximum_point_distance:
            nc_len = (coordinates[i].get_coordinates()[0] + coordinates[i + 1].get_coordinates()[0]) / 2
            nc_long = (coordinates[i].get_coordinates()[1] + coordinates[i + 1].get_coordinates()[1]) / 2
            new_coordinate = Coordinate(nc_len, nc_long)
            new_coordinates.insert(i + offset_counter, new_coordinate)
            offset_counter = offset_counter + 1

    return new_coordinates


def give_ratings_near_path(path, puffer_wanted=True):
    ################################################################################################################
    # Eingangsparameter:    Liste von Koordinaten, die eine Route bilden
    #                       optional: Sicherheitspuffer gewollt?
    # Rückgabe:             Gibt ein Tupel zurück, dass zwei Infos enthält:
    #                           - Eine Liste von Coordinate-Objekten mit rohen ratings, die aus den Datenbanken von
    #                           SmartRoadSence und Queensland abgefragt wurden und in der Nähe der Route liegen
    #                           - Eine Liste von Rectangle-Objekten (aus matplotlib.pyplot), die später falls gewünscht
    #                           geplottet werden kann

    # Beschreibung:
    # Diese Methode liefert für eine Route grob ermittelte nahegelegene Ratings sowie Informationen zur grafischen
    # Darstellung des Bereichs, aus dem diese Ratings entnommen wurden.
    #
    # Die Methode besteht aus 3 Schritten:
    # - Schritt 1: Feststellen der nördlichsten, westlichsten etc. Punkte der Route:
    #       Es wird der minimale und maximale Längen- sowie Breitengrad ermittelt, der in der Route vorkommt
    #       Es wird ein schwarzes Rechteck erstellt, dass diese Werte grafisch darstellt. Das Rechteck schließt also
    #       genau alle Punkte der Route in der grafischen Darstellung ein.
    #
    # - Schritt 2: Sicherheitsabstand in km in Grad umrechnen und aufschlagen
    #       Falls gewollt, wird noch ein Sicherheitsabstand zu allen Seiten aufgeschlagen.
    #       Danach wird ein neues (rotes) Rechteck erstellt, dass diese neue (größere) Fläche zeigt
    #       Standardmäßig eingestellt ist hier ein Sicherheitsabstand von 1.5km
    #
    # - Schritt 3: Straßenzustände in Rechteck abfragen
    #       Nun werden alle Punkte, die in dem entsprechenden Rechteck liegen, abgefragt und in einer Liste gesammelt.
    #       Diese Liste wird dann zurückgegeben
    ################################################################################################################

    # 1. Schritt: Feststellen der nördlichsten, westlichsten etc. Punkte der Route

    point_list = []
    for c in path:
        point_list.append(c.get_coordinates())
    point_data_frame = pd.DataFrame(data=point_list, columns=["lat", "long"])

    lat1, long1 = point_data_frame.min()[0], point_data_frame.min()[1]
    lat2, long2 = point_data_frame.max()[0], point_data_frame.max()[1]

    rectangles = [plt.Rectangle((long1, lat1), abs(long2 - long1), abs(lat1 - lat2), ec="black")]

    # 2. Schritt: Sicherheitsabstand in km in Grad umrechnen und aufschlagen

    if puffer_wanted:
        safety_km = 1.5
        safety_lat = safety_km / 111.3
        safety_long = safety_km / (math.cos(math.radians(lat1)) * 111.3)
        lat1 = lat1 - safety_lat
        lat2 = lat2 + safety_lat
        long1 = long1 - safety_long
        long2 = long2 + safety_long

        rectangles.append(plt.Rectangle((long1, lat1), abs(long2 - long1), abs(lat1 - lat2), ec="red"))

    # Schritt 3: Straßenzustände in Großem Rechteck abfragen

    point_a, point_b = Coordinate(lat1, long1), Coordinate(lat2, long2)

    all_rating_coordinates_srs = give_rated_area_srs(point_a, point_b)
    all_rating_coordinates_ql = give_rated_area_ql(point_a, point_b)
    all_rating_coordinates = all_rating_coordinates_srs + all_rating_coordinates_ql

    return all_rating_coordinates, rectangles


def standardize(coordinate_to_standardize):
    ################################################################################################################
    # Eingangsparameter:    Ein einzelnes Coordinate-Objekt, welches bisher nur das rohe Rating und die Quelle der
    #                       Rohdaten gespeichert hat, aber im Normalfall noch keine standardisierte Bewertung
    #
    # Rückgabe:             Das Coordinate-Objekt mit hinterlegtem standarsiertem Rating
    #
    # Beschreibung:
    # Diese Funktion soll aus dem 'rohen' Rating (also die Bewertung der Straßenqualität, so wie sie bei srs / ql gov
    # angegeben ist) ein standardisiertes Rating erstellen, welches unabhängig von der Datenquelle mit einander
    # vergleichbar ist. Dabei wird mit 'Quantiles' gearbeitet, um in ein standardisiertes Rating mit insgesamt 7 Niveaus
    # zu unterteilen.
    # Level 1: Die besten 40%               (Werte gehören also zu den top 40%)
    # Level 2: Die darauf folgenden 40%     (Werte gehören also zu den top 80%)
    # Level 3: Die darauf folgenden 10%     (Werte gehören also zu den top 90%)
    # Level 4: Die darauf folgenden 5%      (Werte gehören also zu den top 95%)
    # Level 5: Die darauf folgenden 3%      (Werte gehören also zu den top 98%)
    # Level 6: Das darauf folgende 1%       (Werte gehören also zu den top 99%)
    # Level 7: Das schlechteste 1%
    # Diese Einteilung orientiert sich grob an der von SmartRoadSence (s. Dokumentation zu 'update_database_normalizer')

    # Zunächst liest diese Funktion das rohe Rating und die Quelle dieses rohen Ratings aus dem Coordinate-Objekt aus.
    # Dann wird versucht, die 'database_standardizer.csv' im internal Ordner zu öffen. Falls das nicht gelingt,
    # wird 'update_database_standardizer' angefordert und der Einleseversuch dann widerholt
    #
    # Nach dem Einlesen wird geprüft, was die Quelle des rohen Ratings ist bzw. ob diese überhaupt angegeben ist.
    # Die entsprechende Spalte aus 'database_standardizer.csv' wird ausgelesen (falls Datenquelle angegeben war) und
    # in ein 'pandas.DataFrame' mit der quantile nr gespeichert
    # Dann wird in dieses Dataframe eine neue Zeile eingefügt, die das zu standardisierende Rating und als 'quantile nr'
    # -1 enthält. Dann wird die Liste nach Rating sortiert und geschaut, an welcher Stelle die Hinzugefügte Zeile mit
    # quantile nr = -1 ist.
    #
    # Beispiel anhand von queensland-Daten:
    #
    # (index),  quantile nr,    ql_quantiles
    # 0,        1,              2.43
    # 1,        2,              3.49
    # 2,        3,              4.03
    # 3,        -1,             4.3         <====
    # 4,        4,              4.53
    # 5,        5,              5.17
    # 6,        6,              5.63

    # => -1 wurde an Stelle 3 gefunden => Rating 4 (Da schlechter als Grenzwert für Rating 3)

    ################################################################################################################
    raw_rating, data_origin = \
        coordinate_to_standardize.get_rating(standardised_wanted=False, raw_with_source_wanted=True)

    try:
        standardize_values = pd.read_csv('internal/database_standardizer.csv')[
            ["quantile nr", "srs_quantiles", "ql_quantiles"]]
    except IOError:
        update_database_standardizer()
        standardize_values = pd.read_csv('internal/database_standardizer.csv')[
            ["quantile nr", "srs_quantiles", "ql_quantiles"]]

    if data_origin == "srs":
        name_of_data_row = "srs_quantiles"
    elif data_origin == "ql":
        name_of_data_row = "ql_quantiles"
    else:
        raise AttributeError('data origin is needed')

    quantiles = standardize_values[["quantile nr", name_of_data_row]]

    quantiles_value_appended = (
        quantiles.append({"quantile nr": float("-1"), name_of_data_row: float(raw_rating)}, ignore_index=True)
            .sort_values(by=name_of_data_row)
            .reset_index(drop=True))

    rating = quantiles_value_appended[(quantiles_value_appended["quantile nr"] == -1)].index[0] + 1

    coordinate_to_standardize.set_rating(rating)

    return coordinate_to_standardize


def snap_ratings_to_route(path_coordinate_list):
    ################################################################################################################
    # Eingangsparameter:        Liste an Coordinate-Objekten, die eine Route bilden
    # Ausgangsparameter:        Tupel, welches enthält:
    #                               - Liste an Coordinate-Objekten, die eine Route bilden und die dazugehörige Straßen-
    #                               qualität sowie Details zum Ablauf des Vorgangs beinhalten
    #                               - Der Durchschnitt der Distanz von den Punkten der Route zu dem jeweils nächsten
    #                               gefundenen Rating
    #                               - Die maximale Distanz von den Punkten der Route zu dem jeweils nächsten
    #                               gefundenen Rating
    #                               - Eine Liste von Rectangle-Objekten (matplotlib.pyplot), die von der Funktion
    #                               give_ratings_near_path weitergegeben wird
    #
    # Diese Methode sucht für jeden Punkt einer Route das jeweils nächste Rating in einem Bereich und fügt die Rating-
    # informationen sowie Informationen über den Vorgang in diese Wegpunkte (Coordinate-Objekte) ein.
    # - Schritt 1: Nahe Ratings abfragen und in Variable speichern
    # - Schritt 2: Für jeden Punkt auf der Route das nächste Rating finden und Informationen in Punkt speichern
    #               Dazu wird für jeden Punkt r auf der Route jeder Punkt c aus den nahen Ratings auf seine Nähe zu
    #               r geprüft, und dann für r die Daten des nächsten ermittelten Ratings c gespeichert sowie weitere
    #               Informationen hinterlegt (die Info, von welchem anderen Coordinate-Objekt das Rating eigentlich
    #               stammt sowie die Distanz zu diesem)
    # - Wurden alle Routenpunkte durchlaufen, wird u.a. die veränderte Liste dieser Routen-Coordinate-Objekte zurück-
    # gegeben
    ################################################################################################################

    # Schritt 1: Nahe Ratings abfragen und in Variable speichern
    give_ratings_near_path_result = give_ratings_near_path(path_coordinate_list)
    rating_coordinates = give_ratings_near_path_result[0]

    # Schritt 2: Für jeden Punkt auf der Route das nächste Rating finden und Informationen in Punkt speichern

    distances = []
    for r in path_coordinate_list:
        closest = ()
        for c in rating_coordinates:
            distance = r.calc_distance_to_other_point(c)

            if closest == ():
                closest = (distance, c)
            elif closest[0] > distance:
                closest = (distance, c)

        closest_rating_standardised = closest[1].get_rating()
        closest_rating_raw = closest[1].get_rating(False)
        closest_rating_raw_data_source = closest[1].get_rating(False, True)[1]
        closest_rating_distance = closest[0]
        closest_rating_coordinate = closest[1].get_coordinates()
        r.set_snapping_info(closest_rating_distance, closest_rating_coordinate)
        r.set_rating(closest_rating_standardised, closest_rating_raw, closest_rating_raw_data_source)

        distances.append(closest_rating_distance)

    return path_coordinate_list, pd.Series(distances).mean(), pd.Series(distances).max(), \
           give_ratings_near_path_result[1]


def price_rated_route(rated_path, number_of_tires, tire_price=300, tire_best_range=75000, tire_worst_range=10000,
                      margin_percent=0.3):
    ################################################################################################################
    # Eingangsparameter:                - Liste an Coordinate-Objekten, die eine Route bilden
    #                                   - Anzahl der gemieteten Reifen
    #                                   - Einkaufspreis der Reifen für den Betreiber
    #                                   - Die Lebenserwartung eines Reifen unter bestmöglichen Umständen (also
    #                                   theoretisch ausschließlich Fahrt auf Rating 1 Straßen
    #                                   - Die Lebenserwartung eines Reifen unter schlechtestmöglichen Umständen
    #                                   (also theoretisch ausschließlich Fahrt auf Rating 7 Straßen)
    #                                   Beispiel: steinige Stein- und Schotterpisten mit heftigen Schlaglöchern
    #                                   - Die "marge" (stark vereinfacht) des Betreibers.
    #                                   0%/0.0 Würde bedeuten, die Abnutzung der Reifen deckt im Schnitt ungefähr die
    #                                   Wiederanschaffung
    #                                   - 30%/0.3 würde bedeuten, vom Endkundenpreis werden nur 70% benötigt, um den
    #                                   Wertverlust/Verschleiß der Reifen abzudecken. Die 30% bleiben zur freien Ver-
    #                                   wendung durch den Betreiber übrig.
    #
    # Rückgabe:                         - Tupel, welches drei Elemente enthält:
    #                                       - 1) Liste: Preisinformationen:
    #                                           - Endpreis für den Kunden
    #                                           - Endpreis für den Kunden ohne Marge
    #                                           - Endpreis für den Kunden ohne Marge pro Reifen
    #                                       - 2) Liste: Streckeninformationen:
    #                                           - Gewichtete Bewertung der Strecke von 1-7
    #                                           - Gesamtlänge der Strecke
    #                                       - 3) Lebenserwartung pro Reifen bei dieser Streckenbewertung/-qualität
    #
    #
    # Beschreibung:
    # Diese Funktion soll für eine Route ein Gesamtstreckenbewertung sowie einen darauf aufbauenden Preis berechnen.
    # Dazu wird eine einfache Preisfunktion genutzt, welche auf den eingegebenen Schätzungen über die Reifen beruht.
    #
    # Schritt 1: Nach Länge des Streckenabschnitts gewichtetes Durchschnittsrating ermitteln
    # Hier wird zunächst für alle Teilstrecken zwischen jeweils zwei aufeinanderfolgenden Punkten der Route ihrer Länge
    # und eine Bewertung erstellt. Die Bewertung der Strecke zwischen zwei Punkten erfolgt mit dem Mittelwert der
    # Bewertung beider Punkte. Nun wird die Streckenlänge mit dieser Bewertung multipliziert und 'total_weight' hinzu-
    # gefügt. Teilt man nach Durchlauf aller Teilstrecken 'total_weight' durch die Gesamtstrecke, so hat man eine
    # korrekt gewichtete Bewertung der Gesamtstrecke
    #
    # Schritt 2: Bepreisung nach average_rating und Streckenlänge
    # Nun wird sich die Frage gestellt, wie viele km die Reifen wohl bei dem angegebenen Rating halten werden.
    # Es ist bekannt, wie lange die Reifen bei Level 1 halten ('tire_best_range') und wie lange sie bei Level 7
    # halten ('tire_worst_range').
    # Nun wird einfach eine lineare Funktion aufgestellt, die aus diesen Werten ableiten kann, wie wohl die Lebens-
    # erwartung bei z.B. Level 5 ist. (Siehe z.B. im Funktionsplotter:
    # f(x) = 75000 - (x - 1) * (75000 - 10000) * (1 / 6)
    #
    # Nun wird die gefahrene Strecke durch diese ermittelte Lebenserwartung geteilt (= Wie viel % der Lebenserwartung
    # wurde durch diese Fahrt verbraucht) und das Ganze wird dann mit dem Preis pro Reifen multipliziert
    # z.B.: Halbe Lebenszeit abgefahren => Halber Preis eines Neureifens verschlissen
    # Nun wird noch die Anzahl der Reifen multipliziert und dann noch die Marge aufgeschlagen
    ################################################################################################################
    # Schritt 1: Nach Länge des Streckenabschnitts gewichtetes Durchschnittsrating ermitteln
    dist = []
    rating_sub_section = []
    i = 0
    while i < (len(rated_path) - 1):
        # Liste der Distanzen erstellen
        d = rated_path[i].calc_distance_to_other_point(rated_path[i + 1])
        dist.append(d)
        # Liste der Ratings der Teilstrecken erstellen
        r1 = rated_path[i].get_rating()
        r2 = rated_path[i + 1].get_rating()
        rating_sub_section.append((r1 + r2) / 2)
        i = i + 1
    temp_weight = 0.0
    total_distance = 0.0
    for i in range(0, len(dist)):
        temp_weight += dist[i] * rating_sub_section[i]
        total_distance += dist[i]
    average_rating = temp_weight / total_distance


    # Schritt 2: Bepreisung nach average_rating und Streckenlänge
    expected_lifetime_range_at_specific_rating = \
        tire_best_range - (average_rating - 1) * (tire_best_range - tire_worst_range) * (1 / 6)

    price_per_tire_without_margin = (total_distance / expected_lifetime_range_at_specific_rating) * tire_price
    price_without_margin = price_per_tire_without_margin * number_of_tires
    customer_end_price = price_without_margin / (1 - margin_percent)

    return ([customer_end_price, price_without_margin, price_per_tire_without_margin], [average_rating, total_distance],
            expected_lifetime_range_at_specific_rating)


# Ausgabe

def plot(snapped_path, rectangles=(), debug=False):
    ################################################################################################################
    # Eingangsparameter:     - Liste an Coordinate Objekten, die eine Route bilden und standardisiere Ratings enthalten
    #                        - optional: Liste o. Tupel an Rechtecken, die eingezeichnet werden sollen
    #                        (falls Debug=True)
    #                        - optional: debug (Ja/Nein)? (Ändert, was dem Nutzer alles angezeigt wird)
    #
    # Rückgabe:              keine
    #
    # Beschreibung:
    #
    # Zunächst werden die Routeninformationen so aufbereitet, dass eine Routenlinie damit geplottet werden kann.
    # 1) Diese Routenlinie wird dann als erstes geplottet (siehe Dokumentation matplotlib.pyplot)
    # 2) Nun werden Start und Endpunkt eingezeichnet, der Startpunkt mit einem blauen Punkt und der Endpunkt mit einem
    # blauen Kreuz
    # 3) Nun werden alle übrigen Punkte auf der Route mit einer von ihrem Rating abhängigen Farbe eingezeichnet. Diese
    # Punkte liegen dann auf der Linie aus Schritt 1). Die Farbkodierung kann in 'color_codes' geändert werden.
    #
    # 4) (wenn debug=True) Striche, die von jedem farbigen Wegpunkt zu dem Ort zeigen, von dem das Rating entnommen
    # wurde. Sind die Striche sehr kurz, bedeutet dass, dass direkt in der Nähe Informationen zur Straßenqualität
    # verfügbar waren.
    # 5) (wenn debug=True) Einzeichnen der Rechtecke
    # Alle übergebenen Rechtecke werden geplottet
    #
    # 6) mplleaflet.show() wird aufgerufen. mplleaflet nimmt alles, was in pyplot übergeben wurde, und überträgt es
    # auf eine interaktive Karte, die dann unter '_map.html' im Hauptverzeichnis des Programms auffindbar ist.
    # Die Karte sollte auch direkt geöffnet werden
    ################################################################################################################
    content = []
    route_lats = []
    route_longs = []
    for i in snapped_path:
        route_lats.append(i.get_coordinates()[0])
        route_longs.append(i.get_coordinates()[1])
        content.append(
            [(i.get_coordinates()[0], i.get_coordinates()[1]),
             (i.get_snapping_info()[2][0], i.get_snapping_info()[2][1]),
             i.get_rating()])

    # 1) Routenlinie plotten

    plt.plot(route_longs, route_lats, alpha=0.5)

    # 2) Start und Endpunkt plotten

    plt.plot(content[0][0][1], content[0][0][0], marker=".", color="b", markersize=20)
    plt.plot(content[-1][0][1], content[-1][0][0], 'bx', markersize=15)

    # 3) Einzelne Wegpunkte & Route mit passender Farbe plotten

    for p in content:
        rating = p[2]
        color_codes = {
            "1": (0 / 255, 255 / 255, 0),
            "2": (146 / 255, 219 / 255, 0),
            "3": (219 / 255, 219 / 255, 0),
            "4": (219 / 255, 183 / 255, 0),
            "5": (219 / 255, 120 / 255, 0),
            "6": (219 / 255, 69 / 255, 0),
            "7": (219 / 255, 0 / 255, 0)
        }
        plt.plot(p[0][1], p[0][0], color=color_codes[str(rating)], marker=".", markersize=15)

    # 4) Striche von Punkten zu Ort, von dem das Rating stammt plotten
    if debug:
        for p in content:
            lat1 = p[0][0]
            long1 = p[0][1]
            lat2 = p[1][0]
            long2 = p[1][1]
            plt.plot([long1, long2], [lat1, lat2], color=(0.2, 0.2, 0.2), alpha=0.2)

    # 5) Rectangles plotten:
    if debug:
        for rectangle in rectangles:
            plt.gca().add_patch(rectangle)

    # 6) Aufrufen von mplleaflet
    mplleaflet.show()