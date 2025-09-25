# coding: utf8
import main as m

# Festsetzen von Standardwerten, die nur optinal über das UI abgefragt werden
splitter = 380
margin_percent = 0.3

# Eingabe der Informationen über Konsole
# Verpflichtende Eingaben: Startpunkt, Zielpunkt, Reifenanzahl, Debug(Nein=0 / Ja=1)
# Optionale Eingaben (Wenn Debug=1): "Splitter" & Gewünschte Marge

input_start = input("Start (z.B.: Messe Bozen; Vöranerweg 4; Roșu 077042):   ")
input_destination = input("Ziel  (z.B.: Meran; Vöranerweg 6; Manolache 077105):    ")
input_tire_count = int(input("Anzahl der Reifen (z.B. 6):                             "))
debug = bool(int((input("Debug? (0/1):                                           "))))
if debug:
    splitter = int(input("Splitter (Standard: 380)                                "))
    margin_percent = float(input("Zielmarge in % (Standard: 0.3)                          "))

tire_settings = m.pd.read_csv("userfiles/wheel_data.csv").values[0]

# Aufrufen von Methoden:
timer = m.time.time()
start = m.give_coordinate_for_location(input_start)
destination = m.give_coordinate_for_location(input_destination)

# Die Strecke von A nach B wurde in verschiedene Sektionen unterteilt, um nicht mit zu langen Strecken auf einmal
# rechnen zu müssen. In wie viele Sektionen dabei unterteilt wird, ist von 'splitter' abhängig.
# Splitter = 380 bedeutet, die Route wird in Sektionen unterteilt, wobei jede Sektion 380 Koordinaten umfassen soll.
# Werden im Umfeld einer section keine Straßenzustände gefunden, so wird die section in einen Puffer aufgenommen,
# der dann zusammen mit der nächsten Section behantelt wird. Falls hier dann Straßenzustände vorliegen, wird normal
# fortgefahren, falls nicht, wiederholt sich das Ganze und der Puffer wird größer

paths = m.find_path(start, destination, splitter=splitter)
snapped_path = []
snap_max_distance = 0
counter = 0
rectangles = []
puffer = []
for path in paths:
    try:
        snap_result = m.snap_ratings_to_route(puffer + path)
        rectangles += snap_result[3]
        snapped_path += snap_result[0]
        if snap_result[2] > snap_max_distance:
            snap_max_distance = snap_result[2]
        puffer = []
    except IndexError:
        puffer += path
    counter += 1
    print(round((counter / len(paths) * 100), 0), "%", " | ", counter, " / ", len(paths))

price_result = m.price_rated_route(snapped_path, input_tire_count,
                                 tire_settings[0], tire_settings[1], tire_settings[2], margin_percent)

# Output Implementierung:
m.plot(snapped_path, rectangles, debug=debug)
print("\n-> ERGEBNIS:")
print("Koordinaten:                       ", input_start, "= ", start.get_coordinates(), "\n"
      "                                   ", input_destination, "= ", destination.get_coordinates())
print("")
print("Streckenlänge:                     ", price_result[1][1], " km")
print("Streckenbewertung (Skala von 1-7): ", price_result[1][0])
print("")
print("Endkundenpreis:                    ", price_result[0][0], "€")
print("Endkundenpreis/km:                 ", price_result[0][0] / price_result[1][1], "€/km")
print("")
print("Max. Abstand zu Messpunkt:         ", snap_max_distance, "km")
print("")
print("Took                               ", m.time.time() - timer, " secounds")
if debug:
    print("Splitter=                          ", splitter, "|", len(snapped_path))