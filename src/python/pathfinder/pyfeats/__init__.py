import csv
import re
import textwrap
from dataclasses import dataclass, field
from os.path import isfile
from typing import List, Optional
from urllib.request import urlretrieve

import requests
from pydotplus.graphviz import Node, Edge, Dot

DEFAULT_FEAT_URL = \
    'https://docs.google.com/spreadsheets/d/1XqQO21AyE2WtLwW0wSjA9ov74A9tmJmVJjrhPK54JHQ/export?format=csv'

CACHE_FILE_NAME = 'pathfinder_feats.csv'


def read_feat_csv(csv_url: str = DEFAULT_FEAT_URL, cache_feats=True) -> 'FeatDict':
    """
    Read in the feat spreadsheet as a CSV and parse it, extracting all non-mythic feats into a dict of feat objects. If
    run with cache_feats set to true (the default) it will first look for a file 'pathfinder_feats.csv' in the current
    working directory. If it finds it, it will use that instead of the download - if absent and set to true this will
    create the file, subsequent invocations will then use it.

    :param csv_url:
        Fully qualified URL of the feat CSV. By default this directs to the google sheet for the OGL content, but you
        can override this here.
    :param cache_feats:
        Boolean flag, if set to true then this will use a cached copy of the feat CSV if available, and populate the
        cache if not. If set to false it ignores caching entirely - downloading the feat CSV every time and not touching
        the cached copy if any.

    :return: a dict of feat name to Feat
    """

    def build_feat_dict(reader) -> 'FeatDict':
        # Skip the header row
        reader.__next__()

        def deity(prerequisites) -> Optional[str]:
            m = re.search(r'worshiper of (\w+)', prerequisites.lower())
            if m is not None:
                return m.group(1)
            return None

        def find_attributes(prerequisites) -> {}:
            """
            Read in the prerequisites string, and construct a dict containing minimum attribute requirements
            for each of the six basic attributes if we detect any of these. Always returns a dict containing
            every single attribute, if no requirement is specified they're set to 0.

            :param prerequisites:
                String containing expressions like 'STR 18' (case insensitive). Also detects the longer form, i.e.
                'Strength 18' as some of the source data includes these (probably wrong) specifications
            :return:
                Dict containing str, con, dex, wis, int, cha as keys and integer values representing the minimum
                value for each attribute required to use the feat with the specified prerequisite string
            """
            requirements = {'str': 0, 'dex': 0, 'con': 0, 'wis': 0, 'cha': 0, 'int': 0}
            for attr in ['strength', 'constitution', 'dexterity', 'wisdom', 'charisma', 'intelligence']:
                short_attr = attr[:3]
                m = re.search(short_attr + r' ?(\d+)', prerequisites.lower())
                if m is not None:
                    requirements[short_attr] = int(m.group(1))
                else:
                    m = re.search(attr + r' ?(\d+)', prerequisites.lower())
                    if m is not None:
                        requirements[short_attr] = int(m.group(1))
            return requirements

        def level_requirements(prerequisites) -> {}:
            """
            Read in the prerequisites string and work out any requirements specified for BAB, and for levels in any of
            the Fighter, Monk, and Brawler classes.

            :param prerequisites:
                String containing expressions like 'fighter level 12' or '12th-level fighter' for class levels, or 'base
                attack bonus 5' for BAB (case insensitive)
            :return:
                Dict containing keys 'fighter', 'monk', 'brawler', 'bab' with values either None for no requirement
                specified, or an int to indicate that at least that level or BAB is required for the feat to be usable.
            """
            requirements = {}

            def find_requirement(requirement_name: str, requirement_regex: str):
                m = re.search(requirement_regex, prerequisites.lower())
                if m is not None:
                    requirements[requirement_name] = int(m.group(1))
                else:
                    requirements[requirement_name] = None

            find_requirement('bab', r'base attack bonus \+?(\d+)')
            find_requirement('fighter', r'fighter level (\d+)')
            find_requirement('monk', r'monk level (\d+)')
            find_requirement('brawler', r'brawler level (\d+)')

            # check for alternative (wrong) form of level specification
            if requirements['fighter'] is None:
                m = re.search(r'(\d+)th-level fighter', prerequisites.lower())
                if m is not None:
                    requirements['fighter'] = int(m.group(1))
            if requirements['monk'] is None:
                m = re.search(r'(\d+)th-level monk', prerequisites.lower())
                if m is not None:
                    requirements['monk'] = int(m.group(1))
            return requirements

        def fix_name(name):
            if name == 'Tandemevasion':
                return 'Tandem Evasion'
            elif name == 'Leapf Rog':
                return 'Leap Frog'
            return name

        def build_feat(row):
            """
            Build a Feat for a given CSV row

            :param row:
                The row extracted from the CSV file, represented as a tuple
            :return:
                A Feat for this row
            """
            feat_id, name, feat_type, description, prerequisites, prerequisite_feats, benefit, normal, special, \
            source, fulltext, is_teamwork, critical, grit, style, performance, racial, companion_familiar, race_name, \
            note, goal, completion_benefit, multiples, suggested_traits, prerequisite_skills, panache, betrayal, \
            targeting, esoteric, stare, weapon_mastery, item_mastery, armor_mastery, shield_mastery, blood_hex, trick \
                = row
            # Extract all the fields in case we need them at some point
            return Feat(id=feat_id, name=fix_name(name), types=feat_type.lower().split(','), description=description,
                        fulltext=benefit, prerequisites=prerequisites, prerequisite_feats=prerequisite_feats,
                        attribute_requirements=find_attributes(prerequisites),
                        level_requirements=level_requirements(prerequisites), is_teamwork=(int(is_teamwork) == 1),
                        racial=int(racial) == 1, race_name=race_name, deity=deity(prerequisites))

        # Build a dict from compound name to Feat object for all feats other than mythic ones, PFS won't use them and
        # they just confuse the matching system
        feats = FeatDict(
            (feat.compound_name.lower(), feat) for feat in [build_feat(row) for row in reader if row[2] != 'Mythic'])

        def build_dummy_feat(id: int, name: str, description: str):
            """
            We need dummy feats for weapon and shield proficiencies so we can depend on them from other feats. This
            function constructs such feats.

            :param id:
                ID to assign
            :param name:
                Name to use
            :param description:
                Description, also used for fulltext
            :return:
                The generated Feat
            """
            return Feat(id=id, name=fix_name(name), description=description, fulltext=description, prerequisites='',
                        prerequisite_feats='',
                        attribute_requirements={'str': 0, 'dex': 0, 'con': 0, 'wis': 0, 'cha': 0, 'int': 0},
                        level_requirements={'bab': None, 'monk': None, 'fighter': None, 'brawler': None},
                        types=['combat'], is_teamwork=False, racial=False, race_name='', deity=None)

        # Add in dummy feats for dependencies on Weapon Proficiency and Shield Proficiency
        feats['weapon proficiency'] = build_dummy_feat(id=100001, name='Weapon Proficiency',
                                                       description='You are proficient in a given weapon')
        feats['shield proficiency'] = build_dummy_feat(id=100002, name='Shield Proficiency',
                                                       description='You are proficient in a given shield')

        # Scan dependencies and build a graph structure by adding to the parent and child lists in the Feat objects
        for feat_name, feat in feats.items():
            if feat.prerequisite_feats:
                for required_feat_raw in re.split(r'[,|]| or ', feat.prerequisite_feats):
                    if required_feat_raw and required_feat_raw.strip().lower() not in ['evasion', 'sleight of hand',
                                                                                       'spiked gauntlet)', 'bluff',
                                                                                       'diplomacy',
                                                                                       'knowledge (planes) 3',
                                                                                       'enhanced morale']:
                        required_feat = feats.get_feat(required_feat_raw.strip().lower())
                        feat.parents.append(required_feat)
                        required_feat.children.append(feat)

        feats.root_feats = list([feat for feat_name, feat in feats.items() if len(feat.parents) == 0])

        # Extra dependencies that aren't properly supplied in the source data
        def add_dependencies(dependent_feat_name, *dependency_names):
            target_feat = feats.get_feat(dependent_feat_name)
            target_feat.parents.extend([feats.get_feat(dependency_name) for dependency_name in dependency_names])

        add_dependencies('steady engagement', 'stand still')
        add_dependencies('witchbreaker', 'iron will')
        add_dependencies('two-weapon grace', 'two-weapon fighting', 'weapon finesse')
        add_dependencies('tandem evasion', 'dodge')
        add_dependencies('spear dancer', 'weapon focus')
        add_dependencies('masterful display', 'dazzling display')
        add_dependencies('gravitational vital strike', 'vital strike')

        return feats

    if not cache_feats:
        response = requests.get(csv_url)
        reader = csv.reader(response.content.decode('utf-8').splitlines(), delimiter=',')
        return build_feat_dict(reader)
    else:
        if not isfile(CACHE_FILE_NAME):
            urlretrieve(csv_url, CACHE_FILE_NAME)
        with open(CACHE_FILE_NAME) as file:
            return build_feat_dict(csv.reader(file, delimiter=','))


def traverse(selected_feats: ['Feat'], traverse_parents=False, traverse_children=False) -> ['Feat']:
    # Traverse the entire graph, finding all nodes attached to any nodes in the selected_feats input nodes
    found_nodes = []

    def adjacent(edge_nodes):
        new_edges = []
        for node in edge_nodes:
            if traverse_parents:
                for parent in node.parents:
                    if parent not in new_edges and parent not in found_nodes and parent not in edge_nodes:
                        new_edges.append(parent)
            if traverse_children:
                for child in node.children:
                    if child not in new_edges and child not in found_nodes and child not in edge_nodes:
                        new_edges.append(child)
        return new_edges

    while True:
        new_feats = adjacent(selected_feats)
        found_nodes = found_nodes + selected_feats
        selected_feats = new_feats
        if not new_feats:
            break

    return found_nodes


def can_flex(feat: 'Feat', known_feats: ['Feat'], bab=0, fighter_level=0, monk_level=0,
             brawler_level=0, str_stat=0, con_stat=0, dex_stat=0, wis_stat=0, int_stat=0, cha_stat=0, race=None,
             deity=None):
    """
    Return whether a feat is eligible for selection as a target for martial flexibility

    :param feat:
        The feat to check
    :param known_feats:
        A list of currently known feats
    :param bab:
        Base attack bonus (defaults to 0). If this is lower than the sum of monk, brawler, and fighter levels it's
        assumed to be equal to that sum on the basis that these are all full BAB classes
    :param fighter_level:
        Number of fighter class levels (defaults to 0)
    :param monk_level:
        Number of monk class levels (defaults to 0)
    :param brawler_level:
        Number of brawler class levels (defaults to 0)
    :param str_stat:
        Strength attribute (defaults to 0)
    :param con_stat:
        Constitution attribute (defaults to 0)
    :param dex_stat:
        Dexterity attribute (defaults to 0)
    :param wis_stat:
        Wisdom attribute (defaults to 0)
    :param int_stat:
        Intelligence attribute. If this is lower than 13 and any brawler levels higher than zero are specified this is
        treated as 13 due to brawler's cunning (defaults to 0)
    :param cha_stat:
        Charisma attribute (defaults to 0)
    :param race:
        If non-None, and the feat's race_name is also not None, fail if they don't match
    :param deity:
        If non-None, and the feat's deity is also non-None, fail if they don't match
    :return:
        True if the feat is eligible, false otherwise
    """

    # Can only flex to combat feats
    if not feat.combat:
        return False
    # Exclude anything we already know
    if feat in known_feats:
        return False
    # Exclude anything for which we don't have a required ancestor
    if not all([ancestor in known_feats for ancestor in feat.ancestors]):
        return False
    # Exclude anything for which we don't have a required BAB or class level, we only need one of these to pass
    levels = feat.level_requirements
    if not all([levels['fighter'] is None or fighter_level >= levels['fighter'],
                levels['monk'] is None or monk_level >= feat.level_requirements['monk'],
                levels['brawler'] is None or brawler_level >= feat.level_requirements['brawler'],
                levels['bab'] is None or max(bab, fighter_level + monk_level + brawler_level) >=
                feat.level_requirements[
                    'bab']]):
        return False
    # Exclude anything that requires a higher attribute than we have
    if not all([str_stat >= feat.attribute_requirements['str'],
                con_stat >= feat.attribute_requirements['con'],
                dex_stat >= feat.attribute_requirements['dex'],
                wis_stat >= feat.attribute_requirements['wis'],
                # Apply brawler's cunning if necessary
                int_stat >= feat.attribute_requirements['int'] or (
                        brawler_level > 0 and 13 >= feat.attribute_requirements['int']),
                cha_stat >= feat.attribute_requirements['cha']
                ]):
        return False
    # If we defined a race, exclude any racial feats that aren't for this race
    if race is not None:
        if feat.racial:
            races = [x.strip() for x in feat.race_name.lower().split(',')]
            if race.lower() not in races:
                return False
    # If we defined a deity and the feat also specifies one, only pass if they match
    if deity is not None:
        if feat.deity is not None:
            if deity.lower() != feat.deity.lower():
                return False
    return True


def martial_flex(feats: 'FeatDict', known_feats: ['Feat'], exclusions=None, bab=0, fighter_level=0, monk_level=0,
                 brawler_level=0, str_stat=0, con_stat=0, dex_stat=0, wis_stat=0, int_stat=0, cha_stat=0,
                 include_no_deps=False, include_teamwork=False, race=None, deity=None):
    """
    Return a list of feats that aren't in the list of existing feats but for which we have all the prerequisite feats.

    :param feats:
        A :class:`~pyfeats.FeatDict` containing all known feats
    :param known_feats:
        A list of :class:`~pyfeats.Feat` which we already know
    :param exclusions:
        A list of :class:`~pyfeats.Feat` which will never be included in the output, or None (default) to ignore
    :param bab:
        Base attack bonus (defaults to 0)
    :param fighter_level:
        Number of fighter class levels (defaults to 0)
    :param monk_level:
        Number of monk class levels (defaults to 0)
    :param brawler_level:
        Number of brawler class levels (defaults to 0)
    :param str_stat:
        Strength attribute (defaults to 0)
    :param con_stat:
        Constitution attribute (defaults to 0)
    :param dex_stat:
        Dexterity attribute (defaults to 0)
    :param wis_stat:
        Wisdom attribute (defaults to 0)
    :param int_stat:
        Intelligence attribute. If this is lower than 13 and any brawler levels higher than zero are specified this is
        treated as 13 due to brawler's cunning (defaults to 0)
    :param cha_stat:
        Charisma attribute (defaults to 0)
    :param include_no_deps:
        Set this to True to include feats with no dependencies. This can introduce a lot of noise, and defaults to False
        so we only see feats which are natural extensions to the ones we already have. This obviously does miss out on
        some perfectly sensible options.
    :param include_teamwork:
        Set this to true to show teamwork feats, defaults to False
    :param race:
        Set this to non-null to include only racial abilities from the specified race
    :param deity:
        Set this to non-null to include only feats eligible for worshippers of the specific deity
    :return:
        An iterable of :class:`~pyfeats.Feat` to which we could potentially flex
    """

    def valid_feat(feat: 'Feat') -> bool:
        if not include_no_deps and len(feat.ancestors) == 0:
            return False
        if not include_teamwork and feat.teamwork:
            return False
        if exclusions is not None and feat in exclusions:
            return False
        return can_flex(feat=feat, known_feats=known_feats, bab=bab, fighter_level=fighter_level, monk_level=monk_level,
                        brawler_level=brawler_level, str_stat=str_stat, con_stat=con_stat, dex_stat=dex_stat,
                        wis_stat=wis_stat, int_stat=int_stat, cha_stat=cha_stat, race=race, deity=deity)

    candidate_child_feats = set([val for sublist in [feat.children for feat in known_feats] for val in sublist])

    if include_no_deps:
        candidate_child_feats.update(feats.root_feats)

    return [feat for feat in candidate_child_feats if valid_feat(feat)]


class FeatDict(dict):
    """
    Subclass of dict which contains a dict of Feats along with methods to interrogate itself, searching for feats by
    name, removing dependencies implied by transitivity etc.
    """

    def __init__(self, internal_dict):
        super(FeatDict, self).__init__(internal_dict)
        self.root_feats = []

    def find(self, regex: str) -> ['Feat']:
        pattern = re.compile(regex.lower().strip())
        return list(self[key] for key in self if pattern.match(key))

    def graph(self, regex: str, children=True) -> Dot:
        """
        Produce a Dot format graph object which can be used to render all feats matching the specified name regex.

        :param regex:
            Regex to specify feats
        :param children:
            Set to true to show feats which depend on the selected feats, false to only show their dependencies.
        :return:
            A graph object that can be rendered by the dot tool from graphviz
        """
        g = Dot(rankdir='LR', ranksep=0.8, nodesep=0.2, splines='false')
        g.set_node_defaults(fontname='font-awesome', fontsize=12, style='rounded, filled', fillcolor='azure2',
                            color='none')
        for feat in self.simplify(
                traverse(traverse(self.find(regex), traverse_children=children), traverse_parents=True)):
            g.add_node(feat.node)
            for e in feat.parent_edges:
                g.add_edge(e)
        return g

    @staticmethod
    def simplify(selected_feats: ['Feat']) -> ['Feat']:
        """
        Given a set of feats, remove dependencies implied by transitivity
        """
        finished = False
        while not finished:
            finished = True
            for feat in selected_feats:
                for parent in feat.parents:
                    for check in feat.parents:
                        if parent in check.ancestors:
                            if parent in feat.parents:
                                feat.parents.remove(parent)
                                parent.children.remove(feat)
                                finished = False
        return selected_feats

    def get_feat(self, feat_name: str) -> 'Feat':
        """
        Retrieve a feat with a given name. This fixes various aliases / miss-spellings in the source data, as well as
        those which are specialised e.g. weapon focus (longsword) will map to weapon focus. We use this because we have
        no support for specialisation of feats in this way - this produces some false positives in terms of traversal
        as we can't express that a particular feat requires e.g. weapon focus (spear) rather than any weapon focus, but
        it also avoids the problem that were we to make every possible combination available we'd have a stupidly large
        and unmanageable graph for those feats.

        :param feat_name:
            Input feat name
        :return:
            Feat matching the name, after any adjustments have been applied
        """
        if re.match('spell focus*', feat_name.lower()):
            return self['spell focus']
        elif re.match('skill focus*', feat_name.lower()):
            return self['skill focus']
        elif re.match('weapon focus*', feat_name.lower()):
            return self['weapon focus']
        elif re.match('exotic weapon proficiency*', feat_name.lower()):
            return self['exotic weapon proficiency']
        elif re.match('weapon proficiency*', feat_name.lower()):
            return self['weapon proficiency']
        elif re.match('shield proficiency*', feat_name.lower()):
            return self['shield proficiency']
        elif re.match('weapon specialization*', feat_name.lower()):
            return self['weapon specialization']
        elif re.match('combat expertise*', feat_name.lower()):
            return self['combat expertise']
        elif re.match('associate \(*', feat_name.lower()):
            return self['associate']
        elif feat_name == 'point blank shot':
            return self['point-blank shot']
        elif feat_name == 'close quarters thrower':
            return self['close-quarters thrower']
        elif feat_name == 'point-blank master':
            return self['point blank master']
        elif feat_name == 'siege weapon engineer':
            return self['siege engineer']
        elif feat_name == 'surprise follow through':
            return self['surprise follow-through']
        elif feat_name == 'fiendish darknes':
            return self['fiendish darkness']
        elif feat_name == 'meditation maste':
            return self['meditation master']
        elif feat_name == 'augmented summoning':
            return self['augment summoning']
        elif feat_name == 'step-up':
            return self['step up']
        elif feat_name == 'compelling harmony':
            return self['compelling harmonies']
        elif feat_name == 'awareness':
            return self['alertness']
        elif feat_name == 'blinded blade precision':
            return self['blinded competence']
        elif feat_name == 'acrobatics':
            return self['acrobatic']
        elif feat_name == 'mproved grapple':
            return self['improved grapple']
        elif feat_name == 'tandemevasion':
            return self['tandem evasion']
        return self[feat_name]


NODE_LABEL = """<
<table border="0" cellborder="0" cellspacing="0">
    <tr><td align="left"><b><font color="grey10">{name}</font></b></td></tr>
    <tr><td><font point-size="10" color="grey14">{dependencies}</font></td></tr>
</table>
>"""

NODE_LABEL_NO_PRE = """<
<table border="0" cellborder="0" cellspacing="0">
    <tr><td align="left"><b><font color="grey10">{name}</font></b></td></tr>
</table>
>"""


@dataclass
class Feat:
    """Class to represent a single feat"""
    id: int
    name: str
    types: List[str]
    description: str
    fulltext: str
    prerequisites: str
    prerequisite_feats: str
    parents: List['Feat'] = field(default_factory=list, init=False)
    children: List['Feat'] = field(default_factory=list, init=False, repr=False)
    attribute_requirements: {}
    level_requirements: {}
    is_teamwork: bool
    racial: bool
    race_name: str
    deity: Optional[str]

    @property
    def compound_name(self) -> str:
        if 'Mythic' in self.types:
            return self.name + ' (Mythic)'
        else:
            return self.name

    @property
    def node(self) -> Node:
        filtered_prerequisites = list(
            [prereq.strip() for prereq in self.prerequisites.strip().rstrip('.').split(',') if
             prereq.strip() not in list([ancestor.name for ancestor in self.ancestors])])
        label = NODE_LABEL.format(name=self.name, dependencies="<br/>".join(filtered_prerequisites))
        if not ''.join(filtered_prerequisites):
            label = NODE_LABEL_NO_PRE.format(name=self.name)
        colour = 'azure2'
        if self.combat:
            colour = 'palegoldenrod'
        elif self.teamwork:
            colour = 'palegreen2'
        return Node(name=self.id, label=label, shape='polygon', sides=4, fillcolor=colour)

    @property
    def parent_edges(self) -> [Edge]:
        return list([Edge(dst=self.id, src=parent.id, tailport='e', headport='w') for parent in self.parents])

    @property
    def ancestors(self) -> [Edge]:
        nodes = traverse([self], traverse_parents=True)
        nodes.remove(self)
        return nodes

    @property
    def combat(self):
        return 'combat' in self.types

    @property
    def teamwork(self):
        return self.is_teamwork or 'teamwork' in self.types

    def wrapped_fulltext(self, width=100, indent='\t', newline='\n'):
        lines = textwrap.wrap(self.fulltext, width - len(indent))
        return newline.join([f'{indent}{line}' for line in lines])

    def __hash__(self):
        return self.name.__hash__()

    def __lt__(self, other):
        return self.name.__lt__(other.name)

    def __le__(self, other):
        return self.name.__le__(other.name)

    def __gt__(self, other):
        return self.name.__gt__(other.name)

    def __ge__(self, other):
        return self.name.__ge__(other.name)


class MartialFlex:
    """
    Represents the ability to flex to combat feats on the fly. On construction you provide a FeatDict to retrieve all
    known feats, the names of feats the character already knows, the character's Base Attack Bonus and any levels in
    Fighter, Monk, or Brawler the character has along with the character's stat block and, optionally, race. The class
    then allows you to search for feats which are candidates for the martial flex ability, including those cases where
    the character can flex to multiple feats where one of the new feats is a prerequisite of one of the others.
    """

    def __init__(self, feats, known_feat_names, bab=0, fighter_level=0, monk_level=0,
                 brawler_level=0, str_stat=0, con_stat=0, dex_stat=0, wis_stat=0, int_stat=0, cha_stat=0, race=None,
                 deity=None):
        """
        :param feats:
            a FeatDict containing all known feats
        :param known_feat_names:
            Array of names of feats the character already knows
        :param bab:
            BAB, 0 if not specified
        :param fighter_level:
            Number of levels in Fighter, 0 if not specified
        :param monk_level:
            Number of levels in Monk, 0 if not specified
        :param brawler_level:
            Number of levels in Brawler, 0 if not specified
        :param str_stat:
            STR, 0 if not specified
        :param con_stat:
            CON, 0 if not specified
        :param dex_stat:
            DEX, 0 if not specified
        :param wis_stat:
            WIS, 0 if not specified
        :param int_stat:
            INT, 0 if not specified
        :param cha_stat:
            CHA, 0 if not specified
        :param race:
            Race, i.e. 'human', if you don't want to filter on race just don't specify
        :param deity:
            Worshiped deity, or defaults to None to not specify
        """
        self.feats = feats
        self.known_feats = self.feats.find('|'.join([f'{name}$' for name in known_feat_names]))
        self.bab = bab
        self.fighter_level = fighter_level
        self.monk_level = monk_level
        self.brawler_level = brawler_level
        self.str_stat = str_stat
        self.con_stat = con_stat
        self.dex_stat = dex_stat
        self.wis_stat = wis_stat
        self.int_stat = int_stat
        self.cha_stat = cha_stat
        self.race = race
        self.deity = deity

    def get_flex_feats(self, known_feats, exclusions=None, include_no_deps=False, include_teamwork=False):
        return list(martial_flex(feats=self.feats, known_feats=known_feats, exclusions=exclusions, bab=self.bab,
                                 fighter_level=self.fighter_level, monk_level=self.monk_level,
                                 brawler_level=self.brawler_level, include_no_deps=include_no_deps,
                                 include_teamwork=include_teamwork, str_stat=self.str_stat, con_stat=self.con_stat,
                                 dex_stat=self.dex_stat, wis_stat=self.wis_stat, int_stat=self.int_stat,
                                 cha_stat=self.cha_stat, race=self.race, deity=self.deity))

    def get_flex_tree(self, include_no_deps=False, include_teamwork=False, depth=1):
        root_nodes = [MartialFlex.FlexFeat(feat=feat, parent=None, children=None) for feat in self.get_flex_feats(
            self.known_feats, include_teamwork=include_teamwork, include_no_deps=include_no_deps)]

        def edge_nodes():
            edges = []

            def add_all_edges(flex_feat):
                if flex_feat.children is None:
                    edges.append(flex_feat)
                else:
                    for child in flex_feat.children:
                        add_all_edges(child)

            for node in root_nodes:
                add_all_edges(node)

            return edges

        for _ in range(depth - 1):
            for flex_node in edge_nodes():
                exclusions = self.get_flex_feats(self.known_feats + flex_node.parents, include_no_deps=False,
                                                 include_teamwork=include_teamwork)
                flex_node.children = [MartialFlex.FlexFeat(feat=flex_feat, parent=flex_node, children=None) for
                                      flex_feat in
                                      self.get_flex_feats(self.known_feats + [flex_node.feat],
                                                          include_no_deps=False,
                                                          include_teamwork=include_teamwork,
                                                          exclusions=exclusions,
                                                          )]
        return root_nodes

    @dataclass
    class FlexFeat:
        """
        A class wrapping a Feat along with the parent FlexFeat and any children. Parents and children for this class are
        not the same as for the underlying Feat - here they represent the chain of martial flexes that led to this feat
        being available. So for the first flex, there's no parent. Any children of that node represent new options that
        weren't available before if we first flex to that node, and only apply when you have the option to perform more
        than a single flex.

        Total order over feat name.
        """
        feat: Feat
        parent: Optional['MartialFlex.FlexFeat']
        children: ['MartialFlex.FlexFeat'] = None

        @property
        def parents(self):
            """
            Array of FlexFeat to which the character had previously flexed to allow this FlexFeat to become an option.

            :return:
                Array of FlexFeat - if there are no parents this is an empty array rather than None
            """
            if self.parent is None:
                return []
            else:
                return [self.parent] + self.parent.parents

        @property
        def markdown(self):
            return self._inner_markdown()

        @property
        def text(self):
            """
            Formats the name, prerequisites, and description of the feat and any of its children

            :return:
                A rendered string for this feat and any of its flex children
            """
            return self._inner_text()

        def __lt__(self, other):
            return self.feat.name.__lt__(other.feat.name)

        def __le__(self, other):
            return self.feat.name.__le__(other.feat.name)

        def __gt__(self, other):
            return self.feat.name.__gt__(other.feat.name)

        def __ge__(self, other):
            return self.feat.name.__ge__(other.feat.name)

        def _inner_text(self, indent=0):

            def _feat_text(feat, indent=0):
                requirement_names = list(requirement.name for requirement in feat.ancestors)
                name = feat.name
                if feat.teamwork:
                    name = f'{name} (t)'
                if feat.prerequisites is '':
                    lines = f'{name}\n{feat.wrapped_fulltext()}'.split('\n')
                else:
                    lines = f'{name} <- {requirement_names} : requires {feat.prerequisites}\n{feat.wrapped_fulltext()}'.split(
                        '\n')

                indent_string = '\t' * indent
                return '\n'.join([f'{indent_string}{line}' for line in lines]) + '\n'

            if self.children is None or len(self.children) == 0:
                return _feat_text(self.feat, indent)
            else:
                return _feat_text(self.feat, indent) + '\n' + '\n'.join(
                    [child._inner_text(indent=indent + 1) for child in sorted(self.children)])

        def _inner_markdown(self, indent=0):

            def _feat_text(feat, indent=0):
                requirement_names = list(requirement.name for requirement in feat.ancestors)
                name = feat.name
                if feat.teamwork:
                    name = f'{name} (t)'
                if feat.prerequisites is '':
                    lines = f'**{name}**\n\n*{feat.fulltext}*'.split('\n')
                else:
                    lines = f'**{name}**: requires {feat.prerequisites}\n\n*{feat.fulltext}*'.split(
                        '\n')

                indent_string = '  ' * indent
                text = '\n'.join([f'{indent_string}{line}' for line in lines]) + '\n'
                if indent > 0:
                    text = '+'+text[(2*indent)-1:]
                return text

            if self.children is None or len(self.children) == 0:
                return _feat_text(self.feat, indent)
            else:
                return _feat_text(self.feat, indent) + '\n' + '\n'.join(
                    [child._inner_markdown(indent=indent + 1) for child in sorted(self.children)])