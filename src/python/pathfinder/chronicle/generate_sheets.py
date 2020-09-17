import logging
from argparse import ArgumentParser
import os
from os.path import abspath
from pathlib import Path
from pathfinder.utils import Config

from pathfinder.chronicle import *

logging.basicConfig(level=logging.INFO)

conf = Config()

parser = ArgumentParser()
parser.add_argument('scenario_pdf', type=str, help='fetch chronicle sheet from INPUT_PDF')
parser.add_argument('output_dir', nargs='?', type=str,
                    help='write sheets to OUTPUT_DIR, will be created if not found, ' +
                         'if not specified, will use chronicle-sheets alongside the input scenario PDF.',
                    default=None)
parser.add_argument('-s', '--season', type=int, help='Explicitly set the season, normally we can auto-detect this',
                    default=0)
parser.add_argument('-t', '--title', type=str, help='Set the title, otherwise pulled from chronicle metadata', default=None)


def main():
    options = parser.parse_args()
    season = options.season
    input_filename = abspath(options.scenario_pdf)
    if options.output_dir is None:
        output_dir = f'{os.path.dirname(input_filename)}/chronicle-sheets'
    else:
        output_dir = abspath(options.output_dir)
    if not Path(output_dir).exists():
        logging.info('Creating new output directory {}'.format(output_dir))
        os.makedirs(output_dir)
    scenario_title, scenario_season, scenario_number = chronicle_info(input_filename)
    if options.title is not None:
        file_prefix = options.title
    else:
        file_prefix = f'{scenario_season}-{scenario_number}'
    for p in parse_reporting_sheet(sheet_export_url=conf.sheets_url):
        logging.info(f'Creating sheet for {p.player_name} - {p.character_name}')
        # Non-specified day-job rolls are strings and can't be parsed as ints
        if p.dayjob_roll == '':
            dayjob = None
        else:
            dayjob = p.dayjob_roll
        annotate_chronicle_sheet(
            input_filename=input_filename,
            output_filename=f'{output_dir}/{file_prefix} {p.player_name}.pdf',
            season=season,
            annotation_functions=[
                # show_cells(),
                player(player_name=p.player_name, character_name=p.character_name,
                       player_number=p.pfs_number, character_number=p.character_number, faction=p.faction),
                tier(tier=p.tier, slow=(p.slow == 'Y')),
                xp(xp_gained=p.xp),
                prestige(prestige_gained=p.prestige),
                gold_and_day_job(gp_gained=p.gold, roll=dayjob),
                event(event_name=p.event_name,
                      event_code=p.event_code, game_date=p.date),
                gm(signature_filename=f'{conf.dir}/signature.png',
                   initials_filename=f'{conf.dir}/initials.png',
                   gm_number=p.gm_number),
                notes(top=p.notes)])
