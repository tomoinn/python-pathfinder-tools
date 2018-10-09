import csv
import re
from dataclasses import dataclass, field
from typing import List

import requests
from pydotplus.graphviz import Node, Edge, Dot

DEFAULT_FEAT_URL = \
    'https://docs.google.com/spreadsheets/d/1XqQO21AyE2WtLwW0wSjA9ov74A9tmJmVJjrhPK54JHQ/export?format=csv'


def read_feat_csv(csv_url=DEFAULT_FEAT_URL) -> 'FeatDict':
    """
    Read in the feat spreadsheet as a CSV and parse it, extracting all non-mythic feats into a dict of feat objects

    :return: a dict of feat name to Feat
    """
    response = requests.get(csv_url)
    reader = csv.reader(response.content.decode('utf-8').splitlines(), delimiter=',')
    # Skip the header row
    reader.__next__()

    def build_feat(row):
        feat_id, name, feat_type, description, prerequisites, prerequisite_feats, benefit, normal, special, source, \
        fulltext, teamwork, critical, grit, style, performance, racial, companion_familiar, race_name, note, goal, \
        completion_benefit, multiples, suggested_traits, prerequisite_skills, panache, betrayal, targeting, esoteric, \
        stare, weapon_mastery, item_mastery, armor_mastery, shield_mastery, blood_hex, trick = row
        # Extract all the fields in case we need them at some point
        return Feat(id=feat_id, name=name, type=feat_type, description=description, fulltext=benefit,
                    prerequisites=prerequisites, prerequisite_feats=prerequisite_feats)

    # Build a dict from compound name to Feat object for all feats other than mythic ones, PFS won't use them and they
    # just confuse the matching system
    feats = FeatDict(
        (feat.compound_name.lower(), feat) for feat in [build_feat(row) for row in reader if row[2] != 'Mythic'])

    # Add in dummy feats for dependencies on Weapon Proficiency and Shield Proficiency
    feats['weapon proficiency'] = Feat(id=100001, name='Weapon Proficiency', type='Combat',
                                       description='You are proficient in a given weapon',
                                       fulltext='You are proficient in a given weapon', prerequisite_feats='',
                                       prerequisites='')
    feats['shield proficiency'] = Feat(id=100002, name='Shield Proficiency', type='Combat',
                                       description='You are proficient in a given shield type',
                                       fulltext='You are proficient in a given shield type', prerequisite_feats='',
                                       prerequisites='')

    # Scan dependencies and build a graph structure by adding to the parent and child lists in the Feat objects
    for feat_name, feat in feats.items():
        if feat.prerequisite_feats:
            for required_feat_raw in re.split(r'[,|]| or ', feat.prerequisite_feats):
                if required_feat_raw and required_feat_raw.strip().lower() not in ['evasion', 'sleight of hand',
                                                                                   'spiked gauntlet)', 'bluff',
                                                                                   'diplomacy', 'knowledge (planes) 3',
                                                                                   'enhanced morale']:
                    required_feat = feats.get_feat(required_feat_raw.strip().lower())
                    feat.parents.append(required_feat)
                    required_feat.children.append(feat)

    return feats


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


class FeatDict(dict):

    def find(self, regex: str) -> ['Feat']:
        pattern = re.compile(regex.lower().strip())
        return list(self[key] for key in self if pattern.match(key))

    def graph(self, regex: str, children=True) -> Dot:
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
        # Given a set of feats, remove dependencies implied by transitivity
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
        # Handle oddities like spell and skill focus
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
    type: str
    description: str
    fulltext: str
    prerequisites: str
    prerequisite_feats: str
    parents: List['Feat'] = field(default_factory=list, init=False)
    children: List['Feat'] = field(default_factory=list, init=False, repr=False)

    @property
    def compound_name(self) -> str:
        if self.type == 'Mythic':
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
        if self.type == 'Combat':
            colour = 'palegoldenrod'
        elif self.type == 'Teamwork':
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
