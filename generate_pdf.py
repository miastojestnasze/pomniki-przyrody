import datetime
import math
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image as PILImage
import httpx
from PIL import ImageDraw
from borb.io.read.types import Decimal
from borb.pdf import (
    PDF,
    Alignment,
    Document,
    FlexibleColumnWidthTable,
    Image,
    InlineFlow,
    Page,
    PageLayout,
    Paragraph,
    SingleColumnLayout,
)
from borb.pdf.canvas.font.simple_font.true_type_font import TrueTypeFont
from borb.pdf.canvas.layout.text.line_of_text import LineOfText
from borb.pdf.page.page_size import PageSize


@dataclass
class FormInput:
    signature: str


@dataclass
class Tree:
    speciesPolish: str
    speciesLatin: str
    circumferences: list[int]
    height: int
    lat: float
    lon: float
    date: str
    ref: str
    operator: str


@dataclass
class AddressResult:
    houseNumber: str
    street: str
    suburb: str
    city: str
    postCode: str


formInput = FormInput(signature="Filip Czaplicki")
tree = Tree(
    speciesPolish="czereśnia ptasia",
    speciesLatin="Prunus avium (L.) L.",
    height=8,
    circumferences=[157],
    lat=52.364509,
    lon=20.945023,
    date="28.05.2014",
    ref="D370612",
    operator="Dzielnica Białołęka",
)


def reverseNominatim(lat: float, lon: float) -> Optional[AddressResult]:
    try:
        response = httpx.get(
            "https://nominatim.openstreetmap.org/reverse?lat=52.364509&lon=20.945023&format=json"
        ).json()
        address = response["address"]

        return AddressResult(
            houseNumber=address["house_number"],
            street=address["road"],
            suburb=address["suburb"],
            city=address["city"],
            postCode=address["postcode"],
        )
    except:
        return None


addressNominatim = reverseNominatim(tree.lat, tree.lon)

today = datetime.date.today().isoformat()

fontRegular = TrueTypeFont.true_type_font_from_file(
    Path(__file__).parent / "font" / "Lato-Regular.ttf"
)
fontBold = TrueTypeFont.true_type_font_from_file(
    Path(__file__).parent / "font" / "Lato-Bold.ttf"
)
doc: Document = Document()
page: Page = Page(
    width=PageSize.A4_PORTRAIT.value[0], height=PageSize.A4_PORTRAIT.value[1]
)
doc.add_page(page)
layout: PageLayout = SingleColumnLayout(page)
layout.add(
    Paragraph(
        f"Warszawa, {today}", font=fontRegular, horizontal_alignment=Alignment.RIGHT
    )
)
layout.add(
    Paragraph(
        "Biuro Ochrony Środowiska", font=fontBold, horizontal_alignment=Alignment.RIGHT
    )
)
layout.add(
    Paragraph(
        "Sekretariat.BOS@um.warszawa.pl",
        font=fontBold,
        horizontal_alignment=Alignment.RIGHT,
    )
)
layout.add(
    Paragraph(
        "WNIOSEK O UZNANIE ZA POMNIK PRZYRODY",
        font=fontBold,
        horizontal_alignment=Alignment.CENTERED,
    )
)
layout.add(
    InlineFlow()
    .add(LineOfText("1. Przedmiot ochrony: ", font=fontBold))
    .add(LineOfText(tree.speciesPolish, font=fontRegular))
)
layout.add(LineOfText("2. Opis pomnika:", font=fontBold))
layout.add(
    FlexibleColumnWidthTable(number_of_columns=2, number_of_rows=7)
    .add(LineOfText("Gatunek", font=fontBold))
    .add(LineOfText(tree.speciesPolish, font=fontRegular))
    .add(LineOfText("Nazwa łacińska", font=fontBold))
    .add(LineOfText(tree.speciesLatin, font=fontRegular))
    .add(LineOfText("Wysokość", font=fontBold))
    .add(LineOfText(f"{tree.height} m", font=fontRegular))
    .add(LineOfText("Obwód pnia na wysokości 130cm", font=fontBold))
    .add(
        LineOfText(f"{tree.circumferences[0]} cm", font=fontRegular)
    )  # TODO: handle multiple
    .add(LineOfText("Aktualność danych", font=fontBold))
    .add(LineOfText(tree.date, font=fontRegular))
    .add(LineOfText("Numer inwentaryzacyjny", font=fontBold))
    .add(LineOfText(tree.ref, font=fontRegular))
    .add(LineOfText("Jednostka zarządzająca", font=fontBold))
    .add(LineOfText(tree.operator, font=fontRegular))
    .set_padding_on_all_cells(Decimal(2), Decimal(2), Decimal(2), Decimal(2))
)
layout.add(Paragraph("Źródło danych: mapa.um.warszawa.pl", font=fontRegular))


def createLocationTable():
    layout.add(LineOfText("3. Lokalizacja obiektu", font=fontBold))
    table = (
        FlexibleColumnWidthTable(
            number_of_columns=2, number_of_rows=3 if addressNominatim is not None else 1
        )
        .add(LineOfText("Współrzędne", font=fontBold))
        .add(LineOfText(f"{tree.lat}, {tree.lon}", font=fontRegular))
    )
    if addressNominatim is not None:
        table = (
            table.add(LineOfText("Dzielnica", font=fontBold))
            .add(LineOfText(addressNominatim.suburb, font=fontRegular))
            .add(LineOfText("Najbliższy adres", font=fontBold))
            .add(
                LineOfText(
                    f"{addressNominatim.street} {addressNominatim.houseNumber}, {addressNominatim.postCode} {addressNominatim.city}",
                    font=fontRegular,
                )
            )
        )

    table = table.set_padding_on_all_cells(
        Decimal(2), Decimal(2), Decimal(2), Decimal(2)
    )
    layout.add(table)


createLocationTable()




def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0**zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int(
        (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi)
        / 2.0
        * n
    )
    return (xtile, ytile)


def num2deg(xtile, ytile, zoom):
    n = 2.0**zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)


def getImageCluster(lat_deg, lon_deg, delta_lat, delta_long, zoom):
    headers = {
        "User-Agent": "Pomniki Przyrody 0.0.1"
    }
    smurl = r"http://a.tile.openstreetmap.org/{0}/{1}/{2}.png"
    xmin, ymax = deg2num(lat_deg - delta_lat / 2, lon_deg - delta_long / 2, zoom)
    xmax, ymin = deg2num(lat_deg + delta_lat / 2, lon_deg + delta_long / 2, zoom)

    Cluster = PILImage.new(
        "RGB", ((xmax - xmin + 1) * 256 - 1, (ymax - ymin + 1) * 256 - 1)
    )
    for xtile in range(xmin, xmax + 1):
        for ytile in range(ymin, ymax + 1):
            try:
                imgurl = smurl.format(zoom, xtile, ytile)
                print("Opening: " + imgurl)
                imgstr = httpx.get(imgurl, headers=headers)
                tile = PILImage.open(BytesIO(imgstr.content))
                Cluster.paste(tile, box=((xtile - xmin) * 256, (ytile - ymin) * 255))
            except:
                print("Couldn't download image")
                tile = None

    return Cluster


def downloadOpenStreetMapRender():  # -> Optional[PILImage.Image]:
    try:
        # TODO: Copyright OpenStreetMap
        return getImageCluster(tree.lat, tree.lon, 0.01, 0.01, 13)
    except Exception as e:
        print(e)
        return None


image = downloadOpenStreetMapRender()


draw = ImageDraw.Draw(image)

# Define the point coordinates
point_x = 15
point_y = 15

# Draw a point at the coordinates
# TODO: mark location

draw.point((point_x, point_y), fill=(255, 0, 0))
layout.add(
    Image(
        image,
        width=Decimal(256),
        height=Decimal(256),
    )
)


# render OpenStreetMap:
# https://render.openstreetmap.org/cgi-bin/export?bbox=20.943951308727268,52.36391611463536,20.946317017078403,52.3651543306906&scale=2950&format=pngdl

layout.add(LineOfText("Z poważaniem,", font=fontRegular))
layout.add(LineOfText(formInput.signature, font=fontRegular))


# store the PDF
with open(Path("output.pdf"), "wb") as pdf_file_handle:
    PDF.dumps(pdf_file_handle, doc)
