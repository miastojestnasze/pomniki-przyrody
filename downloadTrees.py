#!/usr/bin/env python3
from itertools import product
from typing import Tuple, List

import geojson
from geojson import Feature, Point, FeatureCollection
from tqdm import tqdm

import json
import re
from pathlib import Path

import httpx
from pyproj import Transformer, CRS
from pyproj import Geod


SPECIES_50 = "bez koralowy, cis pospolity, jałowiec pospolity, kruszyna pospolita, rokitnik zwyczajny, szakłak pospolity, trzmielina".split(
    ", "
)
SPECIES_100 = "bez czarny, cyprysik, czeremcha zwyczajna, czereśnia, głóg, jabłoń, jarząb pospolity, jarząb szwedzki, leszczyna pospolita, żywotnik zachodni".split(
    ", "
)
SPECIES_150 = "grusza, klon polny, magnolia drzewiasta, miłorząb, sosna Banksa, sosna limba, wierzba iwa, żywotnik olbrzymi".split(
    ", "
)
SPECIES_200 = "brzoza brodawkowata, brzoza omszona, choina, grab zwyczajny, olsza szara, orzech, sosna wejmutka, topola osika, tulipanowiec, wiąz górski, wiąz polny, wiąz szypułkowy, wierzba pięciopręcikowa".split(
    ", "
)
SPECIES_250 = "daglezja, iglicznia, jesion wyniosły, jodła pospolita, kasztanowiec zwyczajny, kasztanowiec pospolity, klon jawor, klon zwyczajny, klon pospolity, leszczyna turecka, modrzew, olsza czarna, perełkowiec, sosna czarna, sosna zwyczajna, świerk pospolity".split(
    ", "
)
SPECIES_300 = "buk zwyczajny, buk pospolity, dąb bezszypułkowy, dąb szypułkowy, lipa, platan, topola biała, wierzba biała, wierzba krucha".split(
    ", "
)
SPECIES_350 = ["topola"]
MONUMENT_SPECIES = SPECIES_50 + SPECIES_100 + SPECIES_150 + SPECIES_200 + SPECIES_250 + SPECIES_300 + SPECIES_350


class TreesDownloader:
    def __init__(self, cacheEnabled=True):
        self.wgs84Geod = Geod(ellps="WGS84")
        self.transformer = Transformer.from_crs(CRS("epsg:2178"), "wgs84")
        self.reverseTransformer = Transformer.from_crs(CRS("wgs84"), "epsg:2178")
        self.cacheEnabled = cacheEnabled

    @staticmethod
    def addQuotesToJSONKeys(data: str) -> str:
        r = re.compile(r"(?P<separator>[{,])(?P<key>[a-zA-Z]+):")
        return r.sub(r'\g<separator>"\g<key>":', data)

    def downloadData(self, theme: str, bbox: str) -> str:
        return httpx.post(
            "https://mapa.um.warszawa.pl/mapviewer/foi",
            data=dict(
                request="getfoi",
                version="1.0",
                bbox=bbox,
                width=760,
                height=1190,
                theme=theme,
                dstsrid=2178,
                cachefoi="yes",
                tid="85_311281927602616807",
                aw="no",
            ),
        ).text

    def downloadDataWithCache(self, theme: str, bbox: str) -> FeatureCollection:
        umDataDir = Path("umRawData")
        umDataDir.mkdir(exist_ok=True)
        umDataPath = umDataDir / f"{theme}-{bbox}.raw"
        if not umDataPath.exists() or not self.cacheEnabled:
            umDataPath.write_text(self.downloadData(theme, bbox))
        umData = json.loads(self.addQuotesToJSONKeys(umDataPath.read_text()))[
            "foiarray"
        ]
        features = []
        for point in umData:
            tags = {
                k: v
                for k, v in map(lambda x: x.split(": ")[:2], point["name"].split("\n"))
                if v != ""
            }
            lat, lng = self.transformer.transform(point["y"], point["x"])
            features.append(Feature(geometry=Point((lng, lat)), properties=tags))
        return FeatureCollection(features)

    @staticmethod
    def writeOutput(theme: str, data: FeatureCollection):
        outputDir = Path("output")
        outputDir.mkdir(exist_ok=True)
        outputPath = outputDir / (theme + ".geojson")
        geojson.dump(data, outputPath.open("w"))

    def process(self, theme: str) -> FeatureCollection:
        bboxWgs84 = [20.8516882, 52.0978497, 21.2711512, 52.3681531]  # Warszawa
        # bboxWgs84 = [20.9146636, 52.2094774, 21.0015245, 52.2594357]  # Wola

        def reverseTransform(coords: List[float]) -> Tuple[int, int]:
            result = list(
                map(int, self.reverseTransformer.transform(coords[1], coords[0]))
            )
            return result[0], result[1]

        minLat, minLng = reverseTransform(bboxWgs84[:2])
        maxLat, maxLng = reverseTransform(bboxWgs84[2:])
        timesLat = 30
        timesLng = 30
        stepLat = int((maxLat - minLat) / timesLat)
        stepLng = int((maxLng - minLng) / timesLng)
        trees = list()
        for latIndex, lngIndex in tqdm(list(product(range(timesLat), range(timesLng)))):
            lat = minLat + stepLat * latIndex
            bigLat = lat + stepLat
            lng = minLng + stepLng * lngIndex
            bigLng = lng + stepLng
            bbox = f"{lng}:{lat}:{bigLng}:{bigLat}"
            trees.extend(self.downloadDataWithCache(theme, bbox)["features"])
        outputData = FeatureCollection(features=list(trees))
        self.writeOutput(theme=theme, data=outputData)
        return outputData

    @staticmethod
    def isTreeMonument(feature: Feature) -> bool:
        tags = feature["properties"]
        if "Nazwa polska" not in tags or "Obwód pnia w cm" not in tags:
            return False
        name = tags["Nazwa polska"]
        if "brak danych" in name:
            return False
        try:
            circumferences = list(map(int, tags["Obwód pnia w cm"].split(",")))
            maxCircumference = max(circumferences)
            circumference = int(maxCircumference + (sum(circumferences) - maxCircumference) / 2)
        except:
            return False

        def checkSpecies(species: List[str], circumferenceThreshold: int):
            if circumference < circumferenceThreshold:
                return False
            for x in species:
                if x in name:
                    return True
            return False
        # if not checkSpecies(MONUMENT_SPECIES, 0) and circumference >= 200:
        #     print(name, circumference)
        return (
            checkSpecies(SPECIES_50, 50)
            or checkSpecies(SPECIES_100, 100)
            or checkSpecies(SPECIES_150, 150)
            or checkSpecies(SPECIES_200, 200)
            or checkSpecies(SPECIES_250, 250)
            or checkSpecies(SPECIES_300, 300)
            or checkSpecies(SPECIES_350, 350)
        )

    def saveKML(self, theme: str, data: List[Feature]):
        outputDir = Path("output")
        outputDir.mkdir(exist_ok=True)
        outputPath = outputDir / (theme + ".kml")
        with outputPath.open("w") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>\n')
            for tree in data:
                lat, lng = tree["geometry"]["coordinates"]
                tags = tree["properties"]
                name = tags["Nazwa polska"]
                circumferences = tags["Obwód pnia w cm"]
                description = "\n".join([f"{key}: {value}" for key, value in tags.items()])
                f.write(f"""
                <Placemark>
                    <name>{name} {circumferences}</name>
                    <description>{description}</description>
                    <Point>
                      <coordinates>{lat},{lng}</coordinates>
                    </Point>
                </Placemark>
                """)
            f.write("</Document></kml>\n")



    def downloadTrees(self):
        dataSets = [
            f"dane_wawa.BOS_ZIELEN_DRZEWA_{i}_SM" for i in range(1, 21)
        ]
        allTrees = list()
        for theme in tqdm(dataSets):
            trees = self.process(theme=theme)
            allTrees.extend(trees["features"])
        monuments = list(filter(self.isTreeMonument, allTrees))
        self.writeOutput(theme="ALL_TREES", data=FeatureCollection(allTrees))
        self.writeOutput(theme="POTENTIAL_MONUMENTS", data=FeatureCollection(monuments))
        self.saveKML(theme="POTENTIAL_MONUMENTS", data=monuments)

if __name__ == "__main__":
    TreesDownloader().downloadTrees()
