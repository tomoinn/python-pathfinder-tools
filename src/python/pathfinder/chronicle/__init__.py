from PyPDF2 import PdfFileReader, PdfFileWriter
from pathfinder.chronicle.pdf import TransparentPDF
from pathfinder.chronicle.cells import get_cells_for_season
from io import BytesIO
import types
from datetime import date
import re
import csv
import requests
from dataclasses import dataclass


@dataclass
class PlayerDetails:
    """
    Holds columns from the reporting sheet CSV, columns must be in the order declared here or nothing will work!
    """
    player_name: str
    pfs_number: int
    character_number: int
    character_name: str
    faction: str
    slow: bool
    tier: int
    dayjob_roll: int
    prestige: int
    xp: int
    gold: int
    notes: str
    date: str
    event_name: str
    event_code: str
    gm_number: str


def parse_reporting_sheet(sheet_export_url):
    """
    Build a list of PlayerDetails objects from the specified sheet URL. This URL must point to the exportable CSV of
    the export sheet within the reporting doc.
    """
    response = requests.get(sheet_export_url)
    reader = csv.reader(response.content.decode('utf-8').splitlines(), delimiter=',')
    # Skip header row
    reader.__next__()
    return list([PlayerDetails(*row) for row in reader])


class ChronicleSheet:
    """
    Wraps up a dictionary of cells and a TransparentPDF instance used to create annotations.
    """

    def __init__(self, cells, pdf: TransparentPDF):
        self.cells = cells
        self.pdf = pdf
        self.default_font = 'Arial'
        self.default_style = ''

    def strike_out(self, cellname: str):
        """
        If the given cellname exists, cross it out.

        :param cellname:
            Cell name within this sheet
        """
        offset = 1
        if cellname in self.cells:
            self.pdf.set_alpha(1.0)
            x, y, width, height, centred_text = self.cells[cellname]
            self.pdf.set_line_width(1)
            self.pdf.line(x + offset, y + offset, x + width - offset, y + height - offset)
            self.pdf.line(x + width - offset, y + offset, x + offset, y + height - offset)

    def text(self, cellname, contents, centred=None, font=None, style=None):
        if font is None:
            font = self.default_font
        if style is None:
            style = self.default_style
        if cellname in self.cells and contents is not None:
            if isinstance(contents, date):
                contents = contents.strftime('%d %b %Y')
            x, y, width, height, centre_text = self.cells[cellname]
            base_font_size = 14 * height / 7
            contents = str(contents)
            self.pdf.set_font(font, style=style, size=base_font_size)
            self.pdf.set_line_width(0)
            if str.endswith(contents, '.5'):
                if str.startswith(contents, '0'):
                    contents = u"\u00BD"
                else:
                    contents = contents[:-2] + u"\u00BD"
            text_width = self.pdf.get_string_width(contents)
            if text_width > (width - 1):
                self.pdf.set_font_size(base_font_size * ((width - 1) / text_width))
                text_width = self.pdf.get_string_width(contents)
            if centred is None:
                centred = centre_text
            offset = (width - (text_width + 1)) / 2 if centred else 0.5
            self.pdf.text(x + offset, y + height - 1.6, contents)

    def texts(self, **kwargs):
        for cell, contents in kwargs.items():
            self.text(cellname=cell, contents=contents)

    def image(self, cellname, image_filename):
        if cellname in self.cells:
            x, y, width, height, centre_text = self.cells[cellname]
            self.pdf.image(image_filename, x, y, 0, height)

    def rect(self, cellname):
        if cellname in self.cells:
            x, y, width, height, centred_text = self.cells[cellname]
            self.pdf.rect(x, y, width, height, style='F')


def add_font(family, style='', fname='', uni=False):
    def annotate(sheet: ChronicleSheet):
        sheet.pdf.add_font(family, style, fname, uni)

    return annotate


def set_font(font_name, style=''):
    def annotate(sheet: ChronicleSheet):
        sheet.default_font = font_name
        sheet.default_style = style

    return annotate


def show_cells(red=255, green=255, blue=100, alpha=0.3):
    """
    Highlight all available cells, defaults to a pale yellow and mostly used when testing layout to
    see that everything's in the right place, but I guess you could use it if you just like the colours.

    :param red:
        Red value, 0-255
    :param green:
        Green value, 0-255
    :param blue:
        Blue value, 0-255
    :param alpha:
        Alpha, 0-1.0
    """

    def annotate(sheet: ChronicleSheet):
        sheet.pdf.set_fill_with_alpha(red, green, blue, alpha)
        for cell_name in sheet.cells:
            sheet.rect(cell_name)
        sheet.pdf.set_alpha(1.0)

    return annotate


def notes(top=None, bottom=None):
    """
    Add notes in the 'always available' (we think) space at the top and bottom of the sheet. This is useful
    when sheets require you to cross out boons etc, or indicate choices. We don't know where the boons are so
    it's impossible to automatically tick boxes or cross them off, but you can indicate what you would have done
    in a physical sheet here if needed.

    :param top:
        A message to show just below the 'This chronicle sheet grants...' header, defaults to None
    :param bottom:
        A message to show immediately below the event number etc, defaults to None
    """

    def annotate(sheet: ChronicleSheet):
        sheet.texts(note_top=top, note_bottom=bottom)

    return annotate


def tier(tier: int, slow=False):
    """
    Fill in the tier section, crosses out all but the selected tier

    :param tier:
        The tier to pick - this isn't the level range of the game. For the low tier, use 1, between subtiers use
        2, higher tier uses 3. There are some sheets with a fourth tier, in which case use 4.
    :param slow:
        Defaults to False, set to True to use the slow version of the selected tier.
    """

    def annotate(sheet: ChronicleSheet):
        tier_cellnames = [name for name in sheet.cells if str.startswith(name, 'subtier')]
        if f'subtier_{tier}_slow' in tier_cellnames:
            tier_cellnames.remove(f'subtier_{tier}_{"slow" if slow else "fast"}')
        for tier_cellname in tier_cellnames:
            sheet.strike_out(tier_cellname)

    return annotate


def player(player_name, character_name, player_number, character_number, faction):
    """
    Fill in the player section

    :param player_name:
        Player's name
    :param character_name:
        Character's name
    :param player_number:
        Player's society number
    :param character_number:
        Character number
    :param faction:
        Faction, best to use abbreviations here as the box isn't very big!
    """

    def annotate(sheet: ChronicleSheet):
        sheet.texts(player_name=player_name, character_name=character_name, player_number=player_number,
                    character_number=character_number, character_faction=faction)

    return annotate


def xp(xp_gained, starting_xp=None, ):
    """
    Fill in the XP section

    :param starting_xp:
        Starting XP
    :param xp_gained:
        XP gained this adventure
    """

    def annotate(sheet: ChronicleSheet):
        if starting_xp is not None:
            sheet.texts(starting_xp=starting_xp, xp_gained=xp_gained, final_xp=starting_xp + xp_gained)
        else:
            sheet.texts(xp_gained=xp_gained)

    return annotate


def gm(signature_filename: str, initials_filename: str, gm_number: int):
    """
    Fill in the GM section

    :param signature_filename:
        Path to an image containing the GM signature
    :param initials_filename:
        Path to an image containing the GM initials
    :param gm_number:
        GM society number
    """

    def annotate(sheet: ChronicleSheet):
        sheet.image('gm_sig', signature_filename)
        for cellname in sheet.cells:
            if str.endswith(cellname, 'initials'):
                sheet.image(cellname, initials_filename)
        sheet.text('gm_number', gm_number)

    return annotate


def gold_and_day_job(gp_gained: int, roll: str):
    """
    Fill in day job from roll, and gold gained, ignoring everything else
    :param gp_gained:
        Sets the value of the gp_gained box
    :param roll:
        if an int, interpreted as a D20 day-job check. If None, strike out the day job box, otherwise enter
        this value directly into the box
    :return:
    """

    def gold_for_day_job(r: int):
        if r <= 5:
            return 1
        if r <= 10:
            return 5
        if r <= 15:
            return 10
        if r <= 20:
            return 20
        if r <= 25:
            return 50
        if r <= 30:
            return 75
        if r <= 35:
            return 100
        if r <= 40:
            return 150
        return 150

    def annotate(sheet: ChronicleSheet):
        sheet.texts(gp_gained=gp_gained)
        if roll is not None:
            try:
                roll_int = int(roll)
                sheet.texts(day_job=gold_for_day_job(roll_int))
            except ValueError:
                sheet.texts(day_job=roll)
        else:
            sheet.strike_out('day_job')

    return annotate


def gold(gp_gained: int, starting_gp=None, day_job=0, gp_spent=0, items_sold=0):
    """
    Fill in the GP section

    :param starting_gp:
        Starting gold
    :param gp_gained:
        Gold gained
    :param day_job:
        Day job, defaults to 0
    :param gp_spent:
        Gold spent, defaults to 0
    :param items_sold:
        Gold recovered from selling items, defaults to 0
    """

    def annotate(sheet: ChronicleSheet):
        sheet.texts(starting_gp=starting_gp, gp_gained=gp_gained)
        if day_job is not 0:
            sheet.text('day_job', day_job)
        else:
            sheet.strike_out('day_job')
        # Some sheets have items sold / items bought, some just have 'gold spent'
        if 'items_sold' not in sheet.cells:
            inner_gp_spent = gp_spent - items_sold
            inner_items_sold = 0
        else:
            inner_gp_spent = gp_spent
            inner_items_sold = items_sold
        if inner_gp_spent is not 0:
            sheet.text('gp_spent', inner_gp_spent)
        else:
            sheet.strike_out('gp_spent')
        if inner_items_sold is not 0:
            sheet.text('items_sold', inner_items_sold)
        else:
            sheet.strike_out('items_sold')
        sheet.text('gp_subtotal', starting_gp + gp_gained + day_job + items_sold)
        sheet.text('gp_total', starting_gp + gp_gained + day_job - gp_spent + items_sold)

    return annotate


def event(event_name, event_code: int, game_date=None):
    """
    Event details

    :param event_name:
        Event name
    :param event_code:
        Event number
    :param game_date:
        Date, defaults to today. Can be a string, or an instance of datetime.date
    """
    if game_date is None:
        game_date = date.today()

    def annotate(sheet: ChronicleSheet):
        sheet.texts(event=event_name, event_code=event_code, date=game_date)

    return annotate


def prestige(prestige_gained, initial_prestige=None, initial_fame=None, prestige_spent=0):
    """
    Show prestige

    :param initial_prestige:
        Initial prestige
    :param initial_fame:
        Initial fame
    :param prestige_gained:
        Prestige gained this adventure
    :param prestige_spent:
        Prestige spent this adventure
    """

    def annotate(sheet: ChronicleSheet):
        if initial_prestige is not None:
            sheet.texts(initial_prestige=initial_prestige,
                        initial_fame=initial_fame,
                        prestige_gained=prestige_gained,
                        current_fame=initial_fame + prestige_gained,
                        current_prestige=initial_prestige + prestige_gained - prestige_spent)
            if prestige_spent is not 0:
                sheet.texts(prestige_spent=prestige_spent)
            else:
                sheet.strike_out('prestige_spent')
        elif prestige_gained is not None:
            sheet.texts(prestige_gained=prestige_gained)

    return annotate


def chronicle_info(input_filename: str):
    with open(input_filename, mode='rb') as input_file:
        input_pdf = PdfFileReader(input_file)
        # Work around a library bug, sometimes it thinks things are encrypted when they're not
        if input_pdf.isEncrypted:
            input_pdf.decrypt('')
        # Try to find the scenario number, and therefore the season to use
        print(input_pdf.getDocumentInfo())
        try:
            title = input_pdf.getDocumentInfo()['/Title']
        except KeyError:
            title = 'Unknown'
        m = re.search(r'(\d\d)(\d\d)', title)
        if m:
            season = int(m.groups()[0])
            scenario = int(m.groups()[1])
            return title, season, scenario
        return title, '?', '?'


def annotate_chronicle_sheet(input_filename: str, output_filename: str, season: int = 0, page_number: int = 0,
                             annotation_functions=None):
    # Scale points to mm by multiplying by..
    pt_to_mm = 0.35277777777778
    # Read the input PDF
    with open(input_filename, mode='rb') as input_file:
        input = PdfFileReader(input_file)
        # Work around a library bug, sometimes it thinks things are encrypted when they're not
        if input.isEncrypted:
            input.decrypt('')

        if page_number is 0:
            # No page number specified, use the last page in the PDF
            page_number = input.getNumPages()
        page = input.getPage(page_number - 1)
        # Try to find the scenario number, and therefore the season to use
        if season is 0:
            print(input.getDocumentInfo())
            title = input.getDocumentInfo()['/Title']
            m = re.search(r'(\d\d)(\d\d)', title)
            if m:
                season = int(m.groups()[0])

        # Create a blank FPDF document of the correct size with a single page
        width, height = page.mediaBox.upperRight  # Sizes in points, i.e. 1/72 inch units
        overlay_pdf = TransparentPDF(orientation='P', unit='mm',
                                     format=(float(width) * pt_to_mm, float(height) * pt_to_mm))
        overlay_pdf.add_page()
        # Write any annotations to the overlay
        if annotation_functions is None:
            annotation_functions = []
        if type(annotation_functions) == types.FunctionType:
            annotation_functions = [annotation_functions]
        # Pick up the right cell dict based on the season and create a new ChronicleSheet to annotate
        sheet = ChronicleSheet(cells=get_cells_for_season(season), pdf=overlay_pdf)
        for annotation_function in annotation_functions:
            # Run each of the annotation functions in turn to add content
            annotation_function(sheet)
        # Merge from the overlay onto the original page
        with BytesIO(overlay_pdf.output(dest='S').encode('latin-1')) as stream:

            overlay_pdf2 = PdfFileReader(stream, strict=False)
            merge = overlay_pdf2.getPage(0)
            page.mergePage(merge)
            # Write the output PDF
            with open(output_filename, mode='wb') as output_file:
                writer = PdfFileWriter()
                writer.addPage(page)
                writer.write(output_file)
