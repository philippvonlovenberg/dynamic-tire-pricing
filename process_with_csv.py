# coding: utf8
import main as m

# Festsetzen von Standardwerten, die sonst über das UI abgefragt werden könnten
splitter = 380
margin_percent = 0.3

# Einlesen der CSV "to_process.csv" im Ordner userfiles

csv_i = m.pd.read_csv("userfiles/to_process.csv").values.tolist()

# Zuerst für alle Strecken Abfragen der Koordinaten und Paths. So können Fehler (z.B. unmögliche Routen wie
# London > Sydney) schnell gefunden werden)
lines = []
all_paths = []
for line in csv_i:
    print(line[1], "->", line[2], " | ",
          m.give_coordinate_for_location(line[1]).get_coordinates(), "->",
          m.give_coordinate_for_location(line[2]).get_coordinates())
    input_start = line[1]
    input_destination = line[2]
    start = m.give_coordinate_for_location(input_start)
    destination = m.give_coordinate_for_location(input_destination)
    all_paths.append(m.find_path(start, destination, splitter=splitter))


# Kopf (1. Zeile) der ausgegebenen Ergebnis-CSV:
csv_o_header = ["Reifenanzahl", "Start", "Ziel", "->", "Startkoordinate", "Endkoordinate", "", "Streckenlänge",
                "Streckenbewertung (Skala von 1-7)", "", "Endkundenpreis", "Endkundenpreis/km", "",
                "Max. Abstand zu Messpunkt", "Dauer der Berechnung in s"]


# 'sums' enthält die Summen:
#   - der Strecken,
#   - der Endkundenpreise und
#   - der Berechnungsdauer angeben,
# um später die Gesamtwerte (z.B. Gesamtpreis) ausgeben zu können
sums = [0.0, 0.0, 0.0]

# Für jede Zeile in der orig. CSV werden nun die Informationen genommen, zusätzlich die Reifendaten importiert und dann
# die Methoden aus main.py aufgerufen
counter = 0
for line in csv_i:
    paths_for_line = all_paths[counter]
    counter += 1

    input_start = line[1]
    input_destination = line[2]
    input_tire_count = int(line[0])

    tire_settings = m.pd.read_csv("userfiles/wheel_data.csv").values[0]

    # Aufrufen von Methoden:
    timer = m.time.time()

    start = m.give_coordinate_for_location(input_start)
    destination = m.give_coordinate_for_location(input_destination)

    snapped_path = []
    snap_max_distance = 0
    counter2 = 0
    # Fortschrittsindikator:
    print("")
    print("Processing line {}/{}..................................".format(len(lines) + 1, len(csv_i)),
          line[1], "->", line[2])
    print("")

    # Die Strecke von A nach B wurde in verschiedene Sektionen unterteilt, um nicht mit zu langen Strecken auf einmal
    # rechnen zu müssen. In wie viele Sektionen dabei unterteilt wird, ist von 'splitter' abhängig.
    # Splitter = 380 bedeutet, die Route wird in Sektionen unterteilt, wobei jede Sektion 380 Koordinaten umfassen soll.
    # Werden im Umfeld einer section keine Straßenzustände gefunden, so wird die section in einen Puffer aufgenommen,
    # der dann zusammen mit der nächsten Section behantelt wird. Falls hier dann Straßenzustände vorliegen, wird normal
    # fortgefahren, falls nicht, wiederholt sich das Ganze und der Puffer wird größer

    puffer = []

    for path in paths_for_line:
        try:
            snap_result = m.snap_ratings_to_route(puffer + path)
            snapped_path += snap_result[0]
            if snap_result[2] > snap_max_distance:
                snap_max_distance = snap_result[2]
            puffer = []
        except IndexError:
            puffer += path
        counter2 += 1
        print(round((counter2 / len(paths_for_line) * 100), 0), "%", " | ", counter2, " / ", len(paths_for_line))

    price_result = m.price_rated_route(snapped_path, input_tire_count,
                                       tire_settings[0], tire_settings[1], tire_settings[2], margin_percent)

    # Hinzufügen der Ergebnisse zu der Zeile und Aufnahme der befüllten Zeile in die Liste 'lines':
    t = m.time.time() - timer
    result = ["->", start.get_coordinates(), destination.get_coordinates(), "", price_result[1][1], price_result[1][0],
              "", price_result[0][0], price_result[0][0] / price_result[1][1], "",
              snap_max_distance, t]
    for i in result:
        line.append(i)

    lines.append(line)

    # Speichern nach jeder Zeile. Bricht das Programm z.B. bei Zeile 150 / 300 ab, so sind so die Ergebnisse für die
    # ersten 150 Zeilen trotzdem einsehbar
    csv_o = m.pd.DataFrame(data=lines, columns=csv_o_header)
    csv_o.to_csv("userfiles/_processed_csv.csv", index=False)

    # Erhöhen der Summen (Stecke, Preis, Zeit)
    sums[0] += price_result[1][1]
    sums[1] += price_result[0][0]
    sums[2] += t

# Hinzufügen einer leeren Zeile und einer Zeile mit den Summen (Strecke, Preis, Zeit) ans Ende
lines.append(["", "", "", "", "", "", "", "", "", "", "", "", "", "", ""])
lines.append(["", "", "", "", "", "", "",
              str(sums[0]), "", "", str(sums[1]), str(sums[1]/sums[0]), "", "", str(sums[2])])

print("Gesamtstrecke: {}, Gesamtpreis: {}, Gesamptpreis/km: {}, Berechnungszeit: {}"
      .format(sums[0], sums[1], sums[0]/sums[1], sums[2]))

csv_o = m.pd.DataFrame(data=lines, columns=csv_o_header)
csv_o.to_csv("userfiles/_processed_csv.csv", index=False)