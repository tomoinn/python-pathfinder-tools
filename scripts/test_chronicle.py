from chronicle import *

annotate_chronicle_sheet(
    input_filename='/home/tom/Desktop/Google Drive/Pathfinder/Scenarios/4-03 The Golemworks Incident.pdf',
    output_filename='/home/tom/Desktop/test_output.pdf',
    annotation_functions=[
        # show_cells(),
        player(player_name='Tom', character_name='Ashar Whitemane',
               player_number=329365, character_number=5, faction="Liberty's Edge"),
        tier(tier=1, slow=False),
        xp(starting_xp=10, xp_gained=0.5),
        prestige(initial_prestige=10, initial_fame=13, prestige_gained=2),
        gold(starting_gp=1000, gp_gained=2528, day_job=10, gp_spent=200, items_sold=300),
        event(event_name='Cambridge Lodge',
              event_code=368398),
        gm(signature_filename='/home/tom/Desktop/signature.png',
           initials_filename='/home/tom/Desktop/initials.png',
           gm_number=329365),
        notes(top='Avenger of the Farheavens boon picked, others crossed out.',
              bottom='We could put a note here, if need be')])
