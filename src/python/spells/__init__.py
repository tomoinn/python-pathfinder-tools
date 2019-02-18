import csv
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import total_ordering
from os.path import isfile
from typing import Tuple, Optional, Set
from urllib.request import urlretrieve

import requests
from fpdf import FPDF

from mapmaker import Paper

DEFAULT_SPELL_URL = \
    'https://docs.google.com/spreadsheets/d/1cuwb3QSvWDD7GG5McdvyyRBpqycYuKMRsXgyrvxvLFI/export?format=csv'

CACHE_FILE_NAME = 'pathfinder_spells.csv'


class School(Enum):
    """
    Spell schools.
    """
    ABJURATION = 0, (157, 166, 236)
    CONJURATION = 1, (238, 187, 247)
    DIVINATION = 2, (217, 173, 255)
    ENCHANTMENT = 3, (201, 236, 149)
    EVOCATION = 4, (242, 144, 140)
    ILLUSION = 5, (244, 180, 143)
    NECROMANCY = 6, (250, 226, 132)
    SIN = 7, (201, 236, 149)
    TRANSMUTATION = 8, (149, 233, 195)
    UNIVERSAL = 9, (154, 222, 242)
    OTHER = 10, (200, 200, 200)

    def __new__(cls, value, colour):
        member = object.__new__(cls)
        member._value_ = value
        member.colour = colour
        return member

    def __int__(self):
        return self.value


class CasterClass(Enum):
    """
    Class casting a given spell. Needed because spells vary in level by class, and because we want to be able
    to build class-specific spell lists using filters.
    """
    SOR = 0, 'Sorceror'
    WIZ = 1, 'Wizard'
    CLERIC = 2, 'Cleric'
    DRUID = 3, 'Druid'
    RANGER = 4, 'Ranger'
    BARD = 5, 'Bard'
    PALADIN = 6, 'Paladin'
    ALCHEMIST = 7, 'Alchemist'
    SUMMONER = 8, 'Summoner'
    WITCH = 9, 'Witch'
    INQUISITOR = 10, 'Inquisitor'
    ORACLE = 11, 'Oracle'
    ANTIPALADIN = 12, 'Antipaladin'
    MAGUS = 13, 'Magus'
    ADEPT = 14, 'Adept'
    BLOODRAGER = 15, 'Bloodrager'
    SHAMAN = 16, 'Shaman'
    PSYCHIC = 17, 'Psychic'
    MEDIUM = 18, 'Medium'
    MESMERIST = 19, 'Mesmerist'
    OCCULTIST = 20, 'Occultist'
    SPIRITUALIST = 21, 'Spriritualist'
    SKALD = 22, 'Skald'
    INVESTIGATOR = 23, 'Investigator'
    HUNTER = 24, 'Hunter'
    SUMMONER_UNCHAINED = 25, 'Summoner (unchained)'

    def __new__(cls, value, name):
        member = object.__new__(cls)
        member._value_ = value
        member.full_name = name
        return member

    def __int__(self):
        return self.value


class Descriptor(Enum):
    """
    Spell descriptor types, spells can have zero or more of these descriptors.
    """
    ACID = auto()
    AIR = auto()
    CHAOTIC = auto()
    COLD = auto()
    CURSE = auto()
    DARKNESS = auto()
    DEATH = auto()
    DISEASE = auto()
    EARTH = auto()
    ELECTRICITY = auto()
    EMOTION = auto()
    EVIL = auto()
    FEAR = auto()
    FIRE = auto()
    FORCE = auto()
    GOOD = auto()
    LANGUAGE_DEPENDENT = auto()
    LAWFUL = auto()
    LIGHT = auto()
    MIND_AFFECTING = auto()
    PAIN = auto()
    POISON = auto()
    SHADOW = auto()
    SONIC = auto()
    WATER = auto()


@dataclass(frozen=True, eq=True)
class SpellMeta:
    """
    Contains complete detail on a single named spell, including the level for all classes that can cast it. These
    are not used directly, instead they are used to create :class:`~spells.Spell` instances in spell lists to match
    a given set of criteria.
    """
    id: int
    name: str
    school: School
    subschool: Optional[str]
    descriptors: Tuple[Descriptor]
    casting_time: str
    components: str
    costly_components: bool
    range: str
    area: str
    effect: str
    targets: str
    duration: str
    dismissible: bool
    shapeable: bool
    saving_throw: str
    spell_resistance: str
    description: str
    source: str
    verbal: bool
    somatic: bool
    material: bool
    focus: bool
    divine_focus: bool
    levels: {CasterClass: int} = field(hash=False)
    haunt_statistics: Optional[str]


@dataclass(frozen=True, eq=True)
@total_ordering
class Spell(SpellMeta):
    caster_class: CasterClass

    @staticmethod
    def from_spell_meta(meta: SpellMeta, caster_class: CasterClass) -> 'Spell':
        if caster_class not in meta.levels:
            raise ValueError(f'Class {caster_class.name} cannot cast {meta.name}')
        return Spell(caster_class=caster_class, **meta.__dict__)

    @property
    def level(self) -> Optional[int]:
        return self.levels[self.caster_class]

    def __lt__(self, other):
        def o(s: 'Spell') -> int:
            return s.caster_class.value * 10 + s.level

        if o(self) == o(other):
            return self.name.__lt__(other.name)
        elif o(self) < o(other):
            return True
        return False


class AllSpells:
    """
    Contains all known spells, loaded from a CSV file
    """

    def __init__(self, csv_url: str = DEFAULT_SPELL_URL, cache_spells=True):

        def build_spell_list(reader):

            def get_int(d: {}, s: str) -> Optional[int]:
                try:
                    return int(d[s])
                except ValueError:
                    return None

            def get_bool(d: {}, s: str) -> bool:
                return d[s] is '1'

            def get_school(d: {}) -> School:
                try:
                    return School[d['school'].upper()]
                except KeyError:
                    return School.OTHER

            # Read the header row
            header = reader.__next__()

            def spell_for_row(row):
                d = {header[i]: row[i] for i in range(len(row))}

                descriptors: Tuple[Descriptor] = tuple([des for des in Descriptor if get_bool(d, des.name.lower())])
                levels = {cc: get_int(d, cc.name.lower()) for cc in CasterClass if
                          get_int(d, cc.name.lower()) is not None}
                return SpellMeta(id=get_int(d, 'id'),
                                 name=d['name'],
                                 school=get_school(d),
                                 subschool=d['subschool'],
                                 descriptors=descriptors,
                                 casting_time=d['casting_time'],
                                 components=d['components'],
                                 costly_components=get_bool(d, 'costly_components'),
                                 range=d['range'],
                                 area=d['area'],
                                 effect=d['effect'],
                                 targets=d['targets'],
                                 duration=d['duration'],
                                 dismissible=get_bool(d, 'dismissible'),
                                 shapeable=get_bool(d, 'shapeable'),
                                 saving_throw=d['saving_throw'],
                                 spell_resistance=d['spell_resistence'],
                                 description=d['description'],
                                 source=d['source'],
                                 verbal=get_bool(d, 'verbal'),
                                 somatic=get_bool(d, 'somatic'),
                                 material=get_bool(d, 'material'),
                                 focus=get_bool(d, 'focus'),
                                 divine_focus=get_bool(d, 'divine_focus'),
                                 levels=levels,
                                 haunt_statistics=d['haunt_statistics']
                                 )

            return list([spell_for_row(row) for row in reader])

        if not cache_spells:
            response = requests.get(csv_url)
            self.all_spells = build_spell_list(csv.reader(response.content.decode('utf-8').splitlines(), delimiter=','))
        else:
            if not isfile(CACHE_FILE_NAME):
                urlretrieve(csv_url, CACHE_FILE_NAME)
            with open(CACHE_FILE_NAME) as file:
                self.all_spells = build_spell_list(csv.reader(file, delimiter=','))

    def find(self, regex: str) -> [SpellMeta]:
        pattern = re.compile(regex.lower().strip())
        return [spell for spell in self.all_spells if pattern.match(spell.name.lower())]


class SpellBook:
    """
    Defines a subset of all available spells, with each spell having a defined caster class and consequent level.
    """

    def __init__(self, all_spells: AllSpells):
        """
        Create a new SpellBook

        :param all_spells:
            The instance of :class:`spells.AllSpells` used to find spells when adding to the spellbook.
        """
        self.all_spells: AllSpells = all_spells
        self.spells: Set[Spell] = set()

    def add_spells(self, caster_class, min_level=0, max_level=9):
        def f(spell_meta) -> Optional[Spell]:
            try:
                spell = Spell.from_spell_meta(spell_meta, caster_class)
                if not (max_level >= spell.level >= min_level):
                    return None
                return spell
            except ValueError:
                return None

        self.spells.update(
            [f(spell_meta) for spell_meta in self.all_spells.all_spells if f(spell_meta) is not None])

    @property
    def spell_names(self) -> [Spell]:
        return [f'{spell.name} ({spell.caster_class.full_name} {spell.level})' for spell in sorted(self.spells)]

    def make_pdf(self, paper_size: Paper = Paper.A4, margin_mm=10, cells_horizontal=3,
                 cells_vertical=3, spacing_mm=5):
        cell_height_mm = (paper_size.height + spacing_mm - 2 * margin_mm) / float(cells_vertical) - spacing_mm
        cell_width_mm = (paper_size.width + spacing_mm - 2 * margin_mm) / float(cells_horizontal) - spacing_mm

        pdf = FPDF(orientation='P', unit='mm', format=paper_size.dimensions)
        pdf.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf', uni=True)

        pdf.set_auto_page_break(auto=False, margin=0.0)

        def get_location(i: int) -> Tuple[int, int, int, int, int]:
            """
            Return (page, x, y, x_mm, y_mm) for card number i, all values indexed at 0
            """
            cells_per_page = cells_horizontal * cells_vertical
            page = i // cells_per_page
            cell_on_page = i % cells_per_page
            x = cell_on_page % cells_horizontal
            y = cell_on_page // cells_horizontal
            return page, x, y, margin_mm + x * (cell_width_mm + spacing_mm), margin_mm + y * (
                    cell_height_mm + spacing_mm)

        for i, spell in enumerate(sorted(self.spells)):
            page, x, y, x_mm, y_mm = get_location(i)
            if x == 0 and y == 0:
                # New page
                pdf.add_page()
            # Draw outline
            pdf.set_fill_color(*spell.school.colour)
            pdf.rect(x_mm, y_mm, cell_width_mm, cell_height_mm, style='F')
            # Move cursor to top left of new card
            pdf.x = x_mm
            pdf.y = y_mm + 5
            pdf.set_font('DejaVu', '', 12)
            pdf.cell(w=cell_width_mm, txt=f'{spell.name} ({spell.level})')
            pdf.set_font('DejaVu', '', 7)
            pdf.x = x_mm
            pdf.y = y_mm + 10
            pdf.multi_cell(w=cell_width_mm, h=3, txt=spell.description, border=0, align='J', fill=False)


        pdf.output('/home/tom/Desktop/test.pdf')
