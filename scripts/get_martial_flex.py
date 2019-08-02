from pyfeats import MartialFlex, read_feat_csv

m = MartialFlex(feats=read_feat_csv(),
                known_feat_names=['combat expertise', 'outflank', 'following step',
                                  'step up', 'armor proficiency', 'weapon proficiency', 'power attack'],
                bab=5, fighter_level=5, monk_level=0, brawler_level=0,
                str_stat=20, con_stat=12, dex_stat=16, wis_stat=9, int_stat=14, cha_stat=7, race='human', deity='gorum')

print('\n'.join([feat.text for feat in sorted(m.get_flex_tree(depth=1, include_no_deps=True, include_teamwork=True))]))
