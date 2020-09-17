import datetime
from dataclasses import dataclass
from typing import Generator, Any, List, Optional
import itertools

import dateutil.parser
from bs4 import BeautifulSoup


@dataclass(eq=True, frozen=True, order=True)
class Session:
    """
    Holds a single row from the sessions table representing a single reported pathfinder or starfinder scenario
    """
    date: datetime.datetime
    gm: str
    scenario: str
    points: str
    event_code: int
    event_name: str
    session: int
    player: str
    character: str
    faction: str
    acp_earned: str
    prestige: str
    note: str

    @property
    def was_gm(self) -> bool:
        # Did you GM this game?
        return self.prestige[:2] == 'GM'

    @property
    def character_number(self) -> Optional[int]:
        # Character number, or None if you were the GM (because annoyingly this information isn't included in this case)
        if (pos := self.player.find('-')) >= 0:
            return int(self.player[pos + 1:])
        return None

    @property
    def system(self) -> str:
        # Attempt to figure out which system this session represents, returning one of 'pfs1', 'pfs2', 'sfs'
        if (char := self.character_number) is None:
            # Unknown character number, guess based on the scenario name field
            if self.scenario.find('PFS(2ed)') >= 0:
                return 'pfs2'
            elif self.scenario.find('Starfinder') >= 0:
                return 'sfs'
        else:
            if char >= 2000:
                return 'pfs2'
            elif char >= 200:
                return 'sfs'
        # If all the above fails, assume pfs1
        return 'pfs1'


def parse_sessions(html: str) -> Generator[Session, Any, None]:
    """
    Find the results table from the HTML text, look for rows with enough columns to actually correspond to sessions,
    unmangle the horrors inflicted by Paizo and WebObjects, and return a generator of Session objects with all the
    values safely handled.

    Get the HTML by going to 'my organised play', then 'sessions', and saving the resultant web page. You only need
    the HTML file, not the associated 'page_files' directory.
    """

    def clean_string(s):
        return ' '.join([row.strip() for row in s.strip('\n').strip().split('\n')])

    # Iterate over valid table rows that represent sessions
    # noinspection PyTypeChecker
    def find_sessions():
        for row in BeautifulSoup(html, 'html.parser').find(id='results').find_all('tr'):
            if len(columns := [clean_string(col.text) for col in row.find_all('td')]) == 14:
                columns[0] = dateutil.parser.parse(columns[0])
                columns[4] = int(columns[4])
                columns[6] = int(columns[6])
                yield Session(*columns[:13])

    return find_sessions()


def read_files(*filenames: str) -> List[Session]:
    """
    Read multiple HTML files, remove duplicate sessions and return a list ordered by ascending session date
    """

    def read_file(filename: str) -> Generator[Session, Any, None]:
        with open(filename, 'r') as file:
            return parse_sessions(html=file.read())

    return sorted(set(itertools.chain(*[read_file(filename) for filename in filenames])))
