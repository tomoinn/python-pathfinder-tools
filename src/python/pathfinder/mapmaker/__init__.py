import io
import logging
import math
import re
import tempfile
from dataclasses import dataclass
from enum import Enum
from os.path import dirname, basename, abspath
from pathlib import Path

import PyPDF2 as pdf
from PIL import Image, ImageEnhance
from fpdf import FPDF
from guizero import App, Picture


class ImageGrid:
    """
    Holds clicks and crop images to whole grid squares based on them. First click is as close to the top left as
    possible, the next is one square diagonally away from that (in any direction, but makes most sense to be down
    and right), and the third is as far to the bottom right as possible. The second click is used to estimate grid
    size, this is then used to figure out how many squares are between the first and third clicks, which gives a more
    precise size, which is then used to crop to whole squares on all borders.
    """

    def __init__(self, image_filename, output_path):
        """
        Create an ImageGrid

        :param image_filename:
            The filename of an image to crop
        """
        self.clicks = []
        self.path = Path(image_filename)
        self.im = Image.open(image_filename)
        self.output_path = output_path if output_path is not None else self.path.parent

    def handle_click(self):
        """
        Builds a click handler to add to a guizero widget containing the image
        """

        def handler(event):
            self.clicks.append((event.x, event.y))
            self.clicks = self.clicks[-3:]
            if len(self.clicks) == 3:
                self.trim()
                event.widget.master.destroy()

        return handler

    def trim(self):
        """
        Once we have three clicks, trim the image based on them, save it, and exit the display loop
        """
        # Pick up click coordinates
        tx, ty = self.clicks[0]
        gx, gy = self.clicks[1]
        bx, by = self.clicks[2]

        # Make a course estimate of grid size used to determine how many squares
        # there are between the first and third clicks
        grid_size_estimate = (abs(gx - tx) + abs(gy - ty)) / 2
        squares_x = round(abs(tx - bx) / grid_size_estimate)
        squares_y = round(abs(ty - by) / grid_size_estimate)

        # Use this course estimate to make a finer estimate based on the larger distance
        # between the first and third click points
        refined_grid_size_estimate = (abs(tx - bx) / squares_x + abs(ty - by) / squares_y) / 2

        # Crop the top and left
        top_margin_crop = ty % refined_grid_size_estimate
        left_margin_crop = tx % refined_grid_size_estimate
        self.im = self.im.crop((left_margin_crop, top_margin_crop, self.im.width, self.im.height))

        # Crop the bottom and right
        right_margin_crop = self.im.width % refined_grid_size_estimate
        bottom_margin_crop = self.im.height % refined_grid_size_estimate
        self.im = self.im.crop((0, 0, self.im.width - right_margin_crop, self.im.height - bottom_margin_crop))

        # Calculate resultant number of squares in final, cropped, image
        squares_x = round(self.im.width / refined_grid_size_estimate)
        squares_y = round(self.im.height / refined_grid_size_estimate)

        # Use this to build an output path next to the input with the right naming for
        # the next tool to pick up on, and save the result
        output_path = self.output_path / f'{self.path.name[:-len(self.path.suffix)]}_{squares_x}x{squares_y}.png'
        logging.info(f'Saving image to {output_path}')
        self.im.save(fp=output_path)

    @staticmethod
    def show_and_crop(image_name, output_dir=None):
        """
        Load an image, create the very simple GUI, crop when we have three clicks, then return
        """
        logging.info('Pick three points - top left, top left + 1 square diagonally, then bottom right')
        grid = ImageGrid(image_name, output_dir)
        app = App(title=f'Grid Finder - {image_name}', width=grid.im.width, height=grid.im.height, layout='auto')
        app.tk.resizable(False, False)
        picture = Picture(app, image=grid.im)
        picture.when_clicked = grid.handle_click()
        picture.tk.config(cursor='cross')
        app.display()


def parse_filename(filename):
    """
    Parse a filename of the form name_WWxHH.png, i.e. deep_canyon_10x18.png, into a set of useful properties. Returns
    a tuple containing the canonical filename supplied, the canonical name of the pdf to produce, the plain name with
    the sizes stripped, and the width and height specified.

    :param filename:
        Filename to parse
    :return:
        A tuple of (filename, pdf_name, name, width, height)
    :raise:
        ValueError if the string can't be parsed in this format
    """
    filename = abspath(filename)
    leaf_name = basename(filename)
    # Match in the form foo_bar_12.4x25.3.png and extract the name, 12.4, and 25.3 bits
    m = re.match(r'(^[\w-]+?)_*(\d+(?:\.\d*)?|\.\d+)x(\d+(?:\.\d*)?|\.\d+)\.png$',
                 leaf_name)
    if m:
        name = m.groups()[0]
        width = float(m.groups()[1])
        height = float(m.groups()[2])
        pdf_name = dirname(filename) + '/' + name + '.pdf'
        return filename, pdf_name, name, width, height
    else:
        raise ValueError('Filename not of the form name_WxH.png, was {}'.format(leaf_name))


@dataclass
class PaperSize:
    """
    Defines a paper size
    """
    width: int
    height: int
    name: str


class Paper(Enum):
    """
    Common paper sizes, used by the split_image and make_pdf functions to determine how images should be tiled across
    the available paper space.
    """

    A4 = PaperSize(height=297, width=210, name='A4')
    A3 = PaperSize(height=420, width=297, name='A3')
    A2 = PaperSize(height=594, width=420, name='A2')
    A1 = PaperSize(height=841, width=594, name='A1')
    A0 = PaperSize(height=1189, width=841, name='A0')

    @property
    def dimensions(self):
        return self.width, self.height

    @property
    def width(self):
        return self.value.width

    @property
    def height(self):
        return self.value.height

    @property
    def name(self):
        return self.value.name


def basic_image_ops(image, brighten=1.0, sharpen=None, saturation=None):
    """
    Perform basic brighten, sharpen, colour operations on an image

    :param image:
        Image to process
    :param brighten:
        Change in brightness, defaults to 1.0 for no change
    :param sharpen:
        Sharpen, defaults to None for no operation
    :param saturation:
        Saturation, defaults to None for no operation
    :return:
        The modified image
    """
    if brighten is not None and brighten != 1.0:
        logging.info('Applying brighten {}'.format(brighten))
        image = ImageEnhance.Brightness(image).enhance(brighten)
    if sharpen is not None:
        logging.info('Applying sharpen {}'.format(sharpen))
        image = ImageEnhance.Sharpness(image).enhance(sharpen)
    if saturation is not None:
        logging.info('Applying saturation {}'.format(saturation))
        image = ImageEnhance.Color(image).enhance(saturation)
    return image


def process_image_with_border(im: Image, squares_wide: float, squares_high: float, border_north=5, border_east=5,
                              border_west=5, border_south=5, brighten=None, sharpen=None, saturation=None):
    """
    Process an image and calculate sizes, but do not split. This is used when we want to obtain a PDF of a single page
    sized exactly to the image rather than splitting an image across multiple known sized pages. Some print houses can
    accept this as an input to custom sized printing, if we're using those we don't want to split up the image or use
    a paper size larger than we need.

    :param im:
        An Image to process
    :param squares_wide:
        The number of 1 inch squares along the width of the input image
    :param squares_high:
        The number of 1 inch squares along the height of the input image
    :param border_north:
        North border (portrait orientation) in mm
    :param border_east:
        East border (portrait orientation) in mm
    :param border_south:
        South border (portrait orientation) in mm
    :param border_west:
        West border (portrait orientation) in mm
    :param brighten:
        Set to >1.0 to brighten the image before splitting, <1.0 to darken, or leave as None for no effect
    :param sharpen:
        Set to >1.0 to shapen the image before splitting.
    :param saturation:
        Set to >1.0 to enhance colour, <1.0 to remove it, None for no effect
    :return:
        Dict of image, image_width, image_height, margin_left, margin_top, page_width, page_height where all dimensions
        are specified in mm. This dict can be passed directly into process_single_image_pdf
    """
    width_pixels, height_pixels = im.size
    logging.info('process_image_with_border: Image is {} x {} pixels'.format(width_pixels, height_pixels))
    pixels_per_mm = min(width_pixels / (squares_wide * 25.4), height_pixels / (squares_high * 25.4))
    logging.info('process_image_with_border: Calculated {} pixels per mm'.format(pixels_per_mm))
    # Apply enhancements if required
    im = basic_image_ops(im, brighten, sharpen, saturation)
    image_width_mm = width_pixels / pixels_per_mm
    image_height_mm = height_pixels / pixels_per_mm

    return {
        'image': im,
        'image_width': image_width_mm,
        'image_height': image_height_mm,
        'margin_left': border_west,
        'margin_top': border_north,
        'page_width': image_width_mm + border_west + border_east,
        'page_height': image_height_mm + border_north + border_south
    }


def make_single_page_pdf(image_spec: {}, pdf_filename: str):
    """
    Take the processed image from process_image_with_border and produce a PDF file with those exact dimensions and a
    single page.

    :param image_spec:
        Return from process_image_with_border
    :param filename:
        Filename to write
    """
    pdf = FPDF(unit='mm', format=(image_spec['page_width'], image_spec['page_height']))
    with tempfile.TemporaryDirectory() as dirpath:
        pdf.add_page()
        image_spec['image'].save(f'{dirpath}/image.png')
        pdf.image(f'{dirpath}/image.png',
                  image_spec['margin_left'],
                  image_spec['margin_top'],
                  image_spec['image_width'],
                  image_spec['image_height'])
        pdf.output(pdf_filename, 'F')


def split_image(im: Image, squares_wide: float, squares_high: float, border_north=5, border_east=5, border_west=5,
                border_south=5, overlap_east=10, overlap_south=10, paper=Paper.A4, brighten=None,
                sharpen=None, saturation=None):
    """
    Split an input image into a set of images which will tile across the paper, either horizontally or vertically as
    determined by which would take the fewer pages when naively printed. At the moment this doesn't attempt to be
    clever and stack multiple small images on a single page.

    :param im:
        An Image to process
    :param squares_wide:
        The number of 1 inch squares along the width of the input image
    :param squares_high:
        The number of 1 inch squares along the height of the input image
    :param border_north:
        North border (portrait orientation) in mm
    :param border_east:
        East border (portrait orientation) in mm
    :param border_south:
        South border (portrait orientation) in mm
    :param border_west:
        West border (portrait orientation) in mm
    :param overlap_east:
        The number of mm by which the east edge (portrait) of each sheet will be extended when printing. This allows
        for easier taping of multiple pages as it's no longer so critical where the paper is cut. Defaults to 0.
    :param overlap_south:
        The number of mm by which the south edge (portrait) of each sheet will be extended when printing. This allows
        for easier taping of multiple pages as it's no longer so critical where the paper is cut. Defaults to 0.
    :param paper:
        An instance of Paper specifying the dimensions of the paper to use when tiling.
    :param brighten:
        Set to >1.0 to brighten the image before splitting, <1.0 to darken, or leave as None for no effect
    :param sharpen:
        Set to >1.0 to shapen the image before splitting.
    :param saturation:
        Set to >1.0 to enhance colour, <1.0 to remove it, None for no effect
    :return:
        A dict of {pixels_per_mm:int, images:{name : image}, orientation:str[L|P], border:int}
    """

    width_pixels, height_pixels = im.size
    logging.info('split_image: Image is {} x {} pixels'.format(width_pixels, height_pixels))
    pixels_per_mm = min(width_pixels / (squares_wide * 25.4), height_pixels / (squares_high * 25.4))
    logging.info('split_image: Calculated {} pixels per mm'.format(pixels_per_mm))

    # Apply enhancements if required
    im = basic_image_ops(im, brighten, sharpen, saturation)

    width_mm = width_pixels / pixels_per_mm
    height_mm = height_pixels / pixels_per_mm

    def get_page_size():

        printable_width = paper.width - (border_east + border_west)
        printable_height = paper.height - (border_north + border_south)

        def pages(size, printable_size, overlap):
            if math.ceil(size / printable_size) == 1:
                number_pages = 1
            else:
                number_pages = math.ceil(size / (printable_size + overlap))
            logging.debug(f'pages(size={size} printable_size={printable_size} overlap={overlap}) = {number_pages}')
            return number_pages

        pages_horizontal_p = pages(width_mm, printable_width, overlap_east)
        pages_vertical_p = pages(height_mm, printable_height, overlap_south)
        pages_horizontal_l = pages(width_mm, printable_height, overlap_south)
        pages_vertical_l = pages(height_mm, printable_width, overlap_east)

        def zero_if_one(test, value):
            if test == 1:
                return 0
            return value

        if pages_horizontal_p * pages_vertical_p > pages_horizontal_l * pages_vertical_l:
            # Use landscape orientation
            logging.info(
                'split_image: Using landscape orientation, {} by {} pages'.format(pages_horizontal_l, pages_vertical_l))
            return 'L', pages_horizontal_l, pages_vertical_l, \
                   printable_height - zero_if_one(pages_horizontal_l, overlap_south), \
                   printable_width - zero_if_one(pages_vertical_l, overlap_east)
        else:
            # Use Portrait orientation
            logging.info(
                'split_image: Using portrait orientation, {} by {} pages'.format(pages_horizontal_p, pages_vertical_p))
            return 'P', pages_horizontal_p, pages_vertical_p, \
                   printable_width - zero_if_one(pages_horizontal_p, overlap_east), \
                   printable_height - zero_if_one(pages_vertical_p, overlap_south)

    orientation, pages_horizontal, pages_vertical, page_width, page_height = get_page_size()

    pixel_width_page = page_width * pixels_per_mm
    pixel_height_page = page_height * pixels_per_mm

    if orientation == 'P':
        overlap_east_pixels = pixels_per_mm * overlap_east
        overlap_south_pixels = pixels_per_mm * overlap_south
        borders = [border_north, border_east + overlap_east, border_south + overlap_south, border_west]
    else:
        overlap_east_pixels = pixels_per_mm * overlap_south
        overlap_south_pixels = pixels_per_mm * overlap_east
        borders = [border_east, border_south + overlap_east, border_west + overlap_south, border_north]

    def crop_for(page_x, page_y):
        return im.crop((page_x * pixel_width_page, page_y * pixel_height_page,
                        min(width_pixels, (page_x + 1) * pixel_width_page + overlap_east_pixels),
                        min(height_pixels, (page_y + 1) * pixel_height_page + overlap_south_pixels)))

    return {'pixels_per_mm': pixels_per_mm,
            'images': {'{}_{}'.format(x, y): crop_for(x, y) for x in range(pages_horizontal) for y in
                       range(pages_vertical)},
            'orientation': orientation,
            'border': borders,
            'pages_horizontal': pages_horizontal,
            'pages_vertical': pages_vertical,
            'paper': paper}


def make_pdf(images, pdf_filename):
    """
    Write a set of images from split_images into a combined A4 PDF file

    :param images:
        The output dict from split_images
    :param pdf_filename:
        Full name of the PDF to write
    """
    logging.info('make_pdf: Building PDF file {} from image data'.format(pdf_filename))
    pdf = FPDF(orientation=images['orientation'], unit='mm', format=images['paper'].dimensions)
    ppm = images['pixels_per_mm']
    border_north, border_east, border_south, border_west = images['border']
    if images['orientation'] == 'P':
        page_width, page_height = images['paper'].dimensions
    else:
        page_height, page_width = images['paper'].dimensions

    def tick(x, y, size=5, gap=1, n=False, e=False, s=False, w=False, dash=False):
        line = pdf.line
        if dash:
            line = pdf.dashed_line
        if w:
            if x <= size:
                line(x - gap, y, 0, y)
            else:
                line(x - gap, y, x - size, y)
        if e:
            if page_width - x <= size:
                line(x + gap, y, page_width, y)
            else:
                line(x + gap, y, x + size, y)
        if n:
            if y <= size:
                line(x, y - gap, x, 0)
            else:
                line(x, y - gap, x, y - size)
        if s:
            if page_height - y <= size:
                line(x, y + gap, x, page_height)
            else:
                line(x, y + gap, x, y + size)

    with tempfile.TemporaryDirectory() as dirpath:
        for coords, image in images['images'].items():
            pdf.add_page()

            m = re.match(r'(\d+)_(\d+)', coords)
            x = int(m.groups()[0])
            y = int(m.groups()[1])

            im_width, im_height = image.size

            im_width_mm = im_width / ppm
            im_height_mm = im_height / ppm
            last_vertical = y == images['pages_vertical'] - 1
            last_horizontal = x == images['pages_horizontal'] - 1

            # Always position the top left one the same
            tick(border_west, border_north, n=True, w=True)
            tick(border_west, border_north + im_height_mm, s=True, w=True)
            tick(border_west + im_width_mm, border_north + im_height_mm, e=True, s=True)
            tick(border_west + im_width_mm, border_north, e=True, n=True)

            if not last_horizontal:
                tick(page_width - border_east, im_height_mm + border_north, s=True, dash=True)
                tick(page_width - border_east, border_north, n=True, dash=True)

            if not last_vertical:
                tick(border_west, page_height - border_south, w=True, dash=True)
                tick(border_west + im_width_mm, page_height - border_south, e=True, dash=True)

            # tick(page_width - border_east, border_north, n=True, e=True)
            # tick(page_width - border_east, page_height - border_south, e=True, s=True)
            image.save('{}/{}.png'.format(dirpath, coords))
            pdf.image('{}/{}.png'.format(dirpath, coords), border_west, border_north, im_width / ppm,
                      im_height / ppm)
    pdf.output(pdf_filename, 'F')
    logging.info('make_pdf: Wrote {} images to PDF file {}'.format(len(images['images']), pdf_filename))


def extract_images_from_pdf(pdf_filename: str, page=None, to_page=None, min_width=100, min_height=100):
    """
    Pull images out of a PDF file by page range, including finding any SMask elements and applying them
    as alpha channels. Technique taken from this stackoverflow post :
    https://stackoverflow.com/questions/56374258/extracting-images-from-pdf-using-python

    :param pdf_filename:
        Filename of the PDF to read
    :param page:
        Start page, defaults to 0
    :param to_page:
        End page, used in a range so the pages scanned will be page to to_page-1 inclusive. Defaults
        to the length of the PDF file
    :param min_width:
        Minimum width in pixels, below this images are rejected
    :param min_height:
        Minimum height in pixels, below this images are rejected
    :return:
        A generate of images from this PDF
    """

    def image_from_vobj(vobj, image_format='RGB'):
        """
        This isn't an ideal method, it seems to have to ignore a lot of exceptions and assertion failures
        for some older PDF documents. It should, however, manage to extract most available images.

        :param vobj:
        :param image_format:
        :return:
        """
        if vobj['/Filter'] == '/FlateDecode':
            # A raw bitmap
            try:
                buf = vobj.getData()
                # Notice that we need metadata from the object
                # so we can make sense of the image data
                size = tuple(map(int, (vobj['/Width'], vobj['/Height'])))
                try:
                    if isinstance(buf, str):
                        i = Image.frombytes(image_format, size, bytes(buf, 'UTF-8'), decoder_name='raw')
                    else:
                        i = Image.frombytes(image_format, size, buf, decoder_name='raw')
                    return i
                except ValueError as ve:
                    # We don't care about non-RGB images in this case
                    pass
                except TypeError as te:
                    # Sometimes buf is a string, pretty sure this is wrong but hey
                    pass
            except AssertionError:
                # Seems to come up with some older PDFs, possibly when trying to interpret mask images
                pass
        elif vobj['/Filter'] == '/DCTDecode':
            # A compressed image
            return Image.open(io.BytesIO(vobj._data))

    def images_in_page(pdf_page):
        # Find the Resources block and look for images, or things into which we can recurse
        r = pdf_page['/Resources']
        if '/XObject' in r:
            for k, v in r['/XObject'].items():
                vobj = v.getObject()
                if vobj['/Subtype'] != '/Image' or '/Filter' not in vobj:
                    # Reject things that aren't images but recurse into groups
                    if '/Resources' in vobj and '/Group' in vobj:
                        for sub_image in images_in_page(vobj):
                            if sub_image:
                                yield sub_image
                    continue
                if img := image_from_vobj(vobj):
                    # Find an SMask if available and apply it
                    if mask_img := (image_from_vobj(vobj['/SMask'], image_format='L') if '/SMask' in vobj else None):
                        img.putalpha(mask_img)
                    yield img

    # Read in the PDF file
    in_pdf = pdf.PdfFileReader(pdf_filename)
    # Bug sometimes in PDFs with spaces in their filename (meh, whatever..)
    if in_pdf.isEncrypted:
        in_pdf.decrypt('')
    # Iterate over target page range, and over images in each page
    for page_number in range(max(0, page or 0),
                             min(to_page or in_pdf.getNumPages(), in_pdf.getNumPages())):
        for image in images_in_page(in_pdf.getPage(page_number)):
            width, height = image.size
            if width >= min_width and height >= min_height and image.mode[:3] == 'RGB':
                yield image
