from pyfeats import MartialFlex, read_feat_csv

# Feats known by my Fighter / Occultist, Jakob
feats_jakob = ['combat expertise', 'outflank', 'following step',
               'step up', 'armor proficiency', 'weapon proficiency', 'power attack',
               'simple weapon proficiency', 'martial weapon proficiency', 'shield proficiency',
               'weapon proficiency']

# Feats known by the evil Aspis consortium brawler pregen
feats_aspis = ['combat expertise', 'improved disarm', 'improved dirty trick', 'improved trip',
               'improved unarmed strike', 'toughness', 'weapon focus']

# Get all the feats Jakob could flex to from his current starting point as a Fighter 5 / Occultist 1 with
# given stats.
m = MartialFlex(feats=read_feat_csv(),
                known_feat_names=feats_jakob,
                bab=5, fighter_level=5, monk_level=0, brawler_level=0,
                str_stat=18, con_stat=12, dex_stat=16, wis_stat=9, int_stat=14, cha_stat=7, race='human', deity='gorum')

# Produce markdown format output, this will need a bit of filtering to remove feats we haven't been able to exclude
# automatically, such as monster feats, ones with complicated prerequisites that we couldn't parse etc. In particular
# we tend to end up with a bunch of mesmerist stare feats, it might be worth actually coding this explicitly.
#
# For Jakob we include teamwork feats as he's an Eldritch Guardian and his raccoon shares any combat feats he has!
print('\n'.join(
    [feat.markdown for feat in sorted(m.get_flex_tree(depth=1, include_no_deps=False, include_teamwork=True))]))
